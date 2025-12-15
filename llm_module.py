"""
LLM module for collecting event details from users
"""
from typing import Dict, Optional
import json
import re


class LLMModule:
    """
    Module for generating questions and processing user responses about events
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM module
        
        Args:
            api_key: OpenAI API key (optional, will use mock mode if not provided)
        """
        self.api_key = api_key
        self.use_mock = api_key is None
        
        if not self.use_mock:
            try:
                import openai
                self.client = openai.OpenAI(api_key=api_key)
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
                self.use_mock = True
    
    def generate_questions(self, event: Dict) -> Dict[str, str]:
        """
        Generate questions to collect missing event information
        
        Args:
            event: Event dictionary
            
        Returns:
            Dictionary of questions for missing fields
        """
        questions = {}
        
        # Check what information is missing
        if not event.get('location') or event['location'] == '':
            questions['location'] = f"Where will the event '{event['name']}' take place?"
        
        if not event.get('arrival_time'):
            questions['arrival_time'] = f"What time do you need to arrive for '{event['name']}'? (HH:MM format)"
        
        if not event.get('departure_time'):
            questions['departure_time'] = f"What time do you plan to depart for '{event['name']}'? (HH:MM format)"
        
        return questions
    
    def parse_response(self, response: str, question_type: str) -> str:
        """
        Parse and validate user response
        
        Args:
            response: User's response
            question_type: Type of question (location, arrival_time, departure_time)
            
        Returns:
            Parsed and validated response
        """
        response = response.strip()
        
        if question_type in ['arrival_time', 'departure_time']:
            # Basic time validation
            time_pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
            if not re.match(time_pattern, response):
                # Try to fix common formats
                if ':' not in response and len(response) in [3, 4]:
                    # e.g., "930" -> "9:30", "1430" -> "14:30"
                    if len(response) == 3:
                        response = f"{response[0]}:{response[1:3]}"
                    else:
                        response = f"{response[0:2]}:{response[2:4]}"
                else:
                    raise ValueError(f"Invalid time format. Please use HH:MM format (e.g., 09:30 or 14:30)")
        
        return response
    
    def get_contextual_prompt(self, event: Dict, missing_info: list) -> str:
        """
        Generate a contextual prompt for collecting information
        
        Args:
            event: Event dictionary
            missing_info: List of missing information fields
            
        Returns:
            Prompt string
        """
        if self.use_mock:
            return self._get_mock_prompt(event, missing_info)
        
        # Generate AI-powered prompt
        try:
            event_details = f"""
Event: {event['name']}
Date: {event['start'].strftime('%Y-%m-%d %H:%M')}
Description: {event.get('description', 'N/A')}
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that asks clear, concise questions to gather event details."},
                    {"role": "user", "content": f"Generate a friendly question to ask the user about their {missing_info[0]} for this event:\n{event_details}"}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating AI prompt: {e}")
            return self._get_mock_prompt(event, missing_info)
    
    def _get_mock_prompt(self, event: Dict, missing_info: list) -> str:
        """Generate a mock prompt without AI"""
        field = missing_info[0] if missing_info else 'information'
        return f"Please provide {field.replace('_', ' ')} for '{event['name']}'"
