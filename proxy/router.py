import os
from config.model_map import model_mapper
from provider.openrouter.adapter import OpenRouterProvider
from provider.deepseekplatform.adapter import DeepSeekProvider
from provider.base import BaseProvider

class ProviderRouter:
    def _resolve_custom_direct(self, requested_model: str):
        """If requested_model is like 'myprovider/some-model' and myprovider is a custom provider,
        bypass ModelMapper and resolve directly. This lets custom providers be used without a mapping entry."""
        if "/" not in requested_model:
            return None
        maybe_provider, maybe_model = requested_model.split("/", 1)
        try:
            from config.custom_providers import load_custom_providers
            if maybe_provider in load_custom_providers():
                return maybe_provider, maybe_model
        except Exception:
            pass
        return None

    def get_provider(self, requested_model: str) -> BaseProvider:
        direct = self._resolve_custom_direct(requested_model)
        if direct is not None:
            provider_name, target_model = direct
        else:
            provider_name, target_model = model_mapper.resolve(requested_model)

        if provider_name == "openrouter":
            return OpenRouterProvider(target_model=target_model)
        elif provider_name == "deepseekplatform":
            return DeepSeekProvider(target_model=target_model)

        try:
            from config.custom_providers import load_custom_providers, get_api_key_for_provider
            from provider.custom.adapter import GenericOpenAIProvider, GenericAnthropicProvider
            spec = load_custom_providers().get(provider_name)
            if spec:
                env_name = spec.get("api_key_env", "")
                api_key = get_api_key_for_provider(spec) if env_name else ""
                if not api_key:
                    raise ValueError(
                        f"Missing ENV {env_name} for provider '{provider_name}' — set it in .env or environment (add {env_name}=sk-... to .env and restart the proxy)"
                    )
                headers = spec.get("headers") or None
                base_url = spec.get("base_url", "")
                if spec.get("provider_api") == "anthropic":
                    return GenericAnthropicProvider(
                        target_model=target_model, base_url=base_url, api_key=api_key, extra_headers=headers
                    )
                return GenericOpenAIProvider(
                    target_model=target_model, base_url=base_url, api_key=api_key, extra_headers=headers
                )
        except ValueError:
            raise
        except Exception:
            pass

        raise ValueError(f"Unknown provider '{provider_name}'")

provider_router = ProviderRouter()
