"""
Timeline simulator for demo purposes
"""
from datetime import datetime, timedelta
from typing import List, Dict


class TimelineSimulator:
    """
    Simulates the passage of time for demo purposes
    """
    
    def __init__(self):
        self.simulated_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def get_current_date(self) -> datetime:
        """Get the current simulated date"""
        return self.simulated_date
    
    def advance_days(self, days: int):
        """
        Advance the simulated timeline by specified days
        
        Args:
            days: Number of days to advance
        """
        self.simulated_date += timedelta(days=days)
    
    def set_date(self, date: datetime):
        """
        Set the simulated date to a specific datetime
        
        Args:
            date: Target datetime
        """
        self.simulated_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def reset(self):
        """Reset simulator to current real date"""
        self.simulated_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def get_upcoming_events(self, events: List[Dict], days_ahead: int = 30) -> List[Dict]:
        """
        Get events that are upcoming from the simulated current date
        
        Args:
            events: List of event dictionaries
            days_ahead: Number of days ahead to look
            
        Returns:
            List of upcoming events
        """
        end_date = self.simulated_date + timedelta(days=days_ahead)
        
        upcoming = [
            event for event in events
            if event['start'] >= self.simulated_date and event['start'] <= end_date
        ]
        
        return sorted(upcoming, key=lambda x: x['start'])
    
    def get_events_needing_alert(self, events: List[Dict], days_before: int) -> List[Dict]:
        """
        Get events that need alerts (e.g., 7 days or 1 day before)
        
        Args:
            events: List of event dictionaries
            days_before: Number of days before event to alert
            
        Returns:
            List of events that need alerts
        """
        target_date = self.simulated_date + timedelta(days=days_before)
        
        # Find events that occur on the target date
        events_needing_alert = []
        for event in events:
            event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
            if event_date == target_date:
                events_needing_alert.append(event)
        
        return events_needing_alert
    
    def days_until_event(self, event: Dict) -> int:
        """
        Calculate days until an event from simulated current date
        
        Args:
            event: Event dictionary
            
        Returns:
            Number of days until event (negative if past)
        """
        event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
        delta = event_date - self.simulated_date
        return delta.days
