"""
Hiccup Detection Agent: Uses ReAct (Reasoning + Acting) to check for travel issues.
Equipped with web search and Google Maps directions tools.
"""
from typing import Optional, List, Dict, Any
import json
import google.generativeai as genai
from src.prophetic_logger import log_llm_call, log_error, log_info

# Major Israeli stadiums that cause significant traffic/parking disruption during events
ISRAELI_STADIUMS = {
    "Sammy Ofer Stadium": {"city": "Haifa", "address": "Sammy Ofer Stadium, Haifa, Israel", "lat": 32.7940, "lon": 35.0420, "teams": ["Maccabi Haifa", "Hapoel Haifa"]},
    "Bloomfield Stadium": {"city": "Tel Aviv-Jaffa", "address": "Bloomfield Stadium, Tel Aviv, Israel", "lat": 32.0558, "lon": 34.7644, "teams": ["Hapoel Tel Aviv", "Maccabi Tel Aviv", "Bnei Yehuda"]},
    "Teddy Stadium": {"city": "Jerusalem", "address": "Teddy Stadium, Jerusalem, Israel", "lat": 31.7513, "lon": 35.1903, "teams": ["Beitar Jerusalem", "Hapoel Jerusalem"]},
    "Turner Stadium": {"city": "Beer Sheva", "address": "Turner Stadium, Beer Sheva, Israel", "lat": 31.2644, "lon": 34.7914, "teams": ["Hapoel Beer Sheva"]},
    "Netanya Stadium": {"city": "Netanya", "address": "Netanya Stadium, Netanya, Israel", "lat": 32.3215, "lon": 34.8530, "teams": ["Maccabi Netanya", "Hapoel Netanya"]},
    "HaMoshava Stadium": {"city": "Petah Tikva", "address": "HaMoshava Stadium, Petah Tikva, Israel", "lat": 32.0893, "lon": 34.8878, "teams": ["Hapoel Petah Tikva", "Maccabi Petah Tikva"]},
    "Doha Stadium": {"city": "Haifa", "address": "Doha Stadium, Haifa, Israel", "lat": 32.7895, "lon": 35.0095, "teams": ["Hapoel Haifa"]},
    "Ramat Gan Stadium": {"city": "Ramat Gan", "address": "Ramat Gan Stadium, Ramat Gan, Israel", "lat": 32.0927, "lon": 34.8156, "teams": ["Israel National Team"]},
}

# Approximate distance threshold in km for stadium proximity alerts
STADIUM_PROXIMITY_KM = 8.0


class HiccupAgent:
    """
    ReAct agent that reasons about potential travel hiccups and uses tools to verify.
    
    Tools available:
    - web_search: Search the web for current information (events, road closures)
    - maps_directions: Get Google Maps directions and traffic info
    - weather_forecast: Get weather forecast from WeatherAPI.com
    - check_stadium_proximity: Check if event location is near Israeli stadiums
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        self.action_history: List[Dict[str, Any]] = []
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
    
    def check_for_hiccups(
        self,
        event: dict,
        max_iterations: int = 7
    ) -> List[Dict[str, str]]:
        """
        Use ReAct loop to check for potential travel hiccups.
        
        Args:
            event: Event dict with name, location, start, transportation_method, etc.
            max_iterations: Max reasoning-action cycles
        
        Returns:
            List of issue dicts with message, severity, details, source
        """
        if not self.model:
            log_info("Hiccup agent: no API key, returning empty issues")
            return []
        
        # Reset action history for new event
        self.action_history = []
        
        # Extract event details
        event_name = event.get('name', 'Unknown')
        location = event.get('location', '')
        start_dt = event.get('start')
        transport = event.get('transportation_method', 'unknown')
        arrival_time = event.get('arrival_time', '')
        event_end_time = event.get('event_end_time', '')
        departure_location = event.get('departure_location', '')
        
        if not location or not start_dt:
            return []
        
        date_str = start_dt.strftime('%B %d, %Y')
        day_of_week = start_dt.strftime('%A')
        
        # Build context for agent - use arrival_time and event_end_time only (no raw start time)
        context = f"""Event: {event_name}
