"""
Main entry point for the NYRR 9+1 Volunteer Spot Monitor (SPEC.md
architecture overview). Run on a 30-minute schedule via GitHub Actions:

  scraper.py (robots_allowed races) -> state.py diff -> notify.py alerts
  -> save state.json

Prints a run summary to stdout for reading in GitHub Actions logs.
"""

import notify
import scraper
import state


def main():
    config = scraper.load_config()
    race_name_by_id = {r["race_id"]: r["name"] for r in config.get("races", [])}

    scrape_results = scraper.scrape_all_races(config)
    old_state = state.load_state()
    newly_matching, new_state, errored = state.diff_matches(old_state, scrape_results)

    alerts_sent = 0
    for race_id, role_names in newly_matching.items():
        race_name = race_name_by_id.get(race_id, race_id)
        matches_by_role = {m.role_name: m for m in scrape_results[race_id]["matches"]}
        for role_name in role_names:
            match = matches_by_role.get(role_name)
            link = match.link if match else next(
                (r["url"] for r in config["races"] if r["race_id"] == race_id), ""
            )
            ok = notify.send_opening_alert(race_name, role_name, link)
            print(f"  ALERT: {role_name} ({race_name}) -> {link} [{'sent' if ok else 'FAILED TO SEND'}]")
            alerts_sent += 1

    canaries_sent = 0
    for race_id, error in errored.items():
        race_name = race_name_by_id.get(race_id, race_id)
        ok = notify.send_canary_alert(race_name, error)
        print(f"  CANARY: {race_name}: {error} [{'sent' if ok else 'FAILED TO SEND'}]")
        canaries_sent += 1

    state.save_state(new_state)

    races_checked = len(scrape_results)
    total_opportunities = sum(len(r.get("opportunities", [])) for r in scrape_results.values())

    print("=" * 60)
    print("MONITOR RUN SUMMARY")
    print("=" * 60)
    print(f"Races checked:        {races_checked}")
    print(f"Opportunities seen:   {total_opportunities}")
    print(f"New matches found:    {sum(len(v) for v in newly_matching.values())}")
    print(f"Opening alerts sent:  {alerts_sent}")
    print(f"Races errored:        {len(errored)}")
    print(f"Canary alerts sent:   {canaries_sent}")


if __name__ == "__main__":
    main()
