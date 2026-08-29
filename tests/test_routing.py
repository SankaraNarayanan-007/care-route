"""
Run with: python -m pytest tests/  (or just: python tests/test_routing.py)
No Gemini API key required — this only tests the deterministic policy engine.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import routing


def test_urgent_injury_case():
    result = routing.evaluate(["recent_injury", "functional_difficulty"], True)
    assert result.queue == "URGENT_CLINICAL_REVIEW"
    assert result.rule_id == "U-03"


def test_insufficient_information_gate():
    result = routing.evaluate([], False)
    assert result.queue == "NEEDS_CLARIFICATION"
    assert result.rule_id == "GATE-INSUFFICIENT"


def test_routine_checkup():
    result = routing.evaluate(["routine_checkup"], True)
    assert result.queue == "ROUTINE_APPOINTMENT"


def test_administrative():
    result = routing.evaluate(["certificate_request"], True)
    assert result.queue == "ADMINISTRATIVE"


def test_no_matching_rule_defaults_to_routine():
    result = routing.evaluate(["something_unrecognized_xyz"], True)
    assert result.queue == "ROUTINE_APPOINTMENT"
    assert result.rule_id == "DEFAULT"


def test_injection_signal_not_urgent():
    result = routing.evaluate(["prompt_injection_detected"], True)
    assert result.queue == "NEEDS_CLARIFICATION"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("All tests passed.")
