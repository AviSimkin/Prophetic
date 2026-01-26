"""
Integration tests for alert functionality.
Tests that the alert pipeline correctly identifies events needing alerts.
"""
import os
import sys
from datetime import datetime, timedelta

# Ensure project root is importable
ROOT = r"c:\code\Prophetic"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.timeline_simulator import TimelineSimulator
from src.calendar_parser import parse_calendar_file


def create_test_calendar_ics(base_date: datetime):
    """Create a test calendar with events at specific intervals from base_date."""
    events = [
        (0, "Event Today", "9:00 AM"),
        (1, "Event Tomorrow", "2:00 PM"),
        (3, "Event in 3 days", "10:00 AM"),
        (7, "Event in 7 days", "11:00 AM"),
        (10, "Event in 10 days", "3:00 PM"),
        (30, "Event in 30 days", "4:00 PM"),
    ]
    
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Prophetic//Test//EN",
    ]
    
    for days_offset, name, time_str in events:
        event_dt = base_date + timedelta(days=days_offset)
        dtstart = event_dt.strftime('%Y%m%dT%H%M%S')
        dtend = (event_dt + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')
        
        ics_lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{name}",
            "LOCATION:Test Location",
            f"DESCRIPTION:Test event scheduled for {time_str}",
            "END:VEVENT",
        ])
    
    ics_lines.append("END:VCALENDAR")
    return "\n".join(ics_lines).encode('utf-8')


def test_alert_window_1_day():
    """Test that events 0-1 days away trigger in 1-day alert window."""
    timeline = TimelineSimulator(demo_mode=True)
    base_date = datetime(2026, 1, 26, 10, 0, 0)
    timeline.set_date(base_date)
    
    ics_content = create_test_calendar_ics(base_date)
    events = parse_calendar_file(ics_content)
    
    # Get events needing alert within 1 day
    alerts_1day = timeline.get_events_needing_alert(events, days_before=1)
    
    print(f"\n1-day window test (from {base_date.date()}):")
    print(f"  Events found: {len(alerts_1day)}")
    for event in alerts_1day:
        days_until = timeline.days_until_event(event)
        print(f"    - {event['name']}: {days_until} days away")
    
    # Should include: Event Today (0 days) and Event Tomorrow (1 day)
    assert len(alerts_1day) == 2, f"Expected 2 events in 1-day window, got {len(alerts_1day)}"
    
    event_names = [e['name'] for e in alerts_1day]
    assert "Event Today" in event_names, "Should include Event Today"
    assert "Event Tomorrow" in event_names, "Should include Event Tomorrow"
    assert "Event in 3 days" not in event_names, "Should NOT include Event in 3 days"
    
    print("  ✅ PASS: 1-day window correctly identifies events 0-1 days away")


def test_alert_window_7_days():
    """Test that events 0-7 days away trigger in 7-day alert window."""
    timeline = TimelineSimulator(demo_mode=True)
    base_date = datetime(2026, 1, 26, 10, 0, 0)
    timeline.set_date(base_date)
    
    ics_content = create_test_calendar_ics(base_date)
    events = parse_calendar_file(ics_content)
    
    # Get events needing alert within 7 days
    alerts_7day = timeline.get_events_needing_alert(events, days_before=7)
    
    print(f"\n7-day window test (from {base_date.date()}):")
    print(f"  Events found: {len(alerts_7day)}")
    for event in alerts_7day:
        days_until = timeline.days_until_event(event)
        print(f"    - {event['name']}: {days_until} days away")
    
    # Should include: today, tomorrow, 3 days, 7 days (4 events)
    assert len(alerts_7day) == 4, f"Expected 4 events in 7-day window, got {len(alerts_7day)}"
    
    event_names = [e['name'] for e in alerts_7day]
    assert "Event Today" in event_names, "Should include Event Today"
    assert "Event Tomorrow" in event_names, "Should include Event Tomorrow"
    assert "Event in 3 days" in event_names, "Should include Event in 3 days"
    assert "Event in 7 days" in event_names, "Should include Event in 7 days"
    assert "Event in 10 days" not in event_names, "Should NOT include Event in 10 days"
    
    print("  ✅ PASS: 7-day window correctly identifies events 0-7 days away")


def test_days_until_calculation():
    """Test that days_until_event calculates correctly."""
    timeline = TimelineSimulator(demo_mode=True)
    base_date = datetime(2026, 1, 26, 10, 0, 0)
    timeline.set_date(base_date)
    
    ics_content = create_test_calendar_ics(base_date)
    events = parse_calendar_file(ics_content)
    
    print(f"\nDays-until calculation test (from {base_date.date()}):")
    
    expected_days = {
        "Event Today": 0,
        "Event Tomorrow": 1,
        "Event in 3 days": 3,
        "Event in 7 days": 7,
        "Event in 10 days": 10,
    }
    
    for event in events:
        if event['name'] in expected_days:
            days_until = timeline.days_until_event(event)
            expected = expected_days[event['name']]
            print(f"  {event['name']}: {days_until} days (expected {expected})")
            assert days_until == expected, f"{event['name']} should be {expected} days away, got {days_until}"
    
    print("  ✅ PASS: days_until_event calculates correctly")