Location: {location}
Date: {date_str} ({day_of_week})
Arrival time: {arrival_time or 'Not specified'}
Event ends: {event_end_time or 'Not specified'}
Transportation: {transport}
Departure from: {departure_location or 'Not specified'}"""
        
        log_info(f"Hiccup agent: starting ReAct loop for {event_name}")
        
        # ReAct loop
        for iteration in range(max_iterations):
            thought_action = self._reason_and_act(context, iteration, max_iterations)
            
            if thought_action['action'] == 'FINISH':
                # Agent is done reasoning
                issues = thought_action.get('issues', [])
                log_info(f"Hiccup agent: finished after {iteration + 1} iterations with {len(issues)} issues")
                return issues
            
            # Execute the action (use tool)
            observation = self._execute_action(thought_action, event)
            
            # Add to history
            self.action_history.append({
                'iteration': iteration + 1,
                'thought': thought_action.get('thought', ''),
                'action': thought_action['action'],
                'action_input': thought_action.get('action_input', ''),
                'observation': observation
            })
            
            # Update context with observation
            context += f"\n\nObservation {iteration + 1}: {observation}"
        
        # Max iterations reached, extract issues from final state
        log_info(f"Hiccup agent: max iterations reached, extracting final issues")
        return self._extract_final_issues()
    
    def _reason_and_act(self, context: str, iteration: int, max_iterations: int) -> Dict[str, Any]:
        """Let the LLM reason about what to do next and choose an action."""
        
        # Build history summary
        history_text = ""
        if self.action_history:
            history_text = "\n\nPrevious Actions:\n"
            for action in self.action_history:
                history_text += f"- {action['action']}: {action['action_input']}\n"
                history_text += f"  Result: {action['observation']}\n"
        
        prompt = f"""You are a travel hiccup detection agent. Your job is to identify potential issues that could affect someone's ability to attend an event.

{context}{history_text}

Available tools:
1. web_search(query: str) - Search the web for current information (events, road closures, etc.). Requires a search query as action_input. Do NOT use this for weather - use weather_forecast instead.
2. maps_directions() - Get Google Maps directions and check for traffic/delays. Uses the event's departure location, destination, and arrival time automatically - no action_input needed.
3. check_stadium_proximity() - Check if the event location is near any major Israeli stadium. Uses the event location automatically - no action_input needed. Returns nearby stadiums and their home teams. USE THIS FIRST to determine if stadium-related searches are needed.
4. weather_forecast() - Get accurate weather forecast for the event location and date from WeatherAPI.com. Uses the event location and date automatically - no action_input needed. Returns temperature, rain/snow chance, wind, precipitation, hourly forecast around arrival time, and weather alerts. ALWAYS use this for weather checks instead of web_search.
5. FINISH(issues: list) - When you have gathered enough information, finish and return the list of issues

Chain of Thought Instructions:
1. FIRST use check_stadium_proximity to check if any major stadiums are nearby
2. Use weather_forecast to get accurate weather data for the event date - NEVER use web_search for weather
3. If stadiums are found nearby, use web_search to look for specific games/events at those stadiums on the event date
4. Use web_search for road closures near the event location and date
5. Use maps_directions if you need to verify travel time or traffic conditions
6. After 2-4 checks, make a decision and FINISH
7. When confident OR if checks show normal conditions, use FINISH with your findings

Focus on:
- Weather conditions that affect travel
- Traffic delays or road closures (search specifically: "road closures [city] [date]" or "סגירת כבישים [city]")
- Major events at NEARBY STADIUMS (soccer/football games) - use check_stadium_proximity first, then search for specific games by team name and date
- Public transit disruptions (if using public transport)
- Parking availability issues (less important if user walks)

IMPORTANT: If a major event you find (soccer game, concert, etc.) appears to BE the user's event (same location, same time, similar name), do NOT report it as a hiccup - the user already knows they're attending that event. Only report EXTERNAL events that could interfere with travel.

Note: If user transportation is "walking" or "foot", only alert about severe weather or safety issues - parking and traffic are not relevant.

Message Framing - Use LOSS FRAMING (what the user will lose/miss):
- NOT: "Heavy rain expected" → YES: "You'll arrive soaked without rain gear"
- NOT: "Traffic delays likely" → YES: "Traffic could cost you 30 minutes of the meeting"
- NOT: "Parking unavailable" → YES: "You may waste 20 minutes searching for parking"
- NOT: "Road closure on Route 1" → YES: "Route 1 closure will add 15 minutes to your trip"
Frame as personal consequences the user will experience, not neutral facts.

