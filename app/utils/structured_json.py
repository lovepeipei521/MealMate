import json
from typing import Any, Dict
import re

# JSON extraction regex
JSON_BLOCK_RE = re.compile(
    r"```json\s*([\s\S]*?)\s*```", 
    re.IGNORECASE
)
JSON_OBJECT_RE = re.compile(
    r"\{[\s\S]*?\}",
    re.MULTILINE
)

def extract_first_valid_json(content: str) -> Dict[str, Any]:
        """Extract the first valid JSON object from LLM output."""
        # Try to extract from code block first
        for match in JSON_BLOCK_RE.findall(content):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # Try to extract direct JSON object
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object pattern
        for match in JSON_OBJECT_RE.findall(content):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        raise ValueError("No valid JSON found in response")