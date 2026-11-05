import copy

import pytest

from agents.contracts import build_context
from agents.financial_agent import audit_financial_context
from agents.service import audit_snapshot


def test_snapshot_hash_is_stable_for_same_payload():
    first = build_context(task="audit", model_inputs={"wacc": 0.1})
    second = build_context(task="audit", model_inputs={"wacc": 0.1})
    assert first.snapshot_hash == second.snapshot_hash
    assert first.run_id != second.run_id


def test_wacc_weights_flag_when_not_sum_to_one():
    context = build_context(task="audit", model_inputs={"debt_weight": 0.7, "equity_weight": 0.2})
    result = audit_financial_context(context)
    assert result.status == "warning"
    assert any(item["id"] == "FIN-WACC-001" for item in result.findings)


def test_wacc_formula_passes_when_consistent():
    context = build_context(
        task="audit",
        model_inputs={"debt_weight": 0.4, "equity_weight": 0.6, "kd": 0.08, "ke": 0.12, "tax_rate": 0.25},
        model_outputs={"wacc": 0.096},
    )
    result = audit_financial_context(context)
    assert not any(item["id"] == "FIN-WACC-001" for item in result.findings)
    assert not any(item["id"] == "FIN-WACC-002" for item in result.findings)


def test_wacc_formula_flags_reported_mismatch():
    context = build_context(
        task="audit",
        model_inputs={"debt_weight": 0.4, "equity_weight": 0.6, "kd": 0.08, "ke": 0.12, "tax_rate": 0.25},
        model_outputs={"wacc": 0.11},
    )
    result = audit_financial_context(context)
    assert any(item["id"] == "FIN-WACC-002" for item in result.findings)


def test_fcff_identity_passes_and_flags_mismatch():
    base = {"nopat": 100.0, "depreciation": 20.0, "capex": 30.0, "change_nwc": 10.0}
    ok = build_context(task="audit", model_inputs=base, model_outputs={"fcff": 80.0})
    bad = build_context(task="audit", model_inputs=base, model_outputs={"fcff": 75.0})
    assert not any(x["id"] == "FIN-FCFF-001" for x in audit_financial_context(ok).findings)
    assert any(x["id"] == "FIN-FCFF-001" for x in audit_financial_context(bad).findings)


def test_terminal_value_blocks_when_growth_is_not_below_wacc():
    context = build_context(task="audit", model_inputs={"wacc": 0.08, "terminal_growth": 0.08})
    result = audit_financial_context(context)
    assert result.status == "blocked"
    assert any(x["id"] == "FIN-TV-001" for x in result.findings)


def test_incomplete_context_reports_limitations_not_false_success():
    context = build_context(task="audit", model_inputs={}, model_outputs={})
    result = audit_financial_context(context)
    assert result.status == "warning"
    assert result.limitations


def test_service_does_not_mutate_input_payload():
    payload = {"task": "test", "model_inputs": {"debt_weight": 0.5, "equity_weight": 0.5}}
    before = copy.deepcopy(payload)
    report = audit_snapshot(payload)
    assert payload == before
    assert report["approval_required"] is True
    assert report["changes_applied"] is False


def test_service_rejects_invalid_payload():
    with pytest.raises(TypeError):
        audit_snapshot(["not", "an", "object"])
    with pytest.raises(TypeError):
        audit_snapshot({"model_inputs": []})
