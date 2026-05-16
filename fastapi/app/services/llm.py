import httpx
import json
import os
from typing import Dict, Any, Optional


class LLMClient:
    """Клиент для OpenRouter API."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("LLM_MODEL", "google/gemma-3-27b-it")
        self.max_tokens = 4096
        self.temperature = 0.3
    
    async def generate(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Отправляет запрос к LLM и возвращает результат."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenRouter error: {response.status_code} - {response.text}")
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            # Парсим JSON из ответа
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Если модель вернула текст не в JSON — оборачиваем
                result = {"heading": "", "paragraphs": [content]}
            
            return {
                "content": result,
                "tokens_used": tokens,
            }


# Синглтон
llm_client = LLMClient()
