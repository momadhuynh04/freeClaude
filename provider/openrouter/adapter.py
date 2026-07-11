from provider.openai_base import OpenAIBaseProvider
from config.settings import settings
from typing import Dict

class OpenRouterProvider(OpenAIBaseProvider):
    def __init__(self, target_model: str):
        super().__init__(
            target_model=target_model,
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = super()._get_headers()
        headers.update({
            "HTTP-Referer": "https://github.com/freeClaude",
            "X-Title": "freeClaude Proxy"
        })
        return headers
