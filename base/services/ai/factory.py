from base.models import AISettings

from .mistral import MistralProvider
from .gemini import GeminiProvider

PROVIDERS = {
    "mistral": MistralProvider,
    "gemini": GeminiProvider,
}


def get_provider(settings=None):
    settings = settings or AISettings.load()
    provider_cls = PROVIDERS.get(settings.provider)
    if provider_cls is None:
        return None
    return provider_cls(api_key=settings.api_key, model=settings.model)
