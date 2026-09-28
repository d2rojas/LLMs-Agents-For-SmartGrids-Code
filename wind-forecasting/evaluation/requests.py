"""The request every method receives for a benchmark instance: the text, the window, the question.

One request per (instance, horizon), generated with a seed from a few phrasings
an operator would use, so that reading the request is part of what is measured.
Each request carries a checkable question derived from the forecast the method
itself returns (the hour of highest mean power, or the energy over the horizon),
or no question. The ground truth (the target days) is read by the scorer only;
no method receives it and no tool can return it.

The list is generated once per run, serialised to ``requests.jsonl`` next to the
results, and hashed (``requests_digest``) into every row, so a table demonstrates
that every method answered the same requests.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

from config import HORIZONS_H, STEPS_PER_HOUR
from solver.data import Window, instances, load_manifest, load_window

QUESTIONS = ("peak_hour", "energy_kwh", "none")

_OPENINGS = (
    "Turbine {T} of the SDWPF wind farm. Its SCADA history covers days {a} to {b} at 10-minute sampling (144 rows per day). "
    "Forecast its active power in kW for the next {H} hours at 10-minute resolution, that is {N} values starting right after the last history row.",
    "For turbine {T}, using the 14-day SCADA record ending on day {b} (days {a} through {b}, 10-minute sampling), produce a {H}-hour-ahead "
    "forecast of active power: {N} values in kW, one per 10-minute step, beginning with the first step after the last row of the history.",
    "We need a {H} h active-power forecast for turbine {T} in the SDWPF farm, starting immediately after the last row of its history "
    "(days {a} to {b}, 10-minute SCADA). Return the {N} forecast values in kW in time order.",
)
_QUESTION_TEXT = {
    "peak_hour": " Also report the hour of the horizon, counted 1 to {H}, in which the mean forecast power is highest.",
    "energy_kwh": " Also report the energy the forecast implies over the horizon, in kWh: the sum of the 10-minute values divided by 6.",
    "none": " Report the series and say how it was produced.",
}


@dataclass
class Request:
    request_id: str
    instance_id: str
    turbine: int
    base_day: int
    history_days: List[int]
    horizon_hours: int
    question: str
    condition: str
    variant: int
    text: str
    seed: int

    def as_record(self) -> Dict[str, Any]:
        return asdict(self)


def request_text(turbine: int, history_days: Sequence[int], horizon_hours: int, question: str, variant: int) -> str:
    a, b = int(history_days[0]), int(history_days[1])
    body = _OPENINGS[variant % len(_OPENINGS)].format(T=turbine, a=a, b=b, H=horizon_hours, N=horizon_hours * STEPS_PER_HOUR)
    return body + _QUESTION_TEXT[question].format(H=horizon_hours)


def generate_requests(*, instance_ids: Optional[Sequence[str]] = None, horizons: Sequence[int] = HORIZONS_H, condition: str = "normal",
                      seed: int = 0, questions: Optional[Sequence[str]] = None, manifest: Optional[Dict[str, Any]] = None) -> List[Request]:
    m = manifest or load_manifest()
    inst = [e for e in instances(m) if instance_ids is None or e["instance_id"] in set(instance_ids)]
    if instance_ids is not None:
        missing = set(instance_ids) - {e["instance_id"] for e in inst}
        if missing:
            raise KeyError(f"unknown instance id(s) {sorted(missing)}")
    rng = random.Random(seed)
    qs = list(questions or QUESTIONS)
    out: List[Request] = []
    k = 0
    for e in inst:
        for h in horizons:
            q = qs[k % len(qs)]
            v = rng.randrange(len(_OPENINGS))
            k += 1
            rid = f"wind-{e['instance_id']}-h{int(h):02d}-{q}-s{seed}" + ("-stress" if condition != "normal" else "")
            out.append(Request(request_id=rid, instance_id=e["instance_id"], turbine=int(e["turbine"]), base_day=int(e["base_day"]),
                               history_days=list(e["history_days"]), horizon_hours=int(h), question=q, condition=condition, variant=v,
                               text=request_text(e["turbine"], e["history_days"], int(h), q, v), seed=seed))
    return out


def requests_digest(reqs: Sequence[Request]) -> str:
    h = hashlib.sha256()
    for r in reqs:
        h.update(json.dumps(r.as_record(), sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:12]


def request_from_dict(d: Dict[str, Any]) -> Request:
    return Request(**{k: d[k] for k in Request.__dataclass_fields__})


def window_for(req: Request, *, check_hash: bool = True, manifest: Optional[Dict[str, Any]] = None) -> Window:
    return load_window(req.turbine, req.base_day, condition=req.condition, check_hash=check_hash, manifest=manifest)
