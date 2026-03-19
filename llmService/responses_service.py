from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, TypeVar

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from pydantic import BaseModel


TResponseModel = TypeVar("TResponseModel", bound=BaseModel)


class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    AZURE = "azure"


@dataclass(frozen=True)
class ProviderConfig:
    api_key_env: str
    model_env: str
    default_model: str
    default_base_url: str | None = None
    base_url_env: str | None = None


class ResponsesService:
    """Provider-aware wrapper over OpenAI Responses API with JSON schema output."""

    _PROVIDER_CONFIGS: Dict[LLMProvider, ProviderConfig] = {
        LLMProvider.OPENROUTER: ProviderConfig(
            api_key_env="OPENROUTER_API_KEY",
            model_env="OPENROUTER_MODEL",
            default_model="openai/gpt-4o-mini",
            default_base_url="https://openrouter.ai/api/v1",
            base_url_env="OPENROUTER_BASE_URL",
        ),
        LLMProvider.OPENAI: ProviderConfig(
            api_key_env="OPENAI_API_KEY",
            model_env="OPENAI_MODEL",
            default_model="gpt-4o-mini",
        ),
        LLMProvider.AZURE: ProviderConfig(
            api_key_env="AZURE_OPENAI_API_KEY",
            model_env="AZURE_OPENAI_MODEL",
            default_model="gpt-4o-mini",
            default_base_url=None,
            base_url_env="AZURE_OPENAI_BASE_URL",
        ),
    }

    def __init__(self, provider: LLMProvider = LLMProvider.OPENROUTER) -> None:
        _ = load_dotenv(find_dotenv())
        self.provider = provider
        self._config = self._PROVIDER_CONFIGS[provider]

        api_key = os.getenv(self._config.api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing API key in environment variable: {self._config.api_key_env}"
            )

        base_url = self._resolve_base_url()
        self._model = os.getenv(self._config.model_env, self._config.default_model)
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def model(self) -> str:
        return self._model

    def generate_with_schema(
        self,
        *,
        system_prompt: str,
        input_payload: Dict[str, Any],
        output_model: type[TResponseModel],
        schema_name: str | None = None,
    ) -> TResponseModel:
        """Call Responses API and return data validated by the provided Pydantic model."""
        resolved_schema_name = schema_name or output_model.__name__
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": resolved_schema_name,
                    "schema": output_model.model_json_schema(),
                    "strict": True,
                }
            },
        )

        raw_output = getattr(response, "output_text", None)
        if not raw_output:
            raise ValueError("Responses API returned empty output_text.")

        try:
            return output_model.model_validate_json(raw_output)
        except Exception as error:
            raise ValueError(f"Failed to parse Responses API JSON into {output_model.__name__}: {error}") from error

    def _resolve_base_url(self) -> str | None:
        if not self._config.base_url_env:
            return self._config.default_base_url

        return os.getenv(self._config.base_url_env, self._config.default_base_url)
