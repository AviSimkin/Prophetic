"""
Prophetic logging: structured logs for LLM usage and app events
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class PropheticLogger:
    def __init__(self, log_dir: str = "logs", session_name: Optional[str] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        import os as _os
        import uuid
        
        # Get current timestamp with milliseconds
        now = datetime.now()
        timestamp_ms = now.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # milliseconds (3 digits)
        auto_name = f"{timestamp_ms}-{_os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.session_name = session_name or auto_name

        # Organize logs by day folder
        day_folder = self.log_dir / now.strftime('%Y-%m-%d')
        day_folder.mkdir(exist_ok=True)

        self.general_log_file = day_folder / f"app_{timestamp_ms}.log"
        self.llm_log_file = day_folder / f"llm_{timestamp_ms}.jsonl"
        self.session_log_file = day_folder / f"session_{self.session_name}.json"

        self.logger = logging.getLogger("Prophetic")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler = logging.FileHandler(self.general_log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == str(self.general_log_file) for h in self.logger.handlers):
            self.logger.addHandler(file_handler)
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            self.logger.addHandler(console_handler)

        self.session_data: Dict[str, Any] = {
            "session_start": datetime.now().isoformat(),
            "session_name": self.session_name,
            "llm_calls": [],
            "events": [],
            "total_tokens": {"input": 0, "output": 0, "total": 0},
        }

        self.logger.info("=" * 60)
        self.logger.info("Prophetic Logger initialized")
        self.logger.info(f"Log directory: {self.log_dir.absolute()}")
        self.logger.info(f"Session name: {self.session_name}")

    def log_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        call: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "prompt": prompt,
            "response": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (input_tokens or 0) + (output_tokens or 0),
            "metadata": metadata or {},
        }

        if input_tokens:
            self.session_data["total_tokens"]["input"] += input_tokens
        if output_tokens:
            self.session_data["total_tokens"]["output"] += output_tokens
        if input_tokens or output_tokens:
            self.session_data["total_tokens"]["total"] += (input_tokens or 0) + (output_tokens or 0)

        self.session_data["llm_calls"].append(call)

        with open(self.llm_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(call, ensure_ascii=False) + "\n")

        tokens_str = (
            f"[{input_tokens or '?'} in / {output_tokens or '?'} out]" if (input_tokens is not None or output_tokens is not None) else ""
        )
        purpose = (metadata or {}).get("purpose", "general")
        self.logger.info(f"LLM Call: {model} {tokens_str} - {purpose}")

    def log_event(self, event_type: str, event_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "name": event_name,
            "details": details or {},
        }
        self.session_data["events"].append(event)
        self.logger.info(f"Event: {event_type} - {event_name}")

    def log_info(self, message: str) -> None:
        self.logger.info(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def log_error(self, message: str, error: Optional[Exception] = None) -> None:
        if error:
            self.logger.error(f"{message}: {error}", exc_info=True)
        else:
            self.logger.error(message)

    def save_session(self) -> None:
        self.session_data["session_end"] = datetime.now().isoformat()
        with open(self.session_log_file, "w", encoding="utf-8") as f:
            json.dump(self.session_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Session saved to {self.session_log_file}")

    def get_session_summary(self) -> Dict[str, Any]:
        return {
            "session_start": self.session_data["session_start"],
            "session_name": self.session_name,
            "llm_calls_count": len(self.session_data["llm_calls"]),
            "total_tokens": self.session_data["total_tokens"],
            "events_count": len(self.session_data["events"]),
        }

    def print_summary(self) -> None:
        s = self.get_session_summary()
        self.logger.info("=" * 60)
        self.logger.info("SESSION SUMMARY")
        self.logger.info(f"Start: {s['session_start']}")
        self.logger.info(f"Name: {s['session_name']}")
        self.logger.info(f"LLM Calls: {s['llm_calls_count']}")
        self.logger.info(f"Total Input Tokens: {s['total_tokens']['input']}")
        self.logger.info(f"Total Output Tokens: {s['total_tokens']['output']}")
        self.logger.info(f"Total Tokens: {s['total_tokens']['total']}")
        self.logger.info(f"Events Logged: {s['events_count']}")
        self.logger.info("=" * 60)


_logger_instance: Optional[PropheticLogger] = None


def get_logger(session_name: Optional[str] = None) -> PropheticLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PropheticLogger(session_name=session_name)
    return _logger_instance


def log_llm_call(*args, **kwargs) -> None:
    get_logger().log_llm_call(*args, **kwargs)


def log_event(*args, **kwargs) -> None:
    get_logger().log_event(*args, **kwargs)


def log_info(message: str) -> None:
    get_logger().log_info(message)


def log_warning(message: str) -> None:
    get_logger().log_warning(message)


def log_error(message: str, error: Optional[Exception] = None) -> None:
    get_logger().log_error(message, error)