Respond in JSON format:
{{
    "thought": "reasoning about what to check next or why finishing",
    "action": "web_search|maps_directions|check_stadium_proximity|weather_forecast|FINISH",
    "action_input": "the query or parameters for the tool",
    "issues": [] // only if action is FINISH
}}

Example responses:
{{
    "thought": "First, I should check if any major stadiums are near the event location",
    "action": "check_stadium_proximity",
    "action_input": ""
}}

{{
    "thought": "Bloomfield Stadium is 1.2km away. I need to check if Hapoel Tel Aviv or Maccabi Tel Aviv have a game on the event date",
    "action": "web_search",
    "action_input": "Hapoel Tel Aviv Maccabi Tel Aviv game February 2 2026"
}}

{{
    "thought": "Need to check weather conditions for the event date",
    "action": "weather_forecast",
    "action_input": ""
}}

{{
    "thought": "Need to check for road closures near the event location",
    "action": "web_search",
    "action_input": "road closures Tel Aviv February 2 2026"
}}

{{
    "thought": "Have confirmed no major issues, traffic is normal, weather is clear",
    "action": "FINISH",
    "issues": []
}}

{{
    "thought": "Found heavy rain and soccer game causing traffic - these are significant issues",
    "action": "FINISH",
    "issues": [
        {{"message": "Heavy rain expected", "severity": "warning", "details": "80% chance of rain during event time", "source": "weather"}},
        {{"message": "Soccer game at nearby stadium causing traffic delays", "severity": "critical", "details": "Major game at 15:00 near event location", "source": "local_events"}}
    ]
}}

{{
    "thought": "Found a soccer game but it's at the SAME location/time as user's event - this IS the user's event, not an external hiccup. No other issues found.",
    "action": "FINISH",
    "issues": []
}}

