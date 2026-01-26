"""Web scraper / issue checker using Gemini or mock data."""
import asyncio
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv

from .prophetic_logger import log_info, log_error, log_event, log_llm_call


class WebScraper:
    """Identify potential travel/location issues for events."""

    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.use_mock = self.api_key is None
        self._cache: Dict[str, List[Dict[str, str]]] = {}

        if not self.use_mock:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.llm = genai.GenerativeModel(self.model_name)
                log_info(f"WebScraper initialized with Gemini API (model: {self.model_name})")
            except Exception as e:
                log_info(f"WebScraper using mock mode. {e}")
                self.use_mock = True
        else:
            log_info("WebScraper initialized in mock mode (no API key)")

    def check_for_issues(self, event: Dict) -> List[Dict[str, str]]:
        log_event('issue_check', event.get('name', 'Unknown Event'), {
            'location': event.get('location', 'N/A'),
            'date': event.get('start').isoformat() if event.get('start') else 'N/A',
            'mode': 'mock' if self.use_mock else 'api'
        })

        location = event.get('location', '') or ''
        start_dt = event.get('start')
        date_key = start_dt.strftime('%Y-%m-%d') if start_dt else 'N/A'
        transport = (event.get('transport_mode') or 'na').lower()
        arrival = event.get('arrival_time') or 'na'
        departure = event.get('departure_time') or 'na'
        cache_key = f"{location}|{date_key}|{transport}|{arrival}|{departure}"

        if cache_key in self._cache:
            log_info(f"Issue check cache hit for {cache_key}")
            return self._cache[cache_key]

        if self.use_mock:
            issues = self._check_for_issues_mock(event)
            self._cache[cache_key] = issues
            return issues

        try:
            issues = asyncio.run(self._check_for_issues_api(event))
            self._cache[cache_key] = issues
            return issues
        except Exception as e:
            log_error("Error using API for issue check", e)
            issues = self._check_for_issues_mock(event)
            self._cache[cache_key] = issues
            return issues

    async def _check_for_issues_api(self, event: Dict) -> List[Dict[str, str]]:
        issues: List[Dict[str, str]] = []
        location = event.get('location', '')
        event_date = event['start']

        if not location:
            return issues

        try:
            transport = event.get('transport_mode', 'unknown')
            arrival = event.get('arrival_time', '')
            departure = event.get('departure_time', '')
            event_time = event_date.strftime('%H:%M') if event_date.hour or event_date.minute else 'all day'

            search_query = f"""Check conditions for {location} on {event_date.strftime('%b %d, %Y')} around {event_time}.

Traveler plan:
- Transport: {transport}
- Arrival time: {arrival or 'N/A'}
- Departure time: {departure or 'N/A'}

ONLY report ACTIONABLE concerns relevant to the plan:
- If transport is car: major traffic delays, closures, parking disruptions
- If transport is train/bus: service changes, strikes, delays
- Weather that impacts travel (heavy rain, storms, extreme heat/cold)
- Major holidays or large events causing congestion
- SOCCER/FOOTBALL games at nearby stadiums (within 5km) around the same time that could cause traffic/parking issues
  * For Haifa area: check Sammy Ofer Stadium
  * For Tel Aviv area: check Bloomfield Stadium
  * For Jerusalem area: check Teddy Stadium
  * For Be'er Sheva: check Turner Stadium
  * For Netanya: check Netanya Stadium

DO NOT report:
- Normal/good weather or typical traffic
- Generic statements without specifics
- Games at distant stadiums or very different times

If no significant concerns, respond exactly with: No significant concerns
Otherwise, list 1-3 brief alerts (max 12 words each)."""

            response = await asyncio.to_thread(self.llm.generate_content, search_query)
            result_text = getattr(response, 'text', '') or str(response)

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

            if result_text.strip() and 'no significant concerns' not in result_text.lower():
                lines = [line.strip() for line in result_text.strip().split('\n') if line.strip()]

                for line in lines[:3]:
                    line = line.lstrip('0123456789.-) ')

                    if line and len(line) > 10:
                        issues.append({
                            'type': 'ai_forecast',
                            'severity': 'info',
                            'message': line[:100],
                            'details': f"Plan: {transport} | Arrive: {arrival or 'N/A'} | Depart: {departure or 'N/A'}"
                        })

                if not issues:
                    log_info(f"No significant issues found for {location} on {event_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            log_error("Error in Gemini issue search", e)

        return issues

    def _check_for_issues_mock(self, event: Dict) -> List[Dict[str, str]]:
        issues = []
        issues.extend(self._check_weather_mock(event))

        if event.get('location'):
            issues.extend(self._check_traffic_mock(event))
            issues.extend(self._check_location_issues_mock(event))

        return issues

    def _check_weather_mock(self, event: Dict) -> List[Dict[str, str]]:
        issues = []
        event_date = event['start']
        days_until = (event_date - datetime.now()).days

        if days_until <= 7:
            if random.random() > 0.7:
                issues.append({
                    'type': 'weather',
                    'severity': 'warning',
                    'message': f"🌧️ Rain expected {event_date.strftime('%b %d')} - bring umbrella",
                    'details': f"Weather forecast shows possible rain on {event_date.strftime('%Y-%m-%d')}. Consider bringing an umbrella and waterproof shoes."
                })

        return issues

    def _check_traffic_mock(self, event: Dict) -> List[Dict[str, str]]:
        issues = []

        if random.random() > 0.6:
            issues.append({
                'type': 'traffic',
                'severity': 'info',
                'message': f"🚗 Heavy traffic near {event.get('location')} - leave 30min early",
                'details': f"Heavy traffic expected near {event.get('location')} during typical commute hours. Consider leaving 30 minutes earlier than planned."
            })

        event_date = event['start']
        if event_date.weekday() >= 5:
            if random.random() > 0.8:
                issues.append({
                    'type': 'transit',
                    'severity': 'info',
                    'message': "🚌 Weekend transit schedule - check route ahead",
                    'details': "Weekend transit schedule may differ from weekdays. Please check your route in advance and allow extra time."
                })

        return issues

    def _check_location_issues_mock(self, event: Dict) -> List[Dict[str, str]]:
        issues = []

        if random.random() > 0.75:
            issues.append({
                'type': 'location',
                'severity': 'warning',
                'message': f"🚧 Construction near {event.get('location')} - plan route",
                'details': f"There may be construction or road work near {event.get('location')}. Plan your route accordingly and allow extra time."
            })

        if random.random() > 0.8:
            issues.append({
                'type': 'location',
                'severity': 'info',
                'message': f"🏟️ Large event nearby - limited parking",
                'details': f"Large event scheduled near {event.get('location')} on the same day. Parking may be limited. Consider public transit or arrive early."
            })

        return issues

    def get_travel_time_estimate(self, origin: str, destination: str, arrival_time: str) -> Dict:
        base_time = random.randint(15, 60)
        return {
            'estimated_duration_minutes': base_time,
            'with_traffic_minutes': base_time + random.randint(0, 20),
            'suggested_departure': f"Depart approximately {base_time + 15} minutes before {arrival_time}"
        }