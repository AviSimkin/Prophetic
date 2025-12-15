"""
LLM module for collecting event details from users
"""
import os
import re
import json
from typing import Dict, Optional

from dotenv import load_dotenv
from prophetic_logger import log_llm_call, log_info, log_error


class LLMModule:
    """
    Module for generating questions and processing user responses about events
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM module
        
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
                self.client = genai.GenerativeModel(self.model_name)
                log_info(f"LLM Module initialized with Gemini API (model: {self.model_name})")
            except Exception as e:
                log_error("Could not initialize Gemini client, using mock mode", e)
                self.use_mock = True
        else:
            log_info("LLM Module initialized in mock mode (no API key)")
    
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
        
        # Generate AI-powered prompt using Gemini
        try:
            event_details = f"""
Event: {event['name']}
Date: {event['start'].strftime('%Y-%m-%d %H:%M')}
Description: {event.get('description', 'N/A')}
"""
            
            prompt = f"You are a helpful assistant that asks clear, concise questions to gather event details. Generate a friendly question to ask the user about their {missing_info[0]} for this event:\n{event_details}"
            
            response = self.client.generate_content(prompt)
            response_text = response.text.strip()
            
            # Log the LLM call with token usage if available
            input_tokens = getattr(response, 'usage_metadata', {}).get('prompt_token_count', None) if hasattr(response, 'usage_metadata') else None
            output_tokens = getattr(response, 'usage_metadata', {}).get('candidates_token_count', None) if hasattr(response, 'usage_metadata') else None
            
            log_llm_call(
                model=self.model_name,
                prompt=prompt,
                response=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata={
                    'purpose': 'contextual_prompt',
                    'event': event.get('name'),
                    'field': missing_info[0] if missing_info else 'unknown'
                }
            )
            
            return response_text
        except Exception as e:
            log_error("Error generating AI prompt", e)
            return self._get_mock_prompt(event, missing_info)
    
    def _get_mock_prompt(self, event: Dict, missing_info: list) -> str:
        """Generate a mock prompt without AI"""
        field = missing_info[0] if missing_info else 'information'
        return f"Please provide {field.replace('_', ' ')} for '{event['name']}'"
