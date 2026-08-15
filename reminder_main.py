"""
Reminder entry point for the NYRR 9+1 Volunteer Spot Monitor. Run 3x/day
via GitHub Actions. If any active race is robots-blocked, sends one push
listing all of them so they can be checked by hand; otherwise no-ops.
"""

import notify
import scraper


def main():
    config = scraper.load_config()
    blocked = [
        {"race_name": r["name"], "link": r["url"]}
        for r in config.get("races", [])
        if r.get("active", True) and not r.get("robots_allowed")
    ]

    if not blocked:
        print("No robots-blocked races in config — nothing to remind about.")
        return

    ok = notify.send_robots_blocked_reminder(blocked)
    print(f"Sent robots-blocked reminder for {len(blocked)} race(s) [{'sent' if ok else 'FAILED TO SEND'}].")


if __name__ == "__main__":
    main()
