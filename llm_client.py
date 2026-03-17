from __future__ import annotations

from typing import Any

import requests

from .config import EmploymentConfig


class EmploymentLLMClient:
    def __init__(self, config: EmploymentConfig):
        self.config = config

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        if not self.config.llm_enabled:
            raise RuntimeError("LLM is not configured.")

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            content = "\n".join(parts)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM response content is empty.")
        return content.strip()

    def generate_markdown(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate_text(system_prompt, user_prompt, temperature=0.4)
