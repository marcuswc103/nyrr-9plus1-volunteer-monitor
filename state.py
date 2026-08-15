"""
State store for the NYRR 9+1 Volunteer Spot Monitor (SPEC.md section 4).

Holds, per race, the set of role names that currently match all three
9+1 criteria. Diffing against the previous run is what stops the monitor
from re-notifying about a role that was already open last time and you
haven't acted on yet — only NEWLY-matching roles should ever trigger a
notification.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
STATE_PATH = REPO_ROOT / "state.json"


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def diff_matches(old_state: dict, scrape_results: dict) -> tuple[dict, dict, dict]:
    """Compare this run's scrape results against the previously saved state.

    Args:
        old_state: previously saved state, shape
            {race_id: {"matching_roles": [role_name, ...]}}
        scrape_results: output of scraper.scrape_all_races(), shape
            {race_id: {"matches": [Opportunity, ...], "error": str|None}}

    Returns (newly_matching, new_state, errored):
        newly_matching: {race_id: [role_name, ...]} — ONLY roles that match
            now but did not match on the previous run. Empty list/omitted
            race_id if nothing new.
        new_state: the full state dict to save (state.json), race_id ->
            {"matching_roles": [...]}. Races that errored this run keep
            their previous state untouched rather than being cleared.
        errored: {race_id: error_message} for races whose scrape failed
            this run.
    """
    newly_matching = {}
    new_state = {}
    errored = {}

    for race_id, result in scrape_results.items():
        if result.get("error"):
            errored[race_id] = result["error"]
            # Preserve whatever we last knew for this race — a transient
            # scrape failure shouldn't wipe out or re-trigger matches.
            if race_id in old_state:
                new_state[race_id] = old_state[race_id]
            continue

        previously_matching = set(old_state.get(race_id, {}).get("matching_roles", []))
        currently_matching = {m.role_name for m in result["matches"]}

        newly = sorted(currently_matching - previously_matching)
        if newly:
            newly_matching[race_id] = newly

        new_state[race_id] = {"matching_roles": sorted(currently_matching)}

    # Carry forward state for any race present in old_state but absent from
    # this run's results (e.g. paused mid-way, or robots_allowed flipped).
    for race_id, race_state in old_state.items():
        if race_id not in new_state and race_id not in errored:
            new_state[race_id] = race_state

    return newly_matching, new_state, errored
