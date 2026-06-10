"""solver package.

包含：
- case_loader：IEEE 测试用例加载
- power_flow：潮流求解与网络修改封装
- validators：结果校验与越限检测

兼容性说明：
在某些环境中，numba 与 coverage 的版本组合可能导致 numba import 报错。
Pandapower 会尝试 import numba 以加速计算，因此这里做一个“尽量不打扰用户环境”的
轻量补丁：如果检测到 coverage.types 缺少 numba 所需的类型别名，就补齐为 typing.Any。
"""

from __future__ import annotations


def _patch_coverage_for_numba() -> None:
    """Best-effort patch to avoid numba import failures caused by coverage typing API drift."""

    try:
        import coverage  # type: ignore
    except Exception:
        return

    try:
        import types as pytypes
        from typing import Any

        if not hasattr(coverage, "types"):
            coverage.types = pytypes.SimpleNamespace()  # type: ignore[attr-defined]

        ct = coverage.types  # type: ignore[attr-defined]

        # numba.misc.coverage_support may reference these symbols.
        needed = [
            "Tracer",
            "TShouldTraceFn",
            "TShouldStartContextFn",
            "TWarnFn",
            "TTraceFn",
            "TFileDisposition",
        ]

        for name in needed:
            if not hasattr(ct, name):
                setattr(ct, name, Any)

        # Back-compat: some coverage versions expose TTracer instead of Tracer.
        if not hasattr(ct, "Tracer") and hasattr(ct, "TTracer"):
            setattr(ct, "Tracer", getattr(ct, "TTracer"))

    except Exception:
        # Never fail import of our package because of this patch.
        return


_patch_coverage_for_numba()

__all__ = []
