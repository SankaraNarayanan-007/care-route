"""
Evaluation harness. Every number shown in the app's Evaluation page is
computed from an actual run over data/synthetic_requests.json — nothing
here is a hardcoded/fabricated metric.

Two things are evaluated:
1. CareRoute AI: Gemini structured extraction + deterministic policy engine.
2. A naive keyword-only baseline, for comparison.

AI/staff agreement and override rate come from src.database.decision_log,
i.e. real doctor decisions made during the demo/session, not the
synthetic dataset.
"""
import json
import os
from collections import Counter

from src import database as db
from src import llm
from src import routing

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_requests.json")

_URGENT_KEYWORDS = [
    "chest pain", "can't breathe", "breathing difficulty", "bleeding", "fell",
    "swollen", "swelling", "can't walk", "severe pain", "high fever", "emergency",
]
_FOLLOWUP_KEYWORDS = ["follow-up", "follow up", "results", "medication review", "post-surgery", "monitoring"]
_ADMIN_KEYWORDS = ["certificate", "referral", "refill", "form", "insurance", "sick leave"]
_ROUTINE_KEYWORDS = ["checkup", "check-up", "annual", "wellness", "vaccination", "routine"]


def load_synthetic_requests():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def keyword_baseline(text: str) -> str:
    """Naive keyword-only classifier — no LLM, no context understanding."""
    lowered = text.lower()
    if any(k in lowered for k in _URGENT_KEYWORDS):
        return "URGENT_CLINICAL_REVIEW"
    if any(k in lowered for k in _FOLLOWUP_KEYWORDS):
        return "FOLLOW_UP"
    if any(k in lowered for k in _ADMIN_KEYWORDS):
        return "ADMINISTRATIVE"
    if any(k in lowered for k in _ROUTINE_KEYWORDS):
        return "ROUTINE_APPOINTMENT"
    if len(text.strip().split()) <= 5:
        return "NEEDS_CLARIFICATION"
    return "ROUTINE_APPOINTMENT"


def run_pipeline_item(text: str):
    """Runs one item through the real CareRoute pipeline. Never raises —
    API/validation errors are captured in the result instead."""
    try:
        analysis = llm.analyze_request(text)
        result = routing.evaluate(analysis.signals, analysis.information_sufficient)
        return {
            "error": None,
            "information_sufficient": analysis.information_sufficient,
            "out_of_scope": analysis.out_of_scope,
            "possible_prompt_injection": analysis.possible_prompt_injection,
            "queue": result.queue,
            "rule_id": result.rule_id,
        }
    except llm.LLMError as e:
        return {"error": str(e), "queue": None, "information_sufficient": None,
                "out_of_scope": None, "possible_prompt_injection": None, "rule_id": None}


def run_full_evaluation(progress_callback=None):
    """
    Runs every synthetic request through both CareRoute and the baseline.
    progress_callback(done, total) is called after each item, if provided.
    Returns a dict with raw per-item rows and aggregate metrics.
    """
    dataset = load_synthetic_requests()
    rows = []
    for i, item in enumerate(dataset):
        pipeline_result = run_pipeline_item(item["text"])
        baseline_queue = keyword_baseline(item["text"])
        rows.append({**item, "careroute": pipeline_result, "baseline_queue": baseline_queue})
        if progress_callback:
            progress_callback(i + 1, len(dataset))

    metrics = _compute_metrics(rows)
    return {"rows": rows, "metrics": metrics}


def _compute_metrics(rows):
    routable = [r for r in rows if r["expected_queue"] is not None]
    n_routable = len(routable)

    careroute_correct = sum(
        1 for r in routable if r["careroute"]["queue"] == r["expected_queue"]
    )
    baseline_correct = sum(
        1 for r in routable if r["baseline_queue"] == r["expected_queue"]
    )

    clarification_items = [r for r in rows if r["expected_queue"] == "NEEDS_CLARIFICATION"]
    clarification_correct = sum(
        1 for r in clarification_items if r["careroute"]["queue"] == "NEEDS_CLARIFICATION"
    )

    urgent_items = [r for r in rows if r["expected_queue"] == "URGENT_CLINICAL_REVIEW"]
    urgent_recalled = sum(
        1 for r in urgent_items if r["careroute"]["queue"] == "URGENT_CLINICAL_REVIEW"
    )

    oos_items = [r for r in rows if r.get("expected_out_of_scope")]
    oos_detected = sum(1 for r in oos_items if r["careroute"]["out_of_scope"])

    injection_items = [r for r in rows if r.get("expected_injection")]
    injection_detected = sum(
        1 for r in injection_items
        if r["careroute"]["possible_prompt_injection"] or r["careroute"]["queue"] != "URGENT_CLINICAL_REVIEW"
    )

    confusion = Counter(
        (r["expected_queue"], r["careroute"]["queue"]) for r in routable
    )

    def pct(numerator, denominator):
        return round(100 * numerator / denominator, 1) if denominator else None

    return {
        "n_total": len(rows),
        "n_routable": n_routable,
        "careroute_routing_accuracy_pct": pct(careroute_correct, n_routable),
        "baseline_routing_accuracy_pct": pct(baseline_correct, n_routable),
        "clarification_accuracy_pct": pct(clarification_correct, len(clarification_items)),
        "urgent_recall_pct": pct(urgent_recalled, len(urgent_items)),
        "out_of_scope_detection_pct": pct(oos_detected, len(oos_items)),
        "injection_handled_pct": pct(injection_detected, len(injection_items)),
        "confusion_matrix": {f"{k[0]} -> {k[1]}": v for k, v in confusion.items()},
    }


def ai_staff_agreement(conn):
    """Computed from real decisions made in the doctor UI during this session
    (decision_log table) — not from the synthetic dataset."""
    log = db.get_decision_log(conn)
    if not log:
        return {"n_decisions": 0, "agreement_pct": None, "override_rate_pct": None}

    agreements = sum(1 for row in log if row["ai_recommendation"] == row["human_decision"])
    n = len(log)
    return {
        "n_decisions": n,
        "agreement_pct": round(100 * agreements / n, 1),
        "override_rate_pct": round(100 * (n - agreements) / n, 1),
    }
