"""LLM helpers for collecting event details."""
import os
import re
from typing import Dict, Optional

from dotenv import load_dotenv

from .prophetic_logger import log_llm_call, log_info, log_error


class LLMModule:
    """Generate questions and parse responses for event details."""

    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.use_mock = self.api_key is None

        if not self.use_mock:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
                self.client = genai.GenerativeModel(self.model_name)
                log_info(f"LLM Module initialized with Gemini API (model: {self.model_name})")
            except Exception as e:
                log_error("Could not initialize Gemini client, using mock mode", e)
                self.use_mock = True
        else:
            log_info("LLM Module initialized in mock mode (no API key)")

    def generate_questions(self, event: Dict) -> Dict[str, str]:
        questions = {}

        if not event.get('location') or event['location'] == '':
            questions['location'] = f"Where is '{event['name']}' taking place?"

        if not event.get('arrival_time'):
            questions['arrival_time'] = f"What time do you need to arrive for '{event['name']}'?"

        if not event.get('departure_time'):
            questions['departure_time'] = f"What time do you plan to leave for '{event['name']}'?"

        return questions

    def parse_response(self, response: str, question_type: str) -> str:
        response = response.strip()

        if question_type in ['arrival_time', 'departure_time']:
            time_pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
            if not re.match(time_pattern, response):
                if ':' not in response and len(response) in [3, 4]:
                    if len(response) == 3:
                        response = f"{response[0]}:{response[1:3]}"
                    else:
                        response = f"{response[0:2]}:{response[2:4]}"
                else:
                    raise ValueError("Invalid time format. Please use HH:MM format (e.g., 09:30 or 14:30)")

        return response

    def get_contextual_prompt(self, event: Dict, missing_info: list) -> str:
        if self.use_mock:
            return self._get_mock_prompt(event, missing_info)

        try:
            field = missing_info[0].replace('_', ' ')
            prompt = f"Ask a brief, friendly question about {field} for the event '{event['name']}' on {event['start'].strftime('%b %d')}. Max 15 words."

            response = self.client.generate_content(prompt)
            response_text = response.text.strip()

            usage = getattr(response, 'usage_metadata', None)
            input_tokens = getattr(usage, 'prompt_token_count', None) if usage else None
            output_tokens = getattr(usage, 'candidates_token_count', None) if usage else None

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
        field = missing_info[0] if missing_info else 'information'
        return f"Please provide {field.replace('_', ' ')} for '{event['name']}'"