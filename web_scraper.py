"""
Web scraper module for checking potential issues/hiccups for events
"""
import os
import asyncio
import random
from typing import Dict, List, Optional
from datetime import datetime

from dotenv import load_dotenv
from prophetic_logger import log_info, log_error, log_event, log_llm_call


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
        load_dotenv()
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.use_mock = self.api_key is None
        
        if not self.use_mock:
            try:
                import google.generativeai as genai
                
                genai.configure(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.llm = genai.GenerativeModel(self.model_name)
                # browseruse is optional and not currently used
                # self.agent = Agent(task="...", llm=self.llm)
                log_info(f"WebScraper initialized with Gemini API (model: {self.model_name})")
            except Exception as e:
                # Fall back to mock mode if Gemini is unavailable
                log_info(f"WebScraper using mock mode. {e}")
                self.use_mock = True
        else:
            log_info("WebScraper initialized in mock mode (no API key)")
    
    def check_for_issues(self, event: Dict) -> List[Dict[str, str]]:
        """
        Check for potential issues related to an event
        
        Args:
            event: Event dictionary with location and timing details
            
        Returns:
            List of potential issues/alerts
        """
        log_event('issue_check', event.get('name', 'Unknown Event'), {
            'location': event.get('location', 'N/A'),
            'date': event.get('start').isoformat() if event.get('start') else 'N/A',
            'mode': 'mock' if self.use_mock else 'api'
        })
        
        if self.use_mock:
            return self._check_for_issues_mock(event)
        
        # Use Gemini directly to search for issues (no browseruse)
        try:
            return asyncio.run(self._check_for_issues_api(event))
        except Exception as e:
            log_error(f"Error using API for issue check", e)
            return self._check_for_issues_mock(event)
    
    async def _check_for_issues_api(self, event: Dict) -> List[Dict[str, str]]:
        """
        Use Gemini API to search for real issues (no browser automation)
        """
        issues: List[Dict[str, str]] = []
        location = event.get('location', '')
        event_date = event['start']
        
        if not location:
            return issues
        
        try:
            search_query = (
                f"Search for potential issues for an event at {location} on {event_date.strftime('%Y-%m-%d')}:\n"
                "1. Weather forecast (rain, heat, storms)\n"
                "2. Traffic conditions and road closures\n"
                "3. Nearby major events or construction\n\n"
                "Summarize any potential issues in 2-3 bullet points."
            )
            
            # Call Gemini
            response = await asyncio.to_thread(self.llm.generate_content, search_query)
            result_text = getattr(response, 'text', '') or str(response)
            
            # Token usage (if available)
            usage = getattr(response, 'usage_metadata', None)
            input_tokens = getattr(usage, 'prompt_token_count', None) if usage else None
            output_tokens = getattr(usage, 'candidates_token_count', None) if usage else None
            
            log_llm_call(
                model=self.model_name,
                prompt=search_query,
                response=result_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata={
                    'purpose': 'issue_search',
                    'location': location,
                    'date': event_date.isoformat(),
                }
            )
            
            if result_text.strip():
                issues.append({
                    'type': 'gemini_search',
                    'severity': 'info',
                    'message': result_text.strip()
                })
        except Exception as e:
            log_error("Error in Gemini issue search", e)
        
        return issues
    
    def _check_for_issues_mock(self, event: Dict) -> List[Dict[str, str]]:
        """
        Mock implementation for checking issues (used when no API key provided)
        """
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
        # Mock travel time estimation
        # In production, would use Google Maps Distance Matrix API or similar
        
        base_time = random.randint(15, 60)
        
        return {
            'estimated_duration_minutes': base_time,
            'with_traffic_minutes': base_time + random.randint(0, 20),
            'suggested_departure': f"Depart approximately {base_time + 15} minutes before {arrival_time}"
        }
