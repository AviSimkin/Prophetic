"""
Smoke tests for Prophetic modules (no Streamlit required)
Run: python tests/smoke_test.py
Tests basic module functionality, import checks, and integration.
"""
import os
import sys
from datetime import datetime, timedelta

# Ensure project root is importable
ROOT = r"c:\code\Prophetic"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.prophetic_logger import get_logger, log_info, log_event
from src.calendar_parser import create_sample_calendar, create_israeli_calendar, parse_calendar_file
from src.llm_module import LLMModule
from src.web_scraper import WebScraper
from src.timeline_simulator import TimelineSimulator


def assert_true(cond, msg):
    if not cond:
        print(f"[FAIL] {msg}")
        raise SystemExit(1)
    print(f"[PASS] {msg}")


def test_logging():
    session_name = f"smoke-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger = get_logger(session_name=session_name)
    log_info("Smoke test started")
    log_event('smoke', 'logger_init', {'session': session_name})
    print(f"Logger initialized with session: {session_name}")


def test_calendars():
    # Sample calendar
    sbytes = create_sample_calendar()
    sevents = parse_calendar_file(sbytes)
    print(f"Sample calendar events: {len(sevents)}")
    assert_true(len(sevents) == 7, "Sample calendar has 7 events (including Sammy Ofer game)")
    missing_locs = [e for e in sevents if not e.get('location')]
    assert_true(len(missing_locs) >= 1, "Sample calendar includes events with missing location")

    # Israeli calendar
    ibytes = create_israeli_calendar()
    ievents = parse_calendar_file(ibytes)
    print(f"Israeli calendar events: {len(ievents)}")
    assert_true(len(ievents) == 7, "Israeli calendar has 7 events (including homework task)")
    missing_ilocs = [e for e in ievents if not e.get('location')]
    assert_true(len(missing_ilocs) >= 1, "Israeli calendar includes an event with missing location")


def test_llm_and_scraper():
    api_key = os.getenv('GOOGLE_API_KEY')
    llm = LLMModule(api_key=api_key)
    scraper = WebScraper(api_key=api_key)

    # Prepare an event with location and date
    from datetime import timedelta
    event = {
        'name': 'Test Meeting',
        'start': datetime.now() + timedelta(days=7),
        'location': 'Rothschild Blvd, Tel Aviv'
    }

    # Test questions generation (mock works without API)
    questions = llm.generate_questions({'name': 'Test', 'start': datetime.now()})
    assert_true('location' in questions, "LLMModule generates questions for missing fields")

    # Test scraper (mock or API)
    issues = scraper.check_for_issues(event)
    print(f"Scraper returned {len(issues)} issues; mode: {'mock' if scraper.use_mock else 'api'}")
    assert_true(isinstance(issues, list), "Scraper returns a list of issues")


def test_timeline_and_alerts():
    """Test timeline simulator and alert logic."""
    timeline = TimelineSimulator(demo_mode=True)
    base_date = datetime(2026, 1, 2, 10, 0, 0)  # Use Jan 2 when sample events are still upcoming
    timeline.set_date(base_date)
    
    # Create test events
    sbytes = create_sample_calendar()
    events = parse_calendar_file(sbytes)
    
    # Test get_upcoming_events
    upcoming = timeline.get_upcoming_events(events, days_ahead=30)
    assert_true(len(upcoming) > 0, "Timeline returns upcoming events")
    assert_true(all(e['start'] >= base_date for e in upcoming), "All upcoming events are in the future")
    
    # Test days_until_event
    if upcoming:
        days_until = timeline.days_until_event(upcoming[0])
        assert_true(isinstance(days_until, int), "days_until_event returns integer")
        assert_true(days_until >= 0, "days_until is non-negative for future events")
    
    # Test get_events_needing_alert
    alerts_1day = timeline.get_events_needing_alert(events, days_before=1)
    alerts_7day = timeline.get_events_needing_alert(events, days_before=7)
    assert_true(isinstance(alerts_1day, list), "get_events_needing_alert returns list")
    assert_true(isinstance(alerts_7day, list), "get_events_needing_alert returns list")
    assert_true(len(alerts_7day) >= len(alerts_1day), "7-day window should have >= events than 1-day window")
    
    print(f"Timeline test: {len(alerts_1day)} events in 1-day window, {len(alerts_7day)} in 7-day window")



if __name__ == '__main__':
    test_logging()
    test_calendars()
    test_llm_and_scraper()
    test_timeline_and_alerts()
    print("\n✅ All smoke tests passed.")

