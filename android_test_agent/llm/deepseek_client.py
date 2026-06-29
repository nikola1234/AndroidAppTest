from __future__ import annotations

import inspect
import json
import sys
from time import perf_counter
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
        caller = self._caller()
        payload: dict[str, Any] = {
            "model": self._config.llm_model,
            "temperature": self._config.llm_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        started_at = perf_counter()
        self._log(f"DeepSeek call started: caller={caller}, model={self._config.llm_model}")
        try:
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
        except Exception as exc:
            elapsed = perf_counter() - started_at
            self._log(f"DeepSeek call failed: caller={caller}, elapsed={elapsed:.2f}s, error={exc}")
            raise
        elapsed = perf_counter() - started_at
        self._log(f"DeepSeek call finished: caller={caller}, elapsed={elapsed:.2f}s")
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _log(self, message: str) -> None:
        if self._config.llm_log_calls:
            print(f"[android-test-agent] {message}", file=sys.stderr, flush=True)

    def _caller(self) -> str:
        for frame in inspect.stack()[2:]:
            filename = frame.filename.replace("\\", "/")
            if "/android_test_agent/" not in filename:
                continue
            if filename.endswith("/llm/deepseek_client.py") or filename.endswith("/llm/base.py"):
                continue
            relative = filename.rsplit("/android_test_agent/", maxsplit=1)[-1]
            return f"android_test_agent/{relative}:{frame.function}"
        return "unknown"
