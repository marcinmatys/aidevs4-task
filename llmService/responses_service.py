from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, TypeVar

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from common.logger_config import setup_logger


TResponseModel = TypeVar("TResponseModel", bound=BaseModel)
logger = setup_logger("ResponsesService")


class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    AZURE = "azure"


@dataclass(frozen=True)
class ProviderConfig:
    api_key_env: str
    model_env: str
    default_model: str
    reasoning_effort_env: str | None = "RESPONSES_REASONING_EFFORT"
    temperature_env: str | None = "RESPONSES_TEMPERATURE"
    default_base_url: str | None = None
    base_url_env: str | None = None


@dataclass(frozen=True)
class ResponsesServiceConfig:
    model: str | None = None
    reasoning_effort: str | None = None
    temperature: float | None = None


class ResponsesService:
    """Provider-aware wrapper over OpenAI Responses API with JSON schema output."""

    _LOG_INPUT_ENV = "RESPONSES_LOG_INPUT"
    _LOG_SCHEMA_ENV = "RESPONSES_LOG_SCHEMA"
    _LOG_REQUEST_PARAMS_ENV = "RESPONSES_LOG_REQUEST_PARAMS"
    _LOG_OUTPUT_ENV = "RESPONSES_LOG_OUTPUT"

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

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.OPENROUTER,
        config: ResponsesServiceConfig | None = None,
    ) -> None:
        _ = load_dotenv(find_dotenv())
        self.provider = provider
        self._config = self._PROVIDER_CONFIGS[provider]
        self._service_config = config or ResponsesServiceConfig()

        api_key = os.getenv(self._config.api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing API key in environment variable: {self._config.api_key_env}"
            )

        base_url = self._resolve_base_url()
        self._model = self._resolve_model()
        self._reasoning_effort = self._resolve_reasoning_effort()
        self._temperature = self._resolve_temperature()
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info(
            "Initialized ResponsesService with config:\n%s",
            self._format_json_for_log(
                {
                    "provider": self.provider.value,
                    "base_url": base_url,
                    "model": self._model,
                    "reasoning_effort": self._reasoning_effort,
                    "temperature": self._temperature,
                }
            ),
        )

    @classmethod
    def build(
        cls,
        *,
        provider: LLMProvider | str | None = None,
        config: ResponsesServiceConfig | None = None,
    ) -> ResponsesService:
        resolved_provider = cls.resolve_provider(provider)
        return cls(provider=resolved_provider, config=config)

    @classmethod
    def resolve_provider(cls, provider: LLMProvider | str | None = None) -> LLMProvider:
        if isinstance(provider, LLMProvider):
            return provider

        provider_name = provider or os.getenv("LLM_PROVIDER", LLMProvider.OPENROUTER.value)
        normalized_provider_name = provider_name.strip().lower()

        try:
            return LLMProvider(normalized_provider_name)
        except ValueError as error:
            allowed_values = ", ".join([item.value for item in LLMProvider])
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{normalized_provider_name}'. Allowed: {allowed_values}."
            ) from error

    @property
    def model(self) -> str:
        return self._model

    @property
    def reasoning_effort(self) -> str | None:
        return self._reasoning_effort

    @property
    def temperature(self) -> float | None:
        return self._temperature

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
        output_schema = output_model.model_json_schema()

        if self._is_logging_enabled(self._LOG_INPUT_ENV):
            logger.info(
                "generate_with_schema input:\n%s",
                self._format_json_for_log(
                    {
                        "system_prompt": system_prompt,
                        "input_payload": input_payload,
                    }
                ),
            )

        if self._is_logging_enabled(self._LOG_SCHEMA_ENV):
            logger.info(
                "generate_with_schema output_schema:\n%s",
                self._format_json_for_log(output_schema),
            )

        request_payload: Dict[str, Any] = {
            "model": self._model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": resolved_schema_name,
                    "schema": output_schema,
                    "strict": True,
                }
            },
        }
        self._apply_optional_request_settings(request_payload)
        self._log_request_payload_params(
            operation_name="generate_with_schema",
            request_payload=request_payload,
            excluded_keys={"input", "text"},
        )

        response = self._client.responses.create(
            **request_payload,
        )

        raw_output = getattr(response, "output_text", None)
        if self._is_logging_enabled(self._LOG_OUTPUT_ENV):
            logger.info(
                "generate_with_schema output:\n%s",
                self._format_json_for_log(raw_output),
            )

        if not raw_output:
            raise ValueError("Responses API returned empty output_text.")

        try:
            return output_model.model_validate_json(raw_output)
        except Exception as error:
            raise ValueError(f"Failed to parse Responses API JSON into {output_model.__name__}: {error}") from error

    def generate_with_tools(
        self,
        *,
        messages: list[Dict[str, Any]],
        tools: list[Dict[str, Any]],
    ) -> Any:
        """Single Responses API call with tool definitions. Returns raw response object."""
        if self._is_logging_enabled(self._LOG_INPUT_ENV):
            logger.info(
                "generate_with_tools input:\n%s",
                self._format_json_for_log(messages),
            )

        request_payload: Dict[str, Any] = {
            "model": self._model,
            "input": messages,
            "tools": tools,
        }
        self._apply_optional_request_settings(request_payload)
        self._log_request_payload_params(
            operation_name="generate_with_tools",
            request_payload=request_payload,
            excluded_keys={"input", "tools"},
        )

        response = self._client.responses.create(
            **request_payload,
        )

        if self._is_logging_enabled(self._LOG_OUTPUT_ENV):
            logger.info(
                "generate_with_tools output:\n%s",
                self._format_json_for_log(response.model_dump()),
            )
        return response

    @staticmethod
    def _format_json_for_log(value: Any) -> str:
        if isinstance(value, str):
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                return value
            return json.dumps(parsed_value, ensure_ascii=False, indent=2, sort_keys=True)

        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    @staticmethod
    def _is_logging_enabled(env_name: str) -> bool:
        env_value = os.getenv(env_name, "").strip().lower()
        return env_value in {"1", "true", "yes", "on"}

    def _log_request_payload_params(
        self,
        *,
        operation_name: str,
        request_payload: Dict[str, Any],
        excluded_keys: set[str],
    ) -> None:
        if not self._is_logging_enabled(self._LOG_REQUEST_PARAMS_ENV):
            return

        filtered_request_payload = {
            key: value for key, value in request_payload.items() if key not in excluded_keys
        }
        if not filtered_request_payload:
            return

        logger.info(
            "%s request_payload params:\n%s",
            operation_name,
            self._format_json_for_log(filtered_request_payload),
        )

    def _resolve_base_url(self) -> str | None:
        if not self._config.base_url_env:
            return self._config.default_base_url

        return os.getenv(self._config.base_url_env, self._config.default_base_url)

    def _resolve_model(self) -> str:
        configured_model = self._service_config.model
        if configured_model and configured_model.strip():
            return configured_model.strip()

        env_model = os.getenv(self._config.model_env, "").strip()
        if env_model:
            return env_model

        return self._config.default_model

    def _resolve_reasoning_effort(self) -> str | None:
        configured_reasoning_effort = self._service_config.reasoning_effort
        if configured_reasoning_effort and configured_reasoning_effort.strip():
            return configured_reasoning_effort.strip()

        if self._config.reasoning_effort_env:
            env_reasoning_effort = os.getenv(self._config.reasoning_effort_env, "").strip()
            if env_reasoning_effort:
                return env_reasoning_effort

        return None

    def _resolve_temperature(self) -> float | None:
        if self._service_config.temperature is not None:
            return self._service_config.temperature

        if self._config.temperature_env:
            env_temperature = os.getenv(self._config.temperature_env, "").strip()
            if env_temperature:
                try:
                    return float(env_temperature)
                except ValueError as error:
                    raise ValueError(
                        f"Invalid float value in environment variable {self._config.temperature_env}: {env_temperature}"
                    ) from error

        return None

    def _apply_optional_request_settings(self, request_payload: Dict[str, Any]) -> None:
        if self._reasoning_effort:
            request_payload["reasoning"] = {"effort": self._reasoning_effort}

        if self._temperature is not None and self._allows_temperature():
            request_payload["temperature"] = self._temperature

    def _allows_temperature(self) -> bool:
        return self._reasoning_effort is None or self._reasoning_effort.lower() == "none"
