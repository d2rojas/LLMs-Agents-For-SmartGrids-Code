"""
Preprocessor: orchestrates evidence collection and rule evaluation
to produce a structured context for LLM prompting.
"""
from __future__ import annotations

from typing import Any

import pandapower as pp

from .evidence_collector import EvidenceCollector, EvidenceReport
from .rules import RuleEngine, RuleResult


class Preprocessor:
    """
    Orchestrates the full preprocessing pipeline:
      1. Collect evidence from the pandapower network
      2. Evaluate rules against the evidence
      3. Produce a structured context dictionary for LLM prompting
    """

    def __init__(self, v_min: float = 0.95, v_max: float = 1.05, max_loading: float = 100.0):
        self.collector = EvidenceCollector(v_min=v_min, v_max=v_max, max_loading=max_loading)
        self.rule_engine = RuleEngine()

    def process(self, net: pp.pandapowerNet) -> dict[str, Any]:
        """
        Run the full pipeline and return a structured context dict.

        Returns:
            dict with keys:
                - "evidence": EvidenceReport as dict
                - "evidence_text": human-readable evidence summary
                - "triggered_rules": list of triggered RuleResult dicts
                - "failure_category": classified failure type string
                - "network_summary": basic network stats
        """
        # Step 1: Collect evidence
        report = self.collector.collect(net)

        # Step 2: Evaluate rules
        rule_results = self.rule_engine.evaluate(report)
        failure_category = self.rule_engine.classify_failure(rule_results)

        # Step 3: Build context
        return {
            "evidence": report.to_dict(),
            "evidence_text": report.to_text(),
            "triggered_rules": [self._rule_to_dict(r) for r in rule_results],
            "failure_category": failure_category,
            "network_summary": self._network_summary(net),
        }

    def _rule_to_dict(self, rule: RuleResult) -> dict:
        return {
            "rule_name": rule.rule_name,
            "severity": rule.severity,
            "description": rule.description,
            "evidence": rule.evidence,
            "suggested_actions": rule.suggested_actions,
        }

    def _network_summary(self, net: pp.pandapowerNet) -> dict:
        return {
            "name": net.name if hasattr(net, "name") else "unknown",
            "buses": len(net.bus),
            "lines": len(net.line),
            "transformers": len(net.trafo),
            "generators": len(net.gen),
            "static_generators": len(net.sgen),
            "loads": len(net.load),
            "ext_grids": len(net.ext_grid),
            "shunts": len(net.shunt),
        }
