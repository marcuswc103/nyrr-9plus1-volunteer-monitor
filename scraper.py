"""
Poll/scrape script for the NYRR 9+1 Volunteer Spot Monitor (SPEC.md section 3).

Only ever touches races marked robots_allowed: true in config/races.yaml.
Discovery found no JSON API backing the volunteer cards — the data is
already present in the server-rendered HTML on first load, so this uses a
single plain HTTP GET per race (no Playwright needed at runtime).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
import yaml
from bs4 import BeautifulSoup

from robots import USER_AGENT, check_robots_allowed

REQUEST_TIMEOUT_SECONDS = 20

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "races.yaml"

STATUS_AVAILABLE = "AVAILABLE"
STATUS_FILLED = "ALL SPOTS FILLED"
STATUS_UNKNOWN = "UNKNOWN"

_STATUS_ATTR_MAP = {"AVL": STATUS_AVAILABLE, "SOL": STATUS_FILLED}


@dataclass
class Opportunity:
    role_name: str
    status: str
    tags: list[str]
    link: str

    def is_match(self) -> bool:
        has_9plus1 = any(t.strip() == "9+1" for t in self.tags)
        has_background_check = any("background check" in t.lower() for t in self.tags)
        return self.status == STATUS_AVAILABLE and has_9plus1 and not has_background_check


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def parse_opportunities(html: str, race_url: str) -> list[Opportunity]:
    """Parse the volunteer opportunity cards out of a race page's HTML.

    Card structure (confirmed against real events.nyrr.org pages during
    discovery, see discovery_output/):

        <div class="category-box" data-filterable-status="AVL">
          <span>Available</span>                 <!-- badge text -->
          <div class="category-name">Bag Check</div>
          <span class="tag-box">9+1</span>
          <a href="https://register.nyrr.org/?event=...&option=...">Register</a>
        </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities = []

    for box in soup.select("div.category-box"):
        status_attr = box.get("data-filterable-status", "")
        status = _STATUS_ATTR_MAP.get(status_attr, STATUS_UNKNOWN)

        name_el = box.select_one(".category-name")
        role_name = name_el.get_text(strip=True) if name_el else "(unknown role)"

        tags = [t.get_text(strip=True) for t in box.select(".tag-box")]

        register_link = box.select_one('a[href*="register.nyrr.org"]')
        link = register_link["href"] if register_link else race_url

        opportunities.append(
            Opportunity(role_name=role_name, status=status, tags=tags, link=link)
        )

    return opportunities


def scrape_race(race: dict) -> dict:
    """Scrape a single race. Returns {opportunities, matches, error}.

    One request, no retries — a failure here is surfaced via `error` so the
    caller can trigger the canary alert rather than hammering the site.
    """
    race_id = race["race_id"]
    url = race["url"]

    if not race.get("robots_allowed"):
        return {
            "race_id": race_id,
            "opportunities": [],
            "matches": [],
            "error": "skipped: robots_allowed is not true",
        }

    # config/races.yaml's robots_allowed is only ever set by a manual
    # discovery.py run — it can go stale if NYRR changes robots.txt later.
    # Re-check the real robots.txt on every single run before fetching, so
    # this never relies on a cached/hardcoded value.
    if not check_robots_allowed(url):
        return {
            "race_id": race_id,
            "opportunities": [],
            "matches": [],
            "error": (
                "robots.txt now disallows this URL (config says robots_allowed: "
                "true, but a fresh check disagrees) — re-run discovery.py and "
                "update config/races.yaml"
            ),
        }

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        opportunities = parse_opportunities(resp.text, url)
    except Exception as e:
        return {
            "race_id": race_id,
            "opportunities": [],
            "matches": [],
            "error": str(e),
        }

    matches = [o for o in opportunities if o.is_match()]
    return {
        "race_id": race_id,
        "opportunities": opportunities,
        "matches": matches,
        "error": None,
    }


def scrape_all_races(config: dict) -> dict:
    """Scrape every active, robots-allowed race in config. Returns
    {race_id: scrape_race() result}, skipping paused (active: false) races
    entirely."""
    results = {}
    for race in config.get("races", []):
        if not race.get("active", True):
            continue
        if not race.get("robots_allowed"):
            continue
        results[race["race_id"]] = scrape_race(race)
    return results


if __name__ == "__main__":
    config = load_config()
    results = scrape_all_races(config)
    for race_id, result in results.items():
        if result["error"]:
            print(f"[{race_id}] ERROR: {result['error']}")
            continue
        print(f"[{race_id}] {len(result['opportunities'])} opportunities, {len(result['matches'])} match(es)")
        for m in result["matches"]:
            print(f"  MATCH: {m.role_name} -> {m.link}")
