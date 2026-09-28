"""
Safe execution sandbox for LLM-generated pandapower mutation code.

Provides AST-level validation to reject dangerous constructs and
restricted exec() with a controlled namespace.
"""
from __future__ import annotations

import ast
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import pandas as pd
import pandapower as pp


# ── Forbidden constructs ──────────────────────────────────────────

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests",
    "ctypes", "importlib", "code", "codeop",
}

FORBIDDEN_BUILTINS = {
    "eval", "exec", "compile", "open", "__import__",
    "globals", "locals", "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit", "input",
}

FORBIDDEN_ATTRIBUTES = {
    "__class__", "__subclasses__", "__bases__", "__mro__",
    "__dict__", "__globals__", "__code__", "__builtins__",
}


# ── AST Validator ─────────────────────────────────────────────────

class _SafetyVisitor(ast.NodeVisitor):
    """Walk the AST and collect violations."""

    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in ("pandapower", "pp", "numpy", "np", "pandas", "pd", "copy"):
                self.violations.append(
                    f"Forbidden import: '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            top = node.module.split(".")[0]
            if top not in ("pandapower", "pp", "numpy", "np", "pandas", "pd", "copy"):
                self.violations.append(
                    f"Forbidden from-import: '{node.module}'"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for forbidden builtin calls like eval(), exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_BUILTINS:
                self.violations.append(
                    f"Forbidden builtin call: '{node.func.id}()'"
                )
        # Check for forbidden module calls like os.system()
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id in FORBIDDEN_MODULES:
                    self.violations.append(
                        f"Forbidden module access: '{node.func.value.id}.{node.func.attr}'"
                    )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in FORBIDDEN_ATTRIBUTES:
            self.violations.append(
                f"Forbidden attribute access: '.{node.attr}'"
            )
        self.generic_visit(node)


def validate_code(code_str: str) -> tuple[bool, list[str]]:
    """
    Statically validate generated code via AST analysis.

    Returns:
        (is_safe, violations) — is_safe is True if no violations found.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    visitor = _SafetyVisitor()
    visitor.visit(tree)

    return len(visitor.violations) == 0, visitor.violations


# ── Safe Executor ─────────────────────────────────────────────────

def execute_safely(
    code_str: str,
    net: pp.pandapowerNet,
    timeout: int = 5,
) -> dict[str, Any]:
    """
    Execute LLM-generated code in a restricted namespace.

    The code has access to:
      - `net`: the pandapower network to mutate
      - `pp`: the pandapower module
      - `pd`: pandas
      - `np`: numpy

    Args:
        code_str: Python code string to execute
        net: pandapower network (will be mutated in-place)
        timeout: max seconds for execution

    Returns:
        dict with keys: "success", "error" (if any), "net"
    """
    import numpy as np

    # Step 1: Validate
    is_safe, violations = validate_code(code_str)
    if not is_safe:
        return {
            "success": False,
            "error": f"Code rejected by safety check: {'; '.join(violations)}",
            "net": net,
        }

    # Step 2: Build restricted namespace
    safe_builtins = {
        "abs": abs, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list,
        "max": max, "min": min, "print": print, "range": range,
        "round": round, "str": str, "sum": sum, "tuple": tuple,
        "True": True, "False": False, "None": None,
        "zip": zip, "sorted": sorted, "reversed": reversed,
        "isinstance": isinstance, "type": type,
        "__import__": __import__,
    }

    def prepare_for_sc(n: pp.pandapowerNet):
        n.ext_grid['s_sc_max_mva'] = 1000.0
        n.ext_grid['rx_max'] = 0.1
        if getattr(n, "gen", None) is not None and not n.gen.empty:
            if "vn_kv" not in n.gen.columns:
                n.gen["vn_kv"] = n.bus.loc[n.gen.bus, "vn_kv"].values
            else:
                n.gen["vn_kv"] = n.gen["vn_kv"].fillna(n.bus.loc[n.gen.bus, "vn_kv"].values)
            for col, val in [("sn_mva", 100.0), ("xdss_pu", 0.2), ("rdss_pu", 0.05), ("cos_phi", 0.8), ("rdss_ohm", 0.05), ("xdss_ohm", 0.2)]:
                if col not in n.gen.columns:
                    n.gen[col] = val
                else:
                    n.gen[col] = n.gen[col].fillna(val)
        if getattr(n, "sgen", None) is not None and not n.sgen.empty:
            for col, val in [("sn_mva", 10.0), ("k", 1.2), ("rx", 0.1)]:
                if col not in n.sgen.columns:
                    n.sgen[col] = val
                else:
                    n.sgen[col] = n.sgen[col].fillna(val)

    pp.prepare_for_sc = prepare_for_sc

    namespace = {
        "__builtins__": safe_builtins,
        "net": net,
        "pp": pp,
        "pd": pd,
        "np": np,
        "prepare_for_sc": prepare_for_sc,
    }

    # Step 3: Execute with timeout (thread-safe, no signal.SIGALRM)
    def _run():
        exec(code_str, namespace)  # noqa: S102

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run)
            future.result(timeout=timeout)
        return {"success": True, "error": None, "net": net}
    except FuturesTimeoutError:
        return {
            "success": False,
            "error": f"Execution timed out (exceeded {timeout}s limit)",
            "net": net,
        }
    except Exception:
        return {
            "success": False,
            "error": f"Execution error: {traceback.format_exc()}",
            "net": net,
        }