def test_real_world_scenario():
    """Test Jan 26 -> should alert for Jan 29 (business meeting) and Jan 31 (lunch)."""
    timeline = TimelineSimulator(demo_mode=True)
    current_date = datetime(2026, 1, 26, 10, 0, 0)
    timeline.set_date(current_date)
    
    # Create calendar with Jan 29 and Jan 31 events
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Prophetic//Real World Test//EN
BEGIN:VEVENT
DTSTART:20260129T140000
DTEND:20260129T150000
SUMMARY:Business Meeting
LOCATION:Downtown Office
DESCRIPTION:Important client meeting
END:VEVENT
BEGIN:VEVENT
DTSTART:20260131T120000
DTEND:20260131T130000
SUMMARY:Lunch with Sarah
LOCATION:Cafe Downtown
DESCRIPTION:Catch up lunch
END:VEVENT
BEGIN:VEVENT
DTSTART:20260210T100000
DTEND:20260210T110000
SUMMARY:Team Standup
LOCATION:Office
DESCRIPTION:Weekly standup
END:VEVENT
END:VCALENDAR""".encode('utf-8')
    
    events = parse_calendar_file(ics_content)
    
    print(f"\nReal-world scenario test (Jan 26 -> Jan 29 & Jan 31):")
    print(f"  Current date: {current_date.date()}")
    
    # Test 1-day window
    alerts_1day = timeline.get_events_needing_alert(events, days_before=1)
    print(f"  1-day window alerts: {len(alerts_1day)}")
    for event in alerts_1day:
        days_until = timeline.days_until_event(event)
        print(f"    - {event['name']} on {event['start'].date()}: {days_until} days away")
    
    # Test 7-day window
    alerts_7day = timeline.get_events_needing_alert(events, days_before=7)
    print(f"  7-day window alerts: {len(alerts_7day)}")
    for event in alerts_7day:
        days_until = timeline.days_until_event(event)
        print(f"    - {event['name']} on {event['start'].date()}: {days_until} days away")
    
    # Business Meeting on Jan 29 is 3 days away
    # Lunch on Jan 31 is 5 days away
    # Both should appear in 7-day window, neither in 1-day window
    
    alert_7day_names = [e['name'] for e in alerts_7day]
    assert "Business Meeting" in alert_7day_names, "Jan 29 meeting should appear in 7-day alerts"
    assert "Lunch with Sarah" in alert_7day_names, "Jan 31 lunch should appear in 7-day alerts"
    assert "Team Standup" not in alert_7day_names, "Feb 10 event should NOT appear (15 days away)"
    
    alert_1day_names = [e['name'] for e in alerts_1day]
    assert "Business Meeting" not in alert_1day_names, "Jan 29 meeting should NOT appear in 1-day alerts (3 days away)"
    assert "Lunch with Sarah" not in alert_1day_names, "Jan 31 lunch should NOT appear in 1-day alerts (5 days away)"
    
    print("  ✅ PASS: Jan 26 correctly identifies Jan 29 & 31 events in 7-day window")


def test_time_independence():
    """Test that alerts work regardless of time-of-day."""
    timeline = TimelineSimulator(demo_mode=True)
    
    # Set current time to different hours
    test_times = [
        datetime(2026, 1, 26, 0, 0, 0),   # midnight
        datetime(2026, 1, 26, 9, 30, 0),  # morning
        datetime(2026, 1, 26, 14, 45, 0), # afternoon
        datetime(2026, 1, 26, 23, 59, 0), # end of day
    ]
    
    # Event tomorrow at 2 PM
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Prophetic//Time Test//EN
BEGIN:VEVENT
DTSTART:20260127T140000
DTEND:20260127T150000
SUMMARY:Tomorrow Event
LOCATION:Test Location
END:VEVENT
END:VCALENDAR""".encode('utf-8')
    
    events = parse_calendar_file(ics_content)
    
    print(f"\nTime-independence test:")
    
    for current_time in test_times:
        timeline.set_date(current_time)
        alerts = timeline.get_events_needing_alert(events, days_before=1)
        days_until = timeline.days_until_event(events[0]) if alerts else None
        
        print(f"  Current: {current_time} -> Found {len(alerts)} alerts, days_until: {days_until}")
        
        # Regardless of time, tomorrow's event should always be 1 day away
        assert len(alerts) == 1, f"Should find 1 alert at {current_time}, found {len(alerts)}"
        assert days_until == 1, f"Should be 1 day away at {current_time}, got {days_until}"
    
    print("  ✅ PASS: Alerts work consistently regardless of time-of-day")


if __name__ == '__main__':
    try:
        test_alert_window_1_day()
        test_alert_window_7_days()
        test_days_until_calculation()
        test_real_world_scenario()
        test_time_independence()
        
        print("\n" + "="*60)
        print("✅ ALL ALERT INTEGRATION TESTS PASSED")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
