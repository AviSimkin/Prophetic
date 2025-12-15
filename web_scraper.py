"""
Web scraper module for checking potential issues/hiccups for events
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime


class WebScraper:
    """
    Module for scraping the web to identify potential issues for events using browseruse
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize WebScraper with optional Gemini API key
        
        Args:
            api_key: Google Gemini API key (optional, will use mock mode if not provided)
        """
        self.api_key = api_key
        self.use_mock = api_key is None
        
        if not self.use_mock:
            try:
                import google.generativeai as genai
                from browseruse import Agent
                
                genai.configure(api_key=api_key)
                self.llm = genai.GenerativeModel('gemini-2.0-flash-exp')
                self.agent = Agent(
                    task="Search for potential issues related to events",
                    llm=self.llm
                )
            except Exception as e:
                print(f"Warning: Could not initialize browseruse agent: {e}")
                self.use_mock = True
    
    def check_for_issues(self, event: Dict) -> List[Dict[str, str]]:
        """
        Check for potential issues related to an event
        
        Args:
            event: Event dictionary with location and timing details
            
        Returns:
            List of potential issues/alerts
        """
        if self.use_mock:
            return self._check_for_issues_mock(event)
        
        # Use browseruse to search for real issues
        try:
            return asyncio.run(self._check_for_issues_browseruse(event))
        except Exception as e:
            print(f"Error using browseruse: {e}")
            return self._check_for_issues_mock(event)
    
    async def _check_for_issues_browseruse(self, event: Dict) -> List[Dict[str, str]]:
        """
        Use browseruse with Gemini to search for real issues
        """
        issues = []
        location = event.get('location', '')
        event_date = event['start']
        
        if not location:
            return issues
        
        try:
            # Create search tasks for the agent
            search_query = f"""
            Search for potential issues for an event at {location} on {event_date.strftime('%Y-%m-%d')}:
            1. Check weather forecast
            2. Check traffic conditions and road closures
            3. Check for major events or construction in the area
            
            Summarize any potential issues found.
            """
            
            result = await self.agent.run(search_query)
            
            # Parse the result and extract issues
            if result and len(result) > 0:
                issues.append({
                    'type': 'browseruse_search',
                    'severity': 'info',
                    'message': result
                })
        except Exception as e:
            print(f"Error in browseruse search: {e}")
        
        return issues
    
    def _check_for_issues_mock(self, event: Dict) -> List[Dict[str, str]]:
        """
        Mock implementation for checking issues (used when no API key provided)
        """
        import random
        
        issues = []
        
        # Check weather-related issues
        weather_issues = self._check_weather_mock(event)
        issues.extend(weather_issues)
        
        # Check traffic/transit issues
        if event.get('location'):
            traffic_issues = self._check_traffic_mock(event)
            issues.extend(traffic_issues)
        
        # Check location-specific issues
        if event.get('location'):
            location_issues = self._check_location_issues_mock(event)
            issues.extend(location_issues)
        
        return issues
    
    def _check_weather_mock(self, event: Dict) -> List[Dict[str, str]]:
        """
        Check for weather-related issues (mock implementation)
        
        In a production system, this would call a weather API
        """
        import random
        issues = []
        
        event_date = event['start']
        days_until = (event_date - datetime.now()).days
        
        if days_until <= 7:
            # Simulate finding weather issues occasionally
            if random.random() > 0.7:
                issues.append({
                    'type': 'weather',
                    'severity': 'warning',
                    'message': f"Weather forecast shows possible rain on {event_date.strftime('%Y-%m-%d')}. Consider bringing an umbrella."
                })
        
        return issues
    
    def _check_traffic_mock(self, event: Dict) -> List[Dict[str, str]]:
        """
        Check for traffic or transit issues (mock implementation)
        
        In production, would use Google Maps API, Waze API, or transit APIs
        """
        import random
        issues = []
        
        location = event.get('location', '').lower()
        event_date = event['start']
        
        # Mock traffic check
        if random.random() > 0.6:
            issues.append({
                'type': 'traffic',
                'severity': 'info',
                'message': f"Heavy traffic expected near {event.get('location')} during typical commute hours. Consider leaving 30 minutes earlier."
            })
        
        # Check if it's a weekend
        if event_date.weekday() >= 5:  # Saturday or Sunday
            if random.random() > 0.8:
                issues.append({
                    'type': 'transit',
                    'severity': 'info',
                    'message': "Weekend transit schedule may be different. Please check your route in advance."
                })
        
        return issues
    
    def _check_location_issues_mock(self, event: Dict) -> List[Dict[str, str]]:
        """
        Check for location-specific issues (mock implementation)
        
        In production, would check for:
        - Construction/road closures
        - Local events that might cause congestion
        - Venue-specific alerts
        """
        import random
        issues = []
        
        location = event.get('location', '').lower()
        
        # Mock location checks
        
        # Simulate finding construction/closure info
        if random.random() > 0.75:
            issues.append({
                'type': 'location',
                'severity': 'warning',
                'message': f"There may be construction or road work near {event.get('location')}. Plan your route accordingly."
            })
        
        # Simulate finding nearby events
        if random.random() > 0.8:
            issues.append({
                'type': 'location',
                'severity': 'info',
                'message': f"Large event scheduled near {event.get('location')} on the same day. Parking may be limited."
            })
        
        return issues
    
    def get_travel_time_estimate(self, origin: str, destination: str, arrival_time: str) -> Dict:
        """
        Estimate travel time between locations (mock implementation)
        
        Args:
            origin: Starting location
            destination: Destination location
            arrival_time: Desired arrival time
            
        Returns:
            Dictionary with travel estimates
        """
        import random
        # Mock travel time estimation
        # In production, would use Google Maps Distance Matrix API or similar
        
        base_time = random.randint(15, 60)
        
        return {
            'estimated_duration_minutes': base_time,
            'with_traffic_minutes': base_time + random.randint(0, 20),
            'suggested_departure': f"Depart approximately {base_time + 15} minutes before {arrival_time}"
        }
