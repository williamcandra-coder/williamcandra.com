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
    """Every calculated record the valuation produced, keyed by ref.

    The comparison map is the authority — it is what the Analyst View is built
    from and what the research rules cite — so it is indexed first. The
    scenario walk below is kept because it reaches the records independently,
    which is the point: if the two disagreed about a ref, this index would show
    it rather than paper over it.
    """
    index = {record.ref: record for record in result.comparison.values()}
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


# --- the two views are projections of one record set ----------------------


def test_uncle_view_refs_are_a_subset_of_analyst_view_refs(valued):
    """Not "similar". Every ref Uncle View shows, Analyst View shows too — so
    the two can be checked against each other rather than merely looking
    consistent."""
    uncle = set(valued.views["uncle"].numerics())
    analyst = set(valued.views["analyst"].numerics())
    assert uncle
    assert uncle <= analyst, sorted(uncle - analyst)


def test_shared_numbers_are_byte_identical_in_both_views(valued):
    """Compared as serialised bytes, not as floats. Two views that agree to
    fifteen decimals and render differently still disagree on screen."""
    import json

    uncle = {i.ref: json.dumps(i.value) for i in valued.views["uncle"].items}
    analyst = {i.ref: json.dumps(i.value) for i in valued.views["analyst"].items}
    shared = set(uncle) & set(analyst)
    assert shared
    for ref in sorted(shared):
        assert uncle[ref] == analyst[ref], ref


def test_both_views_draw_conclusions_from_the_same_package(valued):
    uncle_ids = {c["id"] for c in valued.views["uncle"].conclusions}
    analyst_ids = {c["id"] for c in valued.views["analyst"].conclusions}
    assert uncle_ids
    assert uncle_ids <= analyst_ids, sorted(uncle_ids - analyst_ids)


def test_a_conclusion_says_the_same_thing_in_both_views(valued):
    analyst = {c["id"]: c["statement"]
               for c in valued.views["analyst"].conclusions}
    for conclusion in valued.views["uncle"].conclusions:
        assert conclusion["statement"] == analyst[conclusion["id"]]


def test_the_uncle_view_carries_conclusions_without_their_citations(valued):
    """A plain-language reader will not follow a fact key. The same record is
    one click away in the Analyst View, under the same id."""
    for conclusion in valued.views["uncle"].conclusions:
        assert "supportingRecords" not in conclusion
        assert conclusion["ruleId"]


def test_the_analyst_view_carries_the_citations(valued):
    for conclusion in valued.views["analyst"].conclusions:
        assert "supportingRecords" in conclusion
        assert "supportingEvidence" in conclusion
    assert valued.views["analyst"].evidence


def test_every_conclusion_cited_record_is_one_the_analyst_view_shows(valued):
    shown = set(valued.views["analyst"].numerics())
    for conclusion in valued.views["analyst"].conclusions:
        for ref in conclusion.get("supportingRecords") or []:
            assert ref in shown, (conclusion["id"], ref)


def test_the_uncle_view_stays_short_even_with_conclusions(valued):
    from engine.goh_dip_tong.narration.views import UNCLE_CONCLUSION_LIMIT

    assert len(valued.views["uncle"].conclusions) <= UNCLE_CONCLUSION_LIMIT
    assert (len(valued.views["analyst"].conclusions)
            > len(valued.views["uncle"].conclusions))


def test_the_uncle_view_leads_with_the_most_important_conclusions(valued):
    """Ordering is by importance, not by the order the rules happened to fire.
    Adding a rule must not silently reorder what a reader sees first."""
    importances = [c["importance"] for c in valued.views["uncle"].conclusions]
    high = [i for i, v in enumerate(importances) if v == "HIGH"]
    other = [i for i, v in enumerate(importances) if v != "HIGH"]
    assert not (high and other) or max(high) < min(other)
