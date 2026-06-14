import requests

from .base import AIProvider


class MistralProvider(AIProvider):
    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def complete(self, system, messages):
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self.API_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
