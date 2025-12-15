"""
Smoke tests for Prophetic modules (no Streamlit required)
Run: C:/code/Prophetic/.venv/Scripts/python.exe tests/smoke_test.py
"""
import os
import sys
from datetime import datetime

# Ensure project root is importable
ROOT = r"c:\code\Prophetic"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from prophetic_logger import get_logger, log_info, log_event
from calendar_parser import create_sample_calendar, create_israeli_calendar, parse_calendar_file
from llm_module import LLMModule
from web_scraper import WebScraper


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
    assert_true(len(sevents) == 4, "Sample calendar has 4 events")
    missing_locs = [e for e in sevents if not e.get('location')]
    assert_true(len(missing_locs) >= 1, "Sample calendar includes events with missing location")

    # Israeli calendar
    ibytes = create_israeli_calendar()
    ievents = parse_calendar_file(ibytes)
    print(f"Israeli calendar events: {len(ievents)}")
    assert_true(len(ievents) == 3, "Israeli calendar has 3 events")
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


if __name__ == '__main__':
    test_logging()
    test_calendars()
    test_llm_and_scraper()
    print("\nAll smoke tests passed.")
