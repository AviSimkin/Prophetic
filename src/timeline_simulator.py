"""Simulate timeline movement for demo mode."""
from datetime import datetime, timedelta
from typing import List, Dict


class TimelineSimulator:
    """Simulates the passage of time for demo purposes."""

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.simulated_date = datetime.now()

    def set_demo_mode(self, demo_mode: bool):
        self.demo_mode = demo_mode
        if not demo_mode:
            self.simulated_date = datetime.now()

    def get_current_date(self) -> datetime:
        if self.demo_mode:
            return self.simulated_date
        return datetime.now()

    def advance_days(self, days: int):
        if self.demo_mode:
            self.simulated_date += timedelta(days=days)

    def advance_hours(self, hours: int):
        if self.demo_mode:
            self.simulated_date += timedelta(hours=hours)

    def advance_minutes(self, minutes: int):
        if self.demo_mode:
            self.simulated_date += timedelta(minutes=minutes)

    def set_time(self, hour: int, minute: int, second: int = 0):
        if self.demo_mode:
            self.simulated_date = self.simulated_date.replace(
                hour=hour, minute=minute, second=second, microsecond=0
            )

    def set_date(self, date: datetime):
        if self.demo_mode:
            self.simulated_date = date

    def reset(self):
        self.simulated_date = datetime.now()

    def get_upcoming_events(self, events: List[Dict], days_ahead: int = 30) -> List[Dict]:
        current_date = self.get_current_date()
        end_date = current_date + timedelta(days=days_ahead)
        upcoming = [
            event for event in events
            if event['start'] >= current_date and event['start'] <= end_date
        ]
        return sorted(upcoming, key=lambda x: x['start'])

    def get_events_needing_alert(self, events: List[Dict], days_before: int) -> List[Dict]:
        current_date = self.get_current_date()
        target_date = current_date + timedelta(days=days_before)

        events_needing_alert = []
        for event in events:
            event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
            if event_date == target_date:
                events_needing_alert.append(event)

        return events_needing_alert

    def days_until_event(self, event: Dict) -> int:
        current_date = self.get_current_date()
        event_date = event['start'].replace(hour=0, minute=0, second=0, microsecond=0)
        delta = event_date - current_date
        return delta.days