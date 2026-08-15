"""
Notifier for the NYRR 9+1 Volunteer Spot Monitor (SPEC.md section 5).

Uses ntfy.sh (https://ntfy.sh) — a free push-notification service with no
account required. NTFY_TOPIC is read from the environment only, never
hardcoded; treat it like a password since anyone who knows the topic name
can publish/subscribe to it.
"""

import argparse
import os
import sys

import requests

NTFY_PUBLISH_URL = "https://ntfy.sh/"
REQUEST_TIMEOUT_SECONDS = 15

# ntfy's JSON publish endpoint requires numeric priority (1-5), unlike the
# header-based publish API which accepts these names directly.
_PRIORITY_NAME_TO_NUMBER = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}


def _get_topic() -> str:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        raise RuntimeError("NTFY_TOPIC environment variable is not set")
    return topic


def _publish(title: str, message: str, priority: str = "default", click: str = None, tags: list = None) -> bool:
    payload = {
        "topic": _get_topic(),
        "title": title,
        "message": message,
        "priority": _PRIORITY_NAME_TO_NUMBER[priority],
    }
    if click:
        payload["click"] = click
    if tags:
        payload["tags"] = tags

    try:
        resp = requests.post(NTFY_PUBLISH_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"WARNING: failed to send ntfy notification '{title}': {e}", file=sys.stderr)
        return False


def send_opening_alert(race_name: str, role_name: str, link: str) -> bool:
    title = f"9+1 SPOT OPEN: {role_name} ({race_name})"
    message = f"A 9+1-eligible volunteer spot just opened up. Tap to register:\n{link}"
    return _publish(title, message, priority="urgent", click=link, tags=["rotating_light"])


def send_robots_blocked_reminder(races: list) -> bool | None:
    """races: list of {race_name, link}. No-ops cleanly if the list is empty."""
    if not races:
        return None
    lines = "\n".join(f"- {r['race_name']}: {r['link']}" for r in races)
    title = "Manual check needed (auto-monitoring blocked)"
    message = f"These races can't be auto-checked — please check them manually:\n{lines}"
    return _publish(title, message, priority="default", tags=["eyes"])


def send_canary_alert(race_name: str, error: str) -> bool:
    title = f"MONITOR BROKEN: {race_name}"
    message = f"The monitor broke while checking {race_name}: {error}\nCheck this race manually until it's fixed."
    return _publish(title, message, priority="high", tags=["warning", "skull"])


def main():
    parser = argparse.ArgumentParser(description="NYRR 9+1 Volunteer Monitor notifier")
    parser.add_argument("--test", action="store_true", help="Send one of each notification type and exit")
    args = parser.parse_args()

    if args.test:
        try:
            topic = _get_topic()
        except RuntimeError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        print(f"Sending test notifications to ntfy topic '{topic}'...")
        ok1 = send_opening_alert(
            "TEST: Ted Corbitt 15K", "Bag Check", "https://register.nyrr.org/?event=test&option=test"
        )
        ok2 = send_robots_blocked_reminder(
            [{"race_name": "TEST: Some Blocked Race", "link": "https://events.nyrr.org/test-blocked-race"}]
        )
        ok3 = send_canary_alert("TEST: Frosty 5K", "Simulated parser failure for --test")

        results = {"opening_alert": ok1, "robots_blocked_reminder": ok2, "canary_alert": ok3}
        for name, ok in results.items():
            print(f"  {name}: {'sent' if ok else 'FAILED'}")

        if not all(results.values()):
            sys.exit(1)
        print("All 3 test notifications sent. Check your phone.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
