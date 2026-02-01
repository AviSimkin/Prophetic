"""
Hiccup Detection Agent: Uses ReAct (Reasoning + Acting) to check for travel issues.
Equipped with web search and Google Maps directions tools.
"""
from typing import Optional, List, Dict, Any
import json
import google.generativeai as genai
from src.prophetic_logger import log_llm_call, log_error, log_info


class HiccupAgent:
    """
    ReAct agent that reasons about potential travel hiccups and uses tools to verify.
    
    Tools available:
    - web_search: Search the web for current information
    - maps_directions: Get Google Maps directions and traffic info
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
        max_iterations: int = 5
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
        time_str = start_dt.strftime('%H:%M')
        day_of_week = start_dt.strftime('%A')
        
        # Build context for agent - only show arrival_time if different from event start time
        context = f"""Event: {event_name}
Location: {location}
Date: {date_str} ({day_of_week})
Time: {time_str}
Transportation: {transport}
Departure from: {departure_location or 'Not specified'}"""
        
        # Only add arrival time if it differs from event start time
        if arrival_time and arrival_time != time_str:
            context += f"\nArrival time: {arrival_time}"
        
        if event_end_time:
            context += f"\nEvent ends: {event_end_time}"
        
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
1. web_search(query: str) - Search the web for current information (weather, events, closures, etc.)
2. maps_directions(origin: str, destination: str, arrival_time: str) - Get Google Maps directions and check for traffic/delays
3. FINISH(issues: list) - When you have gathered enough information, finish and return the list of issues

Chain of Thought Instructions:
1. THINK about what information you need to verify potential hiccups
2. CHOOSE an action to gather that information (vary your approach - don't just search repeatedly)
3. After getting results, ANALYZE if you have enough information
4. Use DIFFERENT tools for different checks (web_search for events/weather, maps_directions for traffic)
5. After 2-3 checks, make a decision - don't keep searching indefinitely
6. When confident OR if checks show normal conditions, use FINISH with your findings

Focus on:
- Weather conditions that affect travel
- Traffic delays or road closures
- Major events (especially big soccer/football games) NEARBY that cause congestion and parking issues
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
    "action": "web_search|maps_directions|FINISH",
    "action_input": "the query or parameters for the tool",
    "issues": [] // only if action is FINISH
}}

Example responses:
{{
    "thought": "Need to check weather conditions for the event date",
    "action": "web_search",
    "action_input": "weather forecast Tel Aviv February 2 2026"
}}

{{
    "thought": "Need to check for major soccer games nearby on event date",
    "action": "web_search",
    "action_input": "soccer football games February 2 2026 Tel Aviv Haifa Israel stadiums"
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
                text = text.split('```')[1].split('```')[0].strip()
            
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
            log_error(f"Raw response was: {response_text[:500]}")
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
                    if 'traffic' in str(traffic_info).lower() or 'delay' in str(traffic_info).lower():
                        summary += f" - Traffic issues: {traffic_info}"
                    else:
                        summary += " - Normal traffic conditions"
                    
                    return summary
                else:
                    return "No route found between origin and destination"
            else:
                log_error(f"SerpAPI error: {response.status_code}")
                return f"Maps API error: {response.status_code}"
                
        except Exception as e:
            log_error(f"Maps directions error: {e}")
            return f"Directions lookup failed: {str(e)}"
    
    def _extract_final_issues(self) -> List[Dict[str, str]]:
        """Extract issues from action history when max iterations reached."""
        # Look through observations for any mentioned issues
        issues = []
        
        for action in self.action_history:
            observation = action.get('observation', '')
            # Simple heuristic: if observation mentions delays, weather issues, etc.
            if 'delay' in observation.lower() or 'traffic' in observation.lower():
                issues.append({
                    'message': 'Potential traffic delays detected',
                    'severity': 'warning',
                    'details': observation[:100],
                    'source': 'agent_analysis'
                })
            if 'rain' in observation.lower() or 'storm' in observation.lower():
                issues.append({
                    'message': 'Weather concerns',
                    'severity': 'info',
                    'details': observation[:100],
                    'source': 'weather'
                })
        
        return issues[:3]  # Limit to top 3 issues
