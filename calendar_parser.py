"""
Calendar parser module for handling .ics files
"""
from icalendar import Calendar
from datetime import datetime
from typing import List, Dict
import io


def parse_calendar_file(file_content: bytes) -> List[Dict]:
    """
    Parse an .ics calendar file and extract events
    
    Args:
        file_content: Raw bytes from uploaded calendar file
        
    Returns:
        List of event dictionaries with name, start, end, description
    """
    events = []
    
    try:
        cal = Calendar.from_ical(file_content)
        
        for component in cal.walk():
            if component.name == "VEVENT":
                event = {
                    'name': str(component.get('summary', 'Untitled Event')),
                    'start': component.get('dtstart').dt if component.get('dtstart') else None,
                    'end': component.get('dtend').dt if component.get('dtend') else None,
                    'description': str(component.get('description', '')),
                    'location': str(component.get('location', '')),
                }
                
                # Convert date to datetime if needed
                if isinstance(event['start'], datetime):
                    event['start'] = event['start']
                else:
                    # If it's a date object, convert to datetime at midnight
                    from datetime import time
                    event['start'] = datetime.combine(event['start'], time())
                    
                if event['end'] and not isinstance(event['end'], datetime):
                    from datetime import time
                    event['end'] = datetime.combine(event['end'], time())
                
                events.append(event)
                
    except Exception as e:
        raise ValueError(f"Error parsing calendar file: {str(e)}")
    
    # Sort events by start date
    events.sort(key=lambda x: x['start'] if x['start'] else datetime.max)
    
    return events


def create_sample_calendar() -> bytes:
    """
    Create a sample .ics calendar file for testing
    
    Returns:
        Bytes of sample calendar file
    """
    from datetime import timedelta
    
    cal = Calendar()
    cal.add('prodid', '-//Prophetic Calendar//EN')
    cal.add('version', '2.0')
    
    # Create sample events
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    events_data = [
        {
            'name': 'Team Meeting',
            'days_offset': 5,
            'duration': 2,
            'description': 'Weekly team sync'
        },
        {
            'name': 'Client Presentation',
            'days_offset': 10,
            'duration': 3,
            'description': 'Q4 results presentation'
        },
        {
            'name': 'Conference',
            'days_offset': 15,
            'duration': 8,
            'description': 'Annual tech conference'
        },
        {
            'name': 'Workshop',
            'days_offset': 20,
            'duration': 4,
            'description': 'AI/ML workshop'
        }
    ]
    
    for event_data in events_data:
        from icalendar import Event
        event = Event()
        event.add('summary', event_data['name'])
        event.add('dtstart', base_date + timedelta(days=event_data['days_offset']))
        event.add('dtend', base_date + timedelta(days=event_data['days_offset'], hours=event_data['duration']))
        event.add('description', event_data['description'])
        cal.add_component(event)
    
    return cal.to_ical()
