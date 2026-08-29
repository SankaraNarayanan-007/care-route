"""
Deterministic routing engine.

The LLM (src/llm.py) never chooses the final queue. It only extracts a
structured 'signals' list. This module matches those signals against
data/routing_policy.json — plain, auditable, human-editable rules — and
returns the suggested queue plus which rule fired and why.
"""
import json
import os
from typing import List

from src.models import RoutingResult

POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "routing_policy.json")


def load_policy() -> dict:
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(signals: List[str], information_sufficient: bool) -> RoutingResult:
    """
    Deterministic evaluation: signals -> queue.
    Rules are checked in ascending 'priority' order; first match wins.
    """
    policy = load_policy()

    if not information_sufficient:
        return RoutingResult(
            queue="NEEDS_CLARIFICATION",
            rule_id="GATE-INSUFFICIENT",
            description="Request did not pass the information-sufficiency gate.",
        )

    signal_set = set(signals)
    rules = sorted(policy["rules"], key=lambda r: r["priority"])

    for rule in rules:
        conditions = set(rule["conditions"])
        if rule["match_type"] == "all":
            matched = conditions.issubset(signal_set)
        else:  # "any"
            matched = bool(conditions & signal_set)
        if matched:
            return RoutingResult(
                queue=rule["queue"],
                rule_id=rule["rule_id"],
                description=rule["description"],
            )

    default = policy["default_rule"]
    return RoutingResult(
        queue=default["queue"],
        rule_id=default["rule_id"],
        description=default["description"],
    )


def signal_vocabulary() -> List[str]:
    return load_policy()["signal_vocabulary"]


def all_queues() -> List[str]:
    return load_policy()["queues"]
