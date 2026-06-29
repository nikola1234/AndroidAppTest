from __future__ import annotations

import json
from typing import Any

import requests

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.llm.base import LLMClient


class DeepSeekClient(LLMClient):
    """DeepSeek chat completion client using the OpenAI-compatible API."""

    def __init__(self, config: AndroidTestConfig) -> None:
        if not config.llm_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeekClient")
        self._config = config

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._config.llm_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._config.llm_model,
            "temperature": self._config.llm_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._config.llm_api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
