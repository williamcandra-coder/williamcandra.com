"""Uncle View and Analyst View show the same numbers, provably.

The failure mode this guards is not deliberate. It is that the simple view
acquires its own rounding, or its own convenience calculation, and six months
later the two views disagree by 2% and nobody can say which is right.

So the assertion is exact float equality against the record each item names —
not `approx`. If a view ever starts calculating, this fails.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong.narration import views as views_mod

from .conftest_bank import evaluate


@pytest.fixture
def valued(synthetic_bank):
    return evaluate(synthetic_bank)


def _records(result):
    """Every calculated record the valuation produced, keyed by ref."""
    index = {}
    for name in result.scenario_order:
        valuation = result.scenarios[name]
        for record in (valuation.primary.equity_value,
                       valuation.primary.value_per_share,
                       *valuation.primary.detail.values(),
                       *valuation.residual_income):
            index[record.ref] = record
        for check in valuation.cross_checks:
            index[check.equity_value.ref] = check.equity_value
            index[check.value_per_share.ref] = check.value_per_share
            index.update({r.ref: r for r in check.detail.values()})
    return index


# --- the identity ----------------------------------------------------------


def test_every_uncle_number_is_exactly_a_calculated_record(valued):
    index = _records(valued)
    for item in valued.views["uncle"].items:
        assert item.ref in index, item.label
        assert item.value == index[item.ref].value, item.label


def test_every_analyst_number_is_exactly_a_calculated_record(valued):
    index = _records(valued)
    for item in valued.views["analyst"].items:
        assert item.ref in index, item.label
        assert item.value == index[item.ref].value, item.label


def test_numbers_shared_by_both_views_are_identical(valued):
    """Not close. Identical."""
    uncle = valued.views["uncle"].numerics()
    analyst = valued.views["analyst"].numerics()
    shared = set(uncle) & set(analyst)
    assert shared, "the two views should overlap on the headline figures"
    for ref in sorted(shared):
        assert uncle[ref] == analyst[ref], ref


def test_the_base_case_value_appears_in_both_views(valued):
    ref = valued.base.primary.value_per_share.ref
    assert ref in valued.views["uncle"].numerics()
    assert ref in valued.views["analyst"].numerics()


# --- no arithmetic ---------------------------------------------------------


def test_the_narration_layer_contains_no_arithmetic(repo_root):
    """Asserted against the source. A behavioural test of today's views would
    not notice a calculation added tomorrow."""
    import ast

    source = (repo_root / "engine/goh_dip_tong/narration/views.py").read_text(
        encoding="utf-8")
    offenders = [
        type(node.op).__name__
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.BinOp)
        and type(node.op).__name__ in {"Add", "Sub", "Mult", "Div", "Pow"}
    ]
    assert offenders == [], offenders


def test_every_item_names_the_formula_behind_it(valued):
    for view in valued.views.values():
        for item in view.items:
            assert item.ref
            assert item.formula_id
            assert item.scenario


# --- labelling -------------------------------------------------------------


def test_both_views_carry_the_fixture_label(valued):
    for view in valued.views.values():
        joined = " ".join(view.notes)
        assert "FIXTURE_TEST_ONLY" in joined


def test_the_uncle_view_says_it_does_not_calculate(valued):
    joined = " ".join(valued.views["uncle"].notes)
    assert "selects" in joined and "does not calculate" in joined


def test_the_uncle_view_carries_the_advice_disclaimer(valued):
    assert any("Not investment advice" in n for n in valued.views["uncle"].notes)


def test_the_uncle_view_stays_short(valued):
    """A view that shows everything is the analyst view with friendlier
    labels, which helps nobody."""
    assert len(valued.views["uncle"].items) <= 6
    assert len(valued.views["analyst"].items) > len(valued.views["uncle"].items)


def test_the_analyst_view_covers_every_scenario(valued):
    labels = " ".join(i.label for i in valued.views["analyst"].items)
    for scenario in ("BEAR", "BASE", "BULL"):
        assert scenario in labels


def test_the_analyst_view_explains_why_cross_checks_diverge(valued):
    joined = " ".join(valued.views["analyst"].notes)
    assert "fade" in joined or "steady state" in joined


# --- serialisation ---------------------------------------------------------


def test_a_view_serialises_with_its_status(valued):
    payload = valued.views["uncle"].to_json()
    assert payload["status"] == "PRODUCED"
    assert payload["kind"] == "UNCLE"
    assert payload["items"]


def test_views_are_deterministic(synthetic_bank):
    first = evaluate(synthetic_bank).views["analyst"].to_json()
    second = evaluate(synthetic_bank).views["analyst"].to_json()
    assert first == second