Now reason about this event (iteration {iteration + 1}/{max_iterations}):
IMPORTANT: You are on iteration {iteration + 1} of {max_iterations}. After a few checks, make a decision and FINISH."""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Log the reasoning call
            log_llm_call(
                model=self.model_name,
                prompt=prompt,
                response=response_text,
                input_tokens=getattr(getattr(response, 'usage_metadata', None), 'prompt_token_count', None),
                output_tokens=getattr(getattr(response, 'usage_metadata', None), 'candidates_token_count', None),
                metadata={'agent': 'hiccup_react', 'iteration': iteration + 1, 'event_name': context.split('\n')[0].replace('Event: ', '')}
            )
            
            # Extract JSON - be aggressive about finding it
            text = response_text
            
            # Try to extract JSON from markdown code blocks
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                # Extract from generic code block, but verify it contains JSON
                parts = text.split('```')
                if len(parts) >= 3:
                    code_block = parts[1].strip()
                    # Only use code block if it looks like JSON (starts with {)
                    if code_block.startswith('{'):
                        text = code_block
                    # Otherwise, check if JSON exists after the code block
                    elif '{' in parts[2]:
                        text = parts[2]
            
            # Find JSON object boundaries
            if '{' in text:
                start = text.index('{')
                # Find matching closing brace
                brace_count = 0
                end = start
                for i in range(start, len(text)):
                    if text[i] == '{':
                        brace_count += 1
                    elif text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                text = text[start:end]
            
            thought_action = json.loads(text)
            return thought_action
            
        except Exception as e:
            log_error(f"Hiccup agent reasoning error: {e}")
            # Only log response_text if it was successfully retrieved
            try:
                if 'response_text' in locals():
                    log_error(f"Raw response was: {response_text[:500]}")
                elif 'response' in locals():
                    log_error(f"Response object exists but text extraction failed")
                else:
                    log_error(f"Failed to generate content from model")
            except:
                pass  # Don't let logging errors cascade
            # Fallback: finish with no issues
            return {"action": "FINISH", "thought": f"Error in reasoning: {str(e)}", "issues": []}
    
    def _execute_action(self, thought_action: Dict[str, Any], event: dict) -> str:
        """Execute the chosen action using the appropriate tool."""
        action = thought_action['action']
        action_input = thought_action.get('action_input', '')
        
        if action == 'web_search':
            return self._tool_web_search(action_input)
        elif action == 'maps_directions':
            return self._tool_maps_directions(action_input, event)
        elif action == 'check_stadium_proximity':
            return self._tool_check_stadium_proximity(event)
        elif action == 'weather_forecast':
            return self._tool_weather_forecast(event)
        else:
            return "Unknown action"
    
    def _tool_web_search(self, query: str) -> str:
        """Tool: Perform web search using Tavily API."""
        log_info(f"Hiccup agent: web_search tool called with query: {query}")
        
        # Get Tavily API key from environment or session state
        import os
        from dotenv import load_dotenv
        load_dotenv()
        tavily_key = os.getenv('TAVILY_API_KEY')
        
        if not tavily_key:
            log_info("No Tavily API key, using mock search")
            return f"Mock search: No significant issues found for '{query}'"
        
        try:
            import requests
            response = requests.post(
                'https://api.tavily.com/search',
                json={
                    'api_key': tavily_key,
                    'query': query,
                    'max_results': 3
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    summary = "Search results: "
                    for idx, result in enumerate(results[:3], 1):
                        summary += f"{idx}. {result.get('title', 'N/A')}: {result.get('content', 'N/A')[:100]}... "
                    return summary
                else:
                    return "No relevant results found"
            else:
                log_error(f"Tavily API error: {response.status_code}")
                return f"Search API error: {response.status_code}"
                
        except Exception as e:
            log_error(f"Web search error: {e}")
            return f"Search failed: {str(e)}"
    
    def _tool_maps_directions(self, action_input: str, event: dict) -> str:
        """Tool: Get Google Maps directions and traffic info using SerpAPI."""
        log_info(f"Hiccup agent: maps_directions tool called with input: {action_input}")
        
        origin = event.get('departure_location', '')
        destination = event.get('location', '')
        arrival_time = event.get('arrival_time', '')
        
        if not origin or not destination:
            return "Missing origin or destination for directions"
        
        # Get SerpAPI key
        import os
        from dotenv import load_dotenv
        load_dotenv()
        serpapi_key = os.getenv('SERPAPI_KEY')
        
        if not serpapi_key:
            log_info("No SerpAPI key, using mock directions")
            return f"Mock directions: Route from {origin} to {destination} takes approximately 30-40 minutes with normal traffic"
        
        try:
            import requests
            params = {
                'api_key': serpapi_key,
                'engine': 'google_maps_directions',
                'start_addr': origin,
                'end_addr': destination,
                'departure_time': 'now'  # Could use event time for better accuracy
            }
            
            response = requests.get(
                'https://serpapi.com/search',
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                directions = data.get('directions', [])
                
                if directions:
                    # Get first route
                    route = directions[0]
                    duration = route.get('duration', 'Unknown')
                    distance = route.get('distance', 'Unknown')
                    traffic_info = route.get('traffic_info', 'No traffic data')
                    
                    # Format duration - convert seconds to readable format if numeric
                    duration_str = str(duration)
                    try:
                        # If duration is in seconds (as integer), convert to minutes
                        if isinstance(duration, (int, float)):
                            minutes = int(duration) // 60
                            seconds = int(duration) % 60
                            duration_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
                        elif duration.isdigit():
                            minutes = int(duration) // 60
                            seconds = int(duration) % 60
                            duration_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
                    except (ValueError, AttributeError):
                        pass  # Keep original format if can't parse
                    
                    summary = f"Route: {distance}, Duration: {duration_str}"
                    
                    # Only report traffic if there's an actual issue
                    # Check if traffic_info contains problem keywords
                    traffic_info = route.get('traffic_info', None)
                    if traffic_info and any(keyword in str(traffic_info).lower() 
                                           for keyword in ['delay', 'heavy', 'slow', 'congestion', 'jam', 'accident', 'closure']):
                        summary += f" - ⚠️ {traffic_info}"
                    else:
                        # No traffic issues detected - duration is normal
                        summary += " - No delays"
                    
                    return summary
                else:
                    return "No route found between origin and destination"
            else:
                log_error(f"SerpAPI error: {response.status_code}")
                return f"Maps API error: {response.status_code}"
                
        except Exception as e:
            log_error(f"Maps directions error: {e}")
            return f"Directions lookup failed: {str(e)}"
    
    def _tool_weather_forecast(self, event: dict) -> str:
        """Tool: Get weather forecast for the event location and date using WeatherAPI.com."""
        location = event.get('location', '')
        start_dt = event.get('start')
        arrival_time = event.get('arrival_time', '')
        
        log_info(f"Hiccup agent: weather_forecast tool called for {location} on {start_dt}")
        
        if not location or not start_dt:
            return "Missing location or date for weather forecast"
        
        import os
        from dotenv import load_dotenv
        load_dotenv()
        weather_key = os.getenv('OPEN_WEATHER')
        
        if not weather_key:
            log_info("No WeatherAPI key, falling back to web search for weather")
            return "Weather API key not configured. Use web_search to check weather instead."
        
        try:
            import requests
            from datetime import datetime, timedelta
            
            event_date = start_dt.date() if hasattr(start_dt, 'date') else start_dt
            today = datetime.now().date()
            days_ahead = (event_date - today).days
            
            # Choose the right API endpoint based on how far ahead the event is
            if days_ahead < 0:
                return "Event date is in the past, weather forecast not applicable."
            elif days_ahead <= 14:
                # Use forecast API (up to 14 days)
                url = 'http://api.weatherapi.com/v1/forecast.json'
                params = {
                    'key': weather_key,
                    'q': location,
                    'days': min(days_ahead + 1, 14),
                    'alerts': 'yes',
                }
            elif days_ahead <= 300:
                # Use future API (14-300 days ahead)
                url = 'http://api.weatherapi.com/v1/future.json'
                params = {
                    'key': weather_key,
                    'q': location,
                    'dt': event_date.strftime('%Y-%m-%d'),
                }
            else:
                return f"Event is {days_ahead} days away - too far for weather forecast (max 300 days)."
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                log_error(f"WeatherAPI error: {error_msg}")
                return f"Weather API error: {error_msg}. Use web_search as fallback."
            
            data = response.json()
            forecast_days = data.get('forecast', {}).get('forecastday', [])
            
            # Find the forecast for the event date
            target_date_str = event_date.strftime('%Y-%m-%d')
            event_forecast = None
            for fd in forecast_days:
                if fd.get('date') == target_date_str:
                    event_forecast = fd
                    break
            
            if not event_forecast:
                # Use the last available day if exact date not found
                if forecast_days:
                    event_forecast = forecast_days[-1]
                else:
                    return "No forecast data available for the event date."
            
            # Extract day summary
            day = event_forecast.get('day', {})
            condition = day.get('condition', {}).get('text', 'Unknown')
            max_temp = day.get('maxtemp_c', 'N/A')
            min_temp = day.get('mintemp_c', 'N/A')
            rain_chance = day.get('daily_chance_of_rain', 0)
            snow_chance = day.get('daily_chance_of_snow', 0)
            max_wind = day.get('maxwind_kph', 0)
            total_precip = day.get('totalprecip_mm', 0)
            avg_humidity = day.get('avghumidity', 'N/A')
            
            summary = f"🌤️ Weather for {location} on {target_date_str}:\n"
            summary += f"Condition: {condition}\n"
            summary += f"Temperature: {min_temp}°C - {max_temp}°C\n"
            summary += f"Rain chance: {rain_chance}%\n"
            if snow_chance > 0:
                summary += f"Snow chance: {snow_chance}%\n"
            summary += f"Max wind: {max_wind} km/h\n"
            summary += f"Total precipitation: {total_precip} mm\n"
            summary += f"Humidity: {avg_humidity}%\n"
            
            # Extract hourly forecast around arrival time if available
            hours = event_forecast.get('hour', [])
            if hours and arrival_time:
                try:
                    arrival_hour = int(arrival_time.split(':')[0])
                    # Show weather for 2 hours before through arrival
                    relevant_hours = [h for h in hours if arrival_hour - 2 <= int(h['time'].split(' ')[1].split(':')[0]) <= arrival_hour + 1]
                    if relevant_hours:
                        summary += f"\nHourly forecast around arrival ({arrival_time}):\n"
                        for h in relevant_hours:
                            h_time = h['time'].split(' ')[1]
                            h_cond = h.get('condition', {}).get('text', '')
                            h_temp = h.get('temp_c', '')
                            h_rain = h.get('chance_of_rain', 0)
                            h_wind = h.get('wind_kph', 0)
                            summary += f"  {h_time}: {h_cond}, {h_temp}°C, rain {h_rain}%, wind {h_wind}km/h\n"
                except (ValueError, IndexError):
                    pass  # Skip hourly if arrival_time can't be parsed
            
            # Check weather alerts
            alerts = data.get('alerts', {}).get('alert', [])
            if alerts:
                summary += f"\n⚠️ WEATHER ALERTS ({len(alerts)}):\n"
                for alert in alerts[:3]:  # Limit to 3 alerts
                    headline = alert.get('headline', 'Unknown alert')
                    severity = alert.get('severity', 'Unknown')
                    event_type = alert.get('event', '')
                    summary += f"  - [{severity}] {headline}\n"
                    if event_type:
                        summary += f"    Event: {event_type}\n"
            
            return summary
            
        except Exception as e:
            log_error(f"Weather forecast error: {e}")
            return f"Weather forecast failed: {str(e)}. Use web_search as fallback."
    
    def _tool_check_stadium_proximity(self, event: dict) -> str:
        """Tool: Check if event location is near any major Israeli stadium using SerpAPI Google Maps."""
        location = event.get('location', '')
        log_info(f"Hiccup agent: check_stadium_proximity tool called for location: {location}")
        
        if not location:
            return "No event location provided for proximity check"
        
        import os
        from dotenv import load_dotenv
        load_dotenv()
        serpapi_key = os.getenv('SERPAPI_KEY')
        
        if not serpapi_key:
            # Fallback: simple city-name matching
            return self._check_stadium_proximity_fallback(location)
        
        try:
            import requests
            
            # First, geocode the event location using SerpAPI Google Maps
            params = {
                'api_key': serpapi_key,
                'engine': 'google_maps',
                'q': location,
                'type': 'search',
                'hl': 'en',
            }
            
            response = requests.get(
                'https://serpapi.com/search',
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                log_error(f"SerpAPI geocode error: {response.status_code}")
                return self._check_stadium_proximity_fallback(location)
            
            data = response.json()
            local_results = data.get('local_results', [])
            
            # Try to get coordinates from local results or place results
            event_lat, event_lon = None, None
            
            if local_results:
                coords = local_results[0].get('gps_coordinates', {})
                event_lat = coords.get('latitude')
                event_lon = coords.get('longitude')
            
            # Also check place_results for single-result queries
            place_results = data.get('place_results', {})
            if not event_lat and place_results:
                coords = place_results.get('gps_coordinates', {})
                event_lat = coords.get('latitude')
                event_lon = coords.get('longitude')
            
            if not event_lat or not event_lon:
                log_info("Could not geocode event location, using city-name fallback")
                return self._check_stadium_proximity_fallback(location)
            
            # Special case: Haifa events should always check both Haifa stadiums
            # (Sammy Ofer and Doha) since games significantly affect city-wide traffic
            location_lower = location.lower()
            haifa_keywords = ['haifa', 'haïfa', 'heifa', 'heyfa', 'heiffa', 'חיפה']
            is_haifa_location = any(kw in location_lower for kw in haifa_keywords)
            
            # Calculate distances to all stadiums using Haversine formula
            nearby_stadiums = []
            import math
            
            for stadium_name, stadium_info in ISRAELI_STADIUMS.items():
                dist = self._haversine_distance(
                    event_lat, event_lon,
                    stadium_info['lat'], stadium_info['lon']
                )
                # Include stadium if within threshold OR if this is a Haifa event and it's a Haifa stadium
                is_haifa_stadium = stadium_info['city'] in ['Haifa', 'חיפה']
                should_include = dist <= STADIUM_PROXIMITY_KM or (is_haifa_location and is_haifa_stadium)
                
                if should_include:
                    nearby_stadiums.append({
                        'name': stadium_name,
                        'city': stadium_info['city'],
                        'distance_km': round(dist, 1),
                        'teams': stadium_info['teams']
                    })
            
            if not nearby_stadiums:
                return f"No major stadiums found within {STADIUM_PROXIMITY_KM}km of {location}. No stadium-related traffic concerns."
            
            # Format results
            result = f"⚠️ Found {len(nearby_stadiums)} stadium(s) near {location}:\n"
            for s in nearby_stadiums:
                teams_str = ', '.join(s['teams'])
                result += f"- {s['name']} ({s['city']}) - {s['distance_km']}km away. Home teams: {teams_str}\n"
            result += "\nYou SHOULD now search for games at these stadiums on the event date. "
            result += "Use web_search with query like: '[team name] game [date]' or '[stadium name] event [date]'."
            result += "\nAlso search for road closures near the event location."
            return result
            
        except Exception as e:
            log_error(f"Stadium proximity check error: {e}")
            return self._check_stadium_proximity_fallback(location)
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the distance between two GPS coordinates in kilometers."""
        import math
        R = 6371  # Earth's radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    def _check_stadium_proximity_fallback(self, location: str) -> str:
        """Fallback: check stadium proximity by matching city names in the location string."""
        location_lower = location.lower()
        nearby = []
        
        for stadium_name, info in ISRAELI_STADIUMS.items():
            city_lower = info['city'].lower()
            if city_lower in location_lower:
                nearby.append({
                    'name': stadium_name,
                    'city': info['city'],
                    'teams': info['teams']
                })
        
        if not nearby:
            return f"No major stadiums identified near '{location}' (city-name fallback). No stadium-related traffic concerns."
        
        result = f"Found {len(nearby)} stadium(s) in the same city as the event (city-name match):\n"
        for s in nearby:
            teams_str = ', '.join(s['teams'])
            result += f"- {s['name']} ({s['city']}). Home teams: {teams_str}\n"
        result += "\nYou SHOULD now search for games at these stadiums on the event date."
        return result
    
    def _extract_final_issues(self) -> List[Dict[str, str]]:
        """Extract issues from action history when max iterations reached.
        
        Intelligently parse observations to find actual issues:
        - Soccer/football games at nearby stadiums
        - Weather problems (rain, storms, extreme conditions)
        - Road closures or traffic issues
        - Specific events that could impact travel
        """
        issues = []
        
        # Parse observations for specific patterns
        for action in self.action_history:
            observation = action.get('observation', '')
            obs_lower = observation.lower()
            
            # 1. Check for stadium/game findings
            if 'stadium' in obs_lower and any(indicator in obs_lower for indicator in ['game', 'match', 'vs', 'football', 'soccer', 'fc']):
                # Extract game details
                game_details = observation[:500]  # Get more context
                
                # Look for specific patterns like "Team A vs Team B", "8:15 PM", dates
                import re
                
                # Try to find game info
                if 'sammy ofer' in obs_lower or 'bloomfield' in obs_lower or 'teddy stadium' in obs_lower:
                    # Found a stadium mentioned with game context
                    severity = 'warning'
                    
                    # Check if it's same day/time concern
                    if any(time_word in obs_lower for time_word in ['8:15', '20:15', 'same day', 'evening', 'sunday', 'saturday']):
                        severity = 'critical'
                    
                    issues.append({
                        'message': 'A major soccer game at nearby stadium could cause traffic delays and parking issues',
                        'severity': severity,
                        'details': game_details,
                        'source': 'local_events'
                    })
            
            # 2. Check for weather issues (but more specific)
            weather_problems = {
                'heavy rain': 'warning',
                'storm': 'warning', 
                'severe weather': 'critical',
                'flood': 'critical',
                'snow': 'warning',
                'extreme': 'warning',
                'weather alert': 'warning'
            }
            for weather_term, sev in weather_problems.items():
                if weather_term in obs_lower:
                    # Extract weather forecast details
                    weather_details = observation[:300]
                    
                    # Try to find temperature, rain %, etc.
                    issues.append({
                        'message': f'Weather conditions may impact your travel',
                        'severity': sev,
                        'details': weather_details,
                        'source': 'weather'
                    })
                    break  # Only add one weather issue
            
            # 3. Check for road closures
            if 'road closure' in obs_lower or 'lane closure' in obs_lower or 'סגירת כביש' in obs_lower:
                issues.append({
                    'message': 'Road closures reported in the area',
                    'severity': 'warning',
                    'details': observation[:300],
                    'source': 'traffic'
                })
            
            # 4. Check for traffic arrangements (often mentioned with games)
            if 'traffic arrangement' in obs_lower or 'traffic delay' in obs_lower:
                if not any(issue['source'] == 'local_events' for issue in issues):
                    # Only add if we haven't already caught the game
                    issues.append({
                        'message': 'Traffic arrangements or delays expected in the area',
                        'severity': 'info',
                        'details': observation[:300],
                        'source': 'traffic'
                    })
        
        # Deduplicate similar issues
        seen_sources = set()
        deduplicated = []
        for issue in issues:
            key = (issue['source'], issue['severity'])
            if key not in seen_sources:
                seen_sources.add(key)
                deduplicated.append(issue)
        
        log_info(f"Hiccup agent: extracted {len(deduplicated)} issues from observations after max iterations")
        return deduplicated[:3]  # Limit to top 3 issues
