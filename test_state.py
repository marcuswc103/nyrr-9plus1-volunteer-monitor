"""
Tests for state.py's diff logic — specifically that a role which already
matched last run does NOT re-trigger a notification, and that a role
which newly starts matching DOES. SPEC.md flags this as easy to get
backwards, so it's tested explicitly here.
"""

from dataclasses import dataclass

from state import diff_matches


@dataclass
class FakeMatch:
    role_name: str


def scrape_result(matches, error=None):
    return {"matches": [FakeMatch(r) for r in matches], "error": error}


def test_first_run_all_matches_are_new():
    old_state = {}
    scrape_results = {"frosty-5k": scrape_result(["Bag Check"])}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert newly == {"frosty-5k": ["Bag Check"]}
    assert new_state["frosty-5k"]["matching_roles"] == ["Bag Check"]
    assert errored == {}


def test_role_still_matching_does_not_renotify():
    old_state = {"frosty-5k": {"matching_roles": ["Bag Check"]}}
    scrape_results = {"frosty-5k": scrape_result(["Bag Check"])}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert newly == {}
    assert new_state["frosty-5k"]["matching_roles"] == ["Bag Check"]


def test_new_role_matching_alongside_existing_only_flags_the_new_one():
    old_state = {"frosty-5k": {"matching_roles": ["Bag Check"]}}
    scrape_results = {"frosty-5k": scrape_result(["Bag Check", "Course Marshal"])}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert newly == {"frosty-5k": ["Course Marshal"]}
    assert set(new_state["frosty-5k"]["matching_roles"]) == {"Bag Check", "Course Marshal"}


def test_role_no_longer_matching_is_removed_and_not_flagged():
    old_state = {"frosty-5k": {"matching_roles": ["Bag Check"]}}
    scrape_results = {"frosty-5k": scrape_result([])}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert newly == {}
    assert new_state["frosty-5k"]["matching_roles"] == []


def test_role_that_closes_then_reopens_notifies_again():
    # Simulates: open -> closed (someone registers) -> open again (they
    # cancel). This should notify both times, not just the first.
    state_after_open = {}
    results_open = {"frosty-5k": scrape_result(["Bag Check"])}
    newly1, state1, _ = diff_matches(state_after_open, results_open)
    assert newly1 == {"frosty-5k": ["Bag Check"]}

    results_closed = {"frosty-5k": scrape_result([])}
    newly2, state2, _ = diff_matches(state1, results_closed)
    assert newly2 == {}

    results_reopened = {"frosty-5k": scrape_result(["Bag Check"])}
    newly3, state3, _ = diff_matches(state2, results_reopened)
    assert newly3 == {"frosty-5k": ["Bag Check"]}


def test_errored_race_preserves_previous_state_and_does_not_renotify():
    old_state = {"frosty-5k": {"matching_roles": ["Bag Check"]}}
    scrape_results = {"frosty-5k": scrape_result([], error="parser broke")}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert newly == {}
    assert new_state["frosty-5k"]["matching_roles"] == ["Bag Check"]
    assert errored == {"frosty-5k": "parser broke"}


def test_race_missing_from_results_is_carried_forward_unchanged():
    old_state = {
        "frosty-5k": {"matching_roles": ["Bag Check"]},
        "ted-corbitt-15k": {"matching_roles": []},
    }
    scrape_results = {"frosty-5k": scrape_result(["Bag Check"])}

    newly, new_state, errored = diff_matches(old_state, scrape_results)

    assert "ted-corbitt-15k" in new_state
    assert new_state["ted-corbitt-15k"]["matching_roles"] == []
