"""
Timeline simulator for demo purposes
"""
from datetime import datetime, timedelta
from typing import List, Dict


class TimelineSimulator:
    """
    Simulates the passage of time for demo purposes
    """
    
    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.simulated_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def set_demo_mode(self, demo_mode: bool):
        """Enable or disable demo mode"""
        self.demo_mode = demo_mode
        if not demo_mode:
            # Reset to current date when exiting demo mode
            self.simulated_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def get_current_date(self) -> datetime:
        """Get the current date (simulated in demo mode, real otherwise)"""
        if self.demo_mode:
            return self.simulated_date
        else:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def advance_days(self, days: int):
        """
        Advance the simulated timeline by specified days (only works in demo mode)
        
        Args:
            days: Number of days to advance
        """
        if self.demo_mode:
            self.simulated_date += timedelta(days=days)
    
    def set_date(self, date: datetime):
        """
        Set the simulated date to a specific datetime (only works in demo mode)
        
        Args:
            date: Target datetime
        """
        if self.demo_mode:
            self.simulated_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def reset(self):
        """Reset simulator to current real date"""
        self.simulated_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def get_upcoming_events(self, events: List[Dict], days_ahead: int = 30) -> List[Dict]:
        """
        Get events that are upcoming from the current date
        
        Args:
            events: List of event dictionaries
            days_ahead: Number of days ahead to look
            
        Returns:
            List of upcoming events
        """
        current_date = self.get_current_date()
        end_date = current_date + timedelta(days=days_ahead)
        
        upcoming = [
            event for event in events
            if event['start'] >= current_date and event['start'] <= end_date
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
        current_date = self.get_current_date()
        target_date = current_date + timedelta(days=days_before)
        
        # Find events that occur on the target date
        events_needing_alert = []
        for event in events:
            event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
            if event_date == target_date:
                events_needing_alert.append(event)
        
        return events_needing_alert
    
    def days_until_event(self, event: Dict) -> int:
        """
        Calculate days until an event from current date
        
        Args:
            event: Event dictionary
            
        Returns:
            Number of days until event (negative if past)
        """
        current_date = self.get_current_date()
        event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
        delta = event_date - current_date
        return delta.days
