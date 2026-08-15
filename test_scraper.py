"""
Tests for scraper.py's parsing logic. Uses a real saved page from
discovery_output/ so parsing can be verified without hitting the live
site, plus small synthetic snippets (built from the same real markup
pattern) to exercise the AVAILABLE+9+1 match case, since no real page
currently has one live (that's exactly the rare event this tool watches
for).
"""

from pathlib import Path
from unittest.mock import patch

from scraper import STATUS_AVAILABLE, STATUS_FILLED, parse_opportunities, scrape_race

FIXTURE_HTML = (Path(__file__).resolve().parent / "discovery_output" / "frosty-5k" / "rendered.html").read_text()
FIXTURE_URL = "https://events.nyrr.org/nyrr-frosty-5k-volunteers"


def test_parses_real_page_cards():
    opportunities = parse_opportunities(FIXTURE_HTML, FIXTURE_URL)
    assert len(opportunities) > 0

    statuses = {o.status for o in opportunities}
    assert statuses <= {STATUS_AVAILABLE, STATUS_FILLED}

    # Every card should have found a role name and at least one tag.
    for o in opportunities:
        assert o.role_name and o.role_name != "(unknown role)"
        assert len(o.tags) >= 1


def test_real_page_has_no_current_match():
    # As of discovery time, no card on this real page was simultaneously
    # AVAILABLE + 9+1 (that combination is what we're watching for).
    opportunities = parse_opportunities(FIXTURE_HTML, FIXTURE_URL)
    matches = [o for o in opportunities if o.is_match()]
    assert matches == []


def test_available_and_9plus1_card_matches():
    html = """
    <li>
      <div class="category-box" data-filterable-status="AVL">
        <span>Available</span>
        <div class="category-name">Bag Check</div>
        <span class="tag-box">9+1</span>
        <a href="https://register.nyrr.org/?event=abc123&option=def456">Register</a>
      </div>
    </li>
    """
    opportunities = parse_opportunities(html, FIXTURE_URL)
    assert len(opportunities) == 1
    o = opportunities[0]
    assert o.status == STATUS_AVAILABLE
    assert o.tags == ["9+1"]
    assert o.link == "https://register.nyrr.org/?event=abc123&option=def456"
    assert o.is_match() is True


def test_available_but_no_plus1_does_not_match():
    html = """
    <div class="category-box" data-filterable-status="AVL">
      <span>Available</span>
      <div class="category-name">Volunteer Leader</div>
      <span class="tag-box">No +1</span>
    </div>
    """
    opportunities = parse_opportunities(html, FIXTURE_URL)
    assert opportunities[0].is_match() is False


def test_9plus1_but_sold_out_does_not_match():
    html = """
    <div class="category-box" data-filterable-status="SOL">
      <span>All Spots Filled</span>
      <div class="category-name">Course Marshal</div>
      <span class="tag-box">9+1</span>
    </div>
    """
    opportunities = parse_opportunities(html, FIXTURE_URL)
    assert opportunities[0].status == STATUS_FILLED
    assert opportunities[0].is_match() is False


def test_available_9plus1_with_background_check_does_not_match():
    html = """
    <div class="category-box" data-filterable-status="AVL">
      <span>Available</span>
      <div class="category-name">Medical Support</div>
      <span class="tag-box">9+1</span>
      <span class="tag-box">Background Check Required</span>
      <a href="https://register.nyrr.org/?event=abc&option=def">Register</a>
    </div>
    """
    opportunities = parse_opportunities(html, FIXTURE_URL)
    assert opportunities[0].is_match() is False


def test_scrape_race_skips_when_config_says_robots_allowed_false():
    race = {"race_id": "x", "url": "https://events.nyrr.org/x", "robots_allowed": False}
    with patch("scraper.check_robots_allowed") as mock_check, patch("scraper.requests.get") as mock_get:
        result = scrape_race(race)

    mock_check.assert_not_called()  # cheap pre-filter short-circuits before any network call
    mock_get.assert_not_called()
    assert result["error"] == "skipped: robots_allowed is not true"


def test_scrape_race_rechecks_robots_txt_live_even_when_config_says_allowed():
    # Config says allowed, but a fresh robots.txt check disagrees (e.g. NYRR
    # changed it since the last discovery.py run) — must not fetch the page.
    race = {"race_id": "x", "url": "https://events.nyrr.org/x", "robots_allowed": True}
    with patch("scraper.check_robots_allowed", return_value=False) as mock_check, patch(
        "scraper.requests.get"
    ) as mock_get:
        result = scrape_race(race)

    mock_check.assert_called_once_with("https://events.nyrr.org/x")
    mock_get.assert_not_called()
    assert result["error"] is not None
    assert "robots.txt" in result["error"]


def test_no_register_link_falls_back_to_race_url():
    html = """
    <div class="category-box" data-filterable-status="SOL">
      <span>All Spots Filled</span>
      <div class="category-name">Bag Check</div>
      <span class="tag-box">9+1</span>
    </div>
    """
    opportunities = parse_opportunities(html, FIXTURE_URL)
    assert opportunities[0].link == FIXTURE_URL
