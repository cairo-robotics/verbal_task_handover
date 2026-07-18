import os
import sys
import datetime
from pathlib import Path

def get_log_file() -> str:
    log_file = os.environ.get("EXPERIMENT_LOG_FILE")
    if not log_file:
        raise RuntimeError("EXPERIMENT_LOG_FILE environment variable is required.")
    return log_file

def log_message(message: str) -> None:
    log_path = get_log_file()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def log_api_call(provider: str, model: str, kwargs: dict) -> None:
    # Log details of the API call, removing large prompts or outputs to keep it concise,
    # but logging all settings like reasoning settings, base URL, temperature, etc.
    safe_kwargs = {}
    for k, v in kwargs.items():
        if k in ("input", "messages", "prompt", "user_prompt", "system_prompt"):
            # Exclude full prompts but log their structure/size
            if isinstance(v, list):
                safe_kwargs[k] = f"<list of {len(v)} messages>"
            else:
                safe_kwargs[k] = f"<text prompt length {len(str(v))}>"
        else:
            safe_kwargs[k] = v
            
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL") or "default"
    
    log_message(
        f"API Call - Provider: {provider}, Model: {model}, Base URL: {base_url}, Config: {safe_kwargs}"
    )
