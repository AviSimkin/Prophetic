"""Calendar parser and demo calendar generators."""
from datetime import datetime, time
from typing import List, Dict
import io

import pytz
from icalendar import Calendar, Event


def _normalize_datetime(dt):
    """Normalize datetimes to be timezone-naive for consistent comparisons."""
    from datetime import date

    if dt is None:
        return None

    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, time())

    if isinstance(dt, datetime):
        if dt.tzinfo is not None and dt.utcoffset() is not None:
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        return dt

    return dt


def parse_calendar_file(file_content: bytes) -> List[Dict]:
    """Parse an .ics calendar file and extract events."""
    events = []

    try:
        cal = Calendar.from_ical(file_content)

        for component in cal.walk():
            if component.name == "VEVENT":
                start_dt = component.get('dtstart').dt if component.get('dtstart') else None
                end_dt = component.get('dtend').dt if component.get('dtend') else None

                event = {
                    'name': str(component.get('summary', 'Untitled Event')),
                    'start': _normalize_datetime(start_dt),
                    'end': _normalize_datetime(end_dt),
                    'description': str(component.get('description', '')),
                    'location': str(component.get('location', '')),
                }

                events.append(event)

    except Exception as e:
        raise ValueError(f"Error parsing calendar file: {str(e)}")

    events.sort(key=lambda x: x['start'] if x['start'] else datetime.max)
    return events


def create_sample_calendar() -> bytes:
    """Create a sample .ics calendar file for testing."""
    from datetime import timedelta

    cal = Calendar()
    cal.add('prodid', '-//Prophetic Calendar//EN')
    cal.add('version', '2.0')

    base_date = datetime(2025, 12, 30, 19, 0, 0)

    events_data = [
        {
            'name': 'Evening Dinner Meeting',
            'start': base_date,
            'duration': 3,
            'description': 'Important dinner with clients'
        },
        {
            'name': 'Morning Workout Session',
            'start': datetime(2026, 1, 2, 7, 30, 0),
            'duration': 1.5,
            'description': 'Personal training session',
            'location': 'City Gym, Downtown'
        },
        {
            'name': 'Project Kickoff',
            'start': datetime(2026, 1, 5, 10, 0, 0),
            'duration': 2,
            'description': 'Q1 2026 project planning'
        },
        {
            'name': 'Lunch with Team',
            'start': datetime(2026, 1, 7, 12, 30, 0),
            'duration': 1.5,
            'description': 'Team building lunch',
            'location': 'The Garden Restaurant'
        },
        {
            'name': 'Tech Conference',
            'start': datetime(2026, 1, 10, 9, 0, 0),
            'duration': 8,
            'description': 'Annual technology conference'
        },
        {
            'name': 'Doctor Appointment',
            'start': datetime(2026, 1, 12, 15, 0, 0),
            'duration': 1,
            'description': 'Regular checkup'
        }
    ]

    for event_data in events_data:
        event = Event()
        event.add('summary', event_data['name'])
        event.add('dtstart', event_data['start'])
        event.add('dtend', event_data['start'] + timedelta(hours=event_data['duration']))
        event.add('description', event_data['description'])
        if 'location' in event_data:
            event.add('location', event_data['location'])
        cal.add_component(event)

    return cal.to_ical()


def create_israeli_calendar() -> bytes:
    """Create a sample Israeli calendar with typical events for demo mode."""
    from datetime import timedelta

    cal = Calendar()
    cal.add('prodid', '-//Prophetic Israeli Calendar//EN')
    cal.add('version', '2.0')

    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    events_data = [
        {
            'name': 'פגישה עסקית - Tel Aviv',
            'days_offset': 3,
            'duration': 2,
            'description': 'Important business meeting with startup founders'
        },
        {
            'name': 'אירוע משפחתי - Haifa',
            'days_offset': 6,
            'duration': 4,
            'description': 'Family celebration dinner',
            'location': 'German Colony, Haifa'
        },
        {
            'name': 'כנס היי-טק - Herzliya',
            'days_offset': 9,
            'duration': 6,
            'description': 'Annual Hi-Tech conference and expo'
        },
        {
            'name': 'טיול מאורגן - Dead Sea',
            'days_offset': 12,
            'duration': 10,
            'description': 'Day trip to the Dead Sea with colleagues',
            'location': 'Ein Bokek, Dead Sea'
        },
        {
            'name': 'השתלמות מקצועית - Jerusalem',
            'days_offset': 8,
            'duration': 3,
            'description': 'Professional development workshop on AI'
        },
        {
            'name': 'ארוחת צהריים - Jaffa',
            'days_offset': 5,
            'duration': 2,
            'description': 'Lunch meeting with potential investors',
            'location': 'Old Jaffa Port'
        }
    ]

    for event_data in events_data:
        event = Event()
        event.add('summary', event_data['name'])
        event.add('dtstart', base_date + timedelta(days=event_data['days_offset']))
        event.add('dtend', base_date + timedelta(days=event_data['days_offset'], hours=event_data['duration']))
        event.add('description', event_data['description'])
        if 'location' in event_data:
            event.add('location', event_data['location'])
        cal.add_component(event)

    return cal.to_ical()