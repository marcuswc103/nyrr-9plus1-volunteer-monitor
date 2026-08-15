"""
Discovery script for the NYRR 9+1 Volunteer Spot Monitor (SPEC.md section 2).

Run manually (not scheduled). For each race URL in config/races.yaml:
  1. Check robots.txt for events.nyrr.org via urllib.robotparser BEFORE
     touching the URL in any other way.
  2. If disallowed: log it as blocked, do not fetch/render it.
  3. If allowed: load the page with Playwright, capture every XHR/fetch
     request+response (looking especially for JSON), save the rendered
     HTML and a full-page screenshot to discovery_output/<race_id>/.

Writes robots_allowed: true/false back into config/races.yaml for each race
(never guessed elsewhere) and prints a summary against the 5-page decision
gate from SPEC.md.
"""

import json
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

from robots import USER_AGENT, check_robots_allowed

ROBOTS_THRESHOLD = 5

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "races.yaml"
DISCOVERY_OUTPUT_DIR = REPO_ROOT / "discovery_output"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


def run_discovery_for_race(race: dict, playwright):
    race_id = race["race_id"]
    url = race["url"]
    out_dir = DISCOVERY_OUTPUT_DIR / race_id
    out_dir.mkdir(parents=True, exist_ok=True)

    captured = []  # list of {url, resource_type, status, is_json, body_file}

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT)
    page = context.new_page()

    def handle_response(response):
        try:
            request = response.request
            if request.resource_type not in ("xhr", "fetch"):
                return
            content_type = response.headers.get("content-type", "")
            is_json = "json" in content_type.lower()
            entry = {
                "url": response.url,
                "method": request.method,
                "status": response.status,
                "resource_type": request.resource_type,
                "content_type": content_type,
                "is_json": is_json,
            }
            if is_json:
                try:
                    body = response.json()
                    idx = len(captured)
                    body_file = f"xhr_{idx:03d}.json"
                    with open(out_dir / body_file, "w") as f:
                        json.dump(body, f, indent=2)
                    entry["body_file"] = body_file
                except Exception as e:
                    entry["body_file"] = None
                    entry["body_error"] = str(e)
            captured.append(entry)
        except Exception as e:
            print(f"  (network capture error, ignored: {e})")

    page.on("response", handle_response)

    print(f"  Loading {url} ...")
    page.goto(url, wait_until="networkidle", timeout=45000)
    # Give any late XHR calls (filters, lazy widgets) a moment to fire.
    page.wait_for_timeout(3000)

    html = page.content()
    with open(out_dir / "rendered.html", "w") as f:
        f.write(html)

    page.screenshot(path=str(out_dir / "screenshot.png"), full_page=True)

    with open(out_dir / "network_requests.json", "w") as f:
        json.dump(captured, f, indent=2)

    context.close()
    browser.close()

    json_hits = [c for c in captured if c.get("is_json")]
    return {
        "xhr_fetch_count": len(captured),
        "json_response_count": len(json_hits),
        "json_urls": [c["url"] for c in json_hits],
    }


def main():
    config = load_config()
    races = config.get("races", [])

    blocked = []
    allowed = []
    results = {}

    print(f"Checking robots.txt for {len(races)} race URL(s)...\n")

    for race in races:
        race_id = race["race_id"]
        url = race["url"]
        print(f"[{race_id}] {url}")
        is_allowed = check_robots_allowed(url)
        race["robots_allowed"] = is_allowed
        if is_allowed:
            print("  robots.txt: ALLOWED")
            allowed.append(race)
        else:
            print("  robots.txt: BLOCKED")
            blocked.append(race)
        print()

    save_config(config)

    if allowed:
        print(f"Running Playwright discovery against {len(allowed)} allowed race(s)...\n")
        with sync_playwright() as playwright:
            for race in allowed:
                race_id = race["race_id"]
                print(f"[{race_id}] discovery...")
                try:
                    result = run_discovery_for_race(race, playwright)
                    results[race_id] = result
                    print(
                        f"  captured {result['xhr_fetch_count']} XHR/fetch call(s), "
                        f"{result['json_response_count']} JSON response(s)"
                    )
                except Exception as e:
                    results[race_id] = {"error": str(e)}
                    print(f"  ERROR during discovery: {e}")
                print()

    # ---- Summary ----
    print("=" * 70)
    print("DISCOVERY SUMMARY")
    print("=" * 70)
    total = len(races)
    print(f"Total race URLs checked: {total}")
    print(f"Auto-checkable (robots-allowed): {len(allowed)}")
    print(f"Robots-blocked: {len(blocked)}")
    print(
        f"\nDecision gate: {len(blocked)} blocked vs threshold of "
        f"{ROBOTS_THRESHOLD}"
    )
    if len(blocked) > ROBOTS_THRESHOLD:
        print(
            "  >>> STOP: more than 5 target races are robots-blocked. "
            "Per SPEC.md 'Decision gate', do not proceed to Prompt 2 — "
            "report this count back and rethink the approach."
        )
    else:
        print(
            "  OK to proceed to Prompt 2 (5 or fewer blocked, "
            f"actual: {len(blocked)})."
        )

    if blocked:
        print("\nBlocked races:")
        for race in blocked:
            print(f"  - {race['race_id']}: {race['url']}")

    if results:
        print("\nStructured data findings (allowed races):")
        for race_id, result in results.items():
            if "error" in result:
                print(f"  - {race_id}: ERROR ({result['error']})")
                continue
            if result["json_response_count"] > 0:
                print(
                    f"  - {race_id}: usable JSON API found "
                    f"({result['json_response_count']} JSON response(s)) -> "
                    f"see discovery_output/{race_id}/"
                )
                for u in result["json_urls"]:
                    print(f"      {u}")
            else:
                print(
                    f"  - {race_id}: no JSON API detected — will likely need "
                    f"HTML parsing. Inspect discovery_output/{race_id}/rendered.html"
                )

    print("\nOutput saved under discovery_output/<race_id>/ for each allowed race.")
    print("config/races.yaml has been updated with robots_allowed: true/false.")


if __name__ == "__main__":
    main()
