from config.model_map import model_mapper
from provider.openrouter.adapter import OpenRouterProvider
from provider.deepseekplatform.adapter import DeepSeekProvider
from provider.base import BaseProvider

class ProviderRouter:
    def get_provider(self, requested_model: str) -> BaseProvider:
        provider_name, target_model = model_mapper.resolve(requested_model)
        
        if provider_name == "openrouter":
            return OpenRouterProvider(target_model=target_model)
        elif provider_name == "deepseekplatform":
            return DeepSeekProvider(target_model=target_model)
        else:
            raise ValueError(f"Unknown provider '{provider_name}'")

provider_router = ProviderRouter()
