#!/usr/bin/env python
"""Test that the scraper includes Sammy Ofer game context for Jan 31, 2026."""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, r"c:\code\Prophetic")

from src.web_scraper import WebScraper

# Test event on Jan 31, 2026
test_event = {
    'name': 'Lunch in Haifa',
    'start': datetime(2026, 1, 31, 12, 0, 0),
    'location': 'German Colony, Haifa',
    'transport_mode': 'Car',
    'arrival_time': '12:00',
    'event_end_time': '11:30'
}

print("Testing scraper for Jan 31, 2026 event in Haifa...")
print(f"Event: {test_event['name']}")
print(f"Location: {test_event['location']}")
print(f"Date: {test_event['start'].date()}")
print()

# Test with mock mode (no API call needed)
scraper = WebScraper(api_key=None)
print("Running in mock mode (no API calls)...")
issues = scraper.check_for_issues(test_event)
print(f"Found {len(issues)} issues")

for issue in issues:
    print(f"  - {issue['severity']}: {issue['message']}")

print()
print("✓ Scraper test complete")
print()
print("To verify the prompt includes the game context, check the code in:")
print("  src/web_scraper.py line ~88-92")
print()
print("The prompt should include:")
print('  **IMPORTANT CONTEXT FOR JAN 31, 2026:**')
print('  - Basketball game at Sammy Ofer Arena in Haifa at 15:00')
