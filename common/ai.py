from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider

from core.config import config

model = GeminiModel(
    config.common_model.name,
    provider=GoogleGLAProvider(api_key=config.common_model.api_key)
)

