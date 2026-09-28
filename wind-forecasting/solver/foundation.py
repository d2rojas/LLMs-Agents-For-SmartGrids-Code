"""The third-party forecaster: a pretrained time-series foundation model, used zero shot.

Chronos-Bolt (Ansari et al., *Chronos: Learning the Language of Time Series*, TMLR 2024;
the Bolt variant is the non-autoregressive one), taken off the shelf from
``amazon/chronos-bolt-small`` and never trained, fine-tuned or adapted here. It is in the
catalogue for one reason: every other forecaster in this case study was fitted by us, and a
reader is entitled to an anchor that was not.

Three things about it belong next to its numbers rather than in a footnote.

**It is not a chat model.** It reads a sequence of numbers and writes the next ones. It cannot
read the request, choose a horizon, refuse, or explain. That is why it is a tool and not one of
the six methods: five of those are defined by how they decide, and this one decides nothing.

**It sees power only.** The model is univariate, so unlike the GRU it never sees wind speed,
direction or temperature. That is a property of the model class, not a handicap we imposed, and
it is the honest reason to expect less of it.

**Its pretraining corpus is published and this dataset is not in it.** Chronos was trained on
twenty-eight public collections; the wind ones are the Monash wind farm series at hourly and
daily resolution, and the KDD Cup entry in that corpus is the 2018 air-quality one. SDWPF, at
ten-minute resolution, is not among them. That is documentation and not proof, which is why the
scaled condition exists: under it the published values no longer match and any forecaster that
was retrieving rather than predicting loses its advantage.

The weights are cached under ``data/foundation/`` on first use and the cache is read offline
afterwards, so a run needs the network once and never again.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

import numpy as np
import pandas as pd

from config import PROJECT_ROOT, STEPS_PER_HOUR

MODEL_ID = "amazon/chronos-bolt-small"
CACHE_DIR = PROJECT_ROOT / "data" / "foundation"
CONTEXT_STEPS = 2016          # the whole 14-day history, within the model's 2048-step context
_PIPE: Optional[Any] = None


def available() -> bool:
    try:
        import chronos  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def pipeline() -> Any:
    """The cached pipeline, downloaded once into ``data/foundation/``."""
    global _PIPE
    if _PIPE is not None:
        return _PIPE
    import torch
    from chronos import BaseChronosPipeline

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(CACHE_DIR))
    _PIPE = BaseChronosPipeline.from_pretrained(MODEL_ID, device_map="cpu", torch_dtype=torch.float32, cache_dir=str(CACHE_DIR))
    return _PIPE


def metadata() -> dict:
    return {
        "model": MODEL_ID,
        "kind": "pretrained time-series foundation model, zero shot",
        "citation": "Ansari et al., Chronos: Learning the Language of Time Series, TMLR 2024",
        "inputs": "the active-power history only (the model is univariate)",
        "context_steps": CONTEXT_STEPS,
        "trained_here": False,
        "pretraining_note": "SDWPF is not in the published Chronos corpus; its wind entries are the Monash hourly and daily series",
    }


def forecast(window: Any, horizon_h: int) -> List[float]:
    """The median of the model's predictive distribution over the horizon, in kW.

    The context is the window's own power history and nothing else. The model normalises its
    input internally, so a turbine of another rating is read correctly and the scaled condition
    costs it nothing, exactly as for the other forecasters."""
    import torch

    n = int(horizon_h) * STEPS_PER_HOUR
    hist = pd.to_numeric(window.history()["Patv"], errors="coerce").clip(lower=0).ffill().bfill().fillna(0.0).to_numpy(dtype=float)
    ctx = torch.tensor(hist[-CONTEXT_STEPS:], dtype=torch.float32).unsqueeze(0)
    q, _mean = pipeline().predict_quantiles(inputs=ctx, prediction_length=n, quantile_levels=[0.5])
    y = np.clip(q[0, :, 0].numpy(), 0.0, window.power_max_kw)
    return [round(float(v), 1) for v in y[:n]]
