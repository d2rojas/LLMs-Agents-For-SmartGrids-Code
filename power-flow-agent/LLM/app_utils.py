"""app_utils.py

为 Streamlit app.py 提供纯函数工具，方便单元测试与复用。

注意：本文件不依赖 streamlit。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


def safe_json_loads(s: str) -> Dict[str, Any]:
    """容错 JSON 解析。"""

    try:
        return json.loads(s)
    except Exception:
        return {}


@dataclass
class ToolArtifact:
    """从 tool 输出中提取的 UI 可渲染工件。"""

    tool_name: str
    payload: Dict[str, Any]

    @property
    def has_plot(self) -> bool:
        """tool 输出中是否包含 plotly figure_json。"""

        return isinstance(self.payload.get("figure_json"), str)

    @property
    def figure_json(self) -> Optional[str]:
        if self.has_plot:
            return self.payload.get("figure_json")
        return None

    @property
    def plot_type(self) -> Optional[str]:
        v = self.payload.get("plot_type")
        return str(v) if v is not None else None

    @property
    def has_n1_report(self) -> bool:
        return isinstance(self.payload.get("n1_report"), dict)

    @property
    def n1_report(self) -> Optional[Dict[str, Any]]:
        v = self.payload.get("n1_report")
        return v if isinstance(v, dict) else None

    @property
    def has_remedial_plan(self) -> bool:
        return isinstance(self.payload.get("remedial_plan"), dict)

    @property
    def remedial_plan(self) -> Optional[Dict[str, Any]]:
        v = self.payload.get("remedial_plan")
        return v if isinstance(v, dict) else None

    @property
    def extra_figures(self) -> List[Dict[str, Any]]:
        v = self.payload.get("extra_figures")
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict) and isinstance(x.get("figure_json"), str)]
        return []


def extract_tool_artifacts(new_history_entries: Iterable[Dict[str, Any]]) -> List[ToolArtifact]:
    """从 conversation_history 的增量片段中提取 tool 工件。"""

    artifacts: List[ToolArtifact] = []
    for e in new_history_entries:
        if e.get("role") != "tool":
            continue
        name = e.get("name") or ""
        payload = safe_json_loads(e.get("content") or "{}")
        artifacts.append(ToolArtifact(tool_name=name, payload=payload))
    return artifacts


def pick_last_plot(artifacts: List[ToolArtifact]) -> Optional[ToolArtifact]:
    """选取最后一个可绘图工件（如果有）。"""

    for a in reversed(artifacts):
        if a.has_plot:
            return a
    return None


def pick_last_n1_report(artifacts: List[ToolArtifact]) -> Optional[ToolArtifact]:
    """选取最后一个包含 N-1 报告的工件（如果有）。"""

    for a in reversed(artifacts):
        if a.has_n1_report:
            return a
    return None


def is_error_payload(payload: Dict[str, Any]) -> bool:
    return bool(payload.get("error"))
