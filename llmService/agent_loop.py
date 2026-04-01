from __future__ import annotations

import json
from typing import Any, Callable, Dict

from common.logger_config import setup_logger
from llmService.responses_service import ResponsesService

logger = setup_logger("AgentLoop")


class AgentLoop:
    """Orchestrates an agentic loop using ResponsesService with tool calling."""

    def __init__(
        self,
        responses_service: ResponsesService,
        tools: list[Dict[str, Any]],
        tool_executor: Callable[[str, Dict[str, Any]], str],
        system_prompt: str,
        max_iterations: int = 15,
    ) -> None:
        self._service = responses_service
        self._tools = tools
        self._tool_executor = tool_executor
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations

    def run(
        self,
        messages: list[Dict[str, Any]] | None = None,
        user_message: str | None = None,
    ) -> Dict[str, Any]:
        conversation_messages = self._build_initial_messages(messages, user_message)
        api_messages = self._with_system_prompt(conversation_messages)

        for iteration in range(1, self._max_iterations + 1):
            logger.info("=== Agent iteration %d / %d ===", iteration, self._max_iterations)

            response = self._service.generate_with_tools(
                messages=api_messages,
                tools=self._tools,
            )

            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]

            if not function_calls:
                final_text = self._extract_text_output(response) or "Agent did not produce a final text response."
                api_messages.append({"role": "assistant", "content": final_text})
                logger.info("Agent finished with text response: %s", final_text[:500])
                return {
                    "messages": self._strip_system_message(api_messages),
                    "assistant_message": final_text,
                }

            # Execute each tool call and append results to messages
            # First, append all function_call items to messages so the model sees them.
            # fc is a ResponseFunctionToolCall SDK object (not a dict) — the Responses API
            # accepts these directly in the input array and serializes them internally.
            # Alternatively, fc can be converted to a plain dict:
            #   {"type": "function_call", "call_id": fc.call_id, "name": fc.name, "arguments": fc.arguments}
            for fc in function_calls:
                api_messages.append({
                    "type": "function_call",
                    "call_id": fc.call_id,
                    "name": fc.name,
                    "arguments": fc.arguments,
                })

            for fc in function_calls:
                tool_name = fc.name
                tool_args = json.loads(fc.arguments)
                logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_args, ensure_ascii=False))

                try:
                    result = self._tool_executor(tool_name, tool_args)
                except Exception as e:
                    result = json.dumps({"error": str(e)}, ensure_ascii=False)
                    logger.error("Tool %s raised an error: %s", tool_name, e)

                logger.info("Tool result: %s", result[:1000] if len(result) > 1000 else result)

                api_messages.append({
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": result,
                })

        logger.warning("Agent reached max iterations (%d) without finishing.", self._max_iterations)
        fallback_message = "Agent reached maximum iterations without producing a final answer."
        api_messages.append({"role": "assistant", "content": fallback_message})
        return {
            "messages": self._strip_system_message(api_messages),
            "assistant_message": fallback_message,
        }

    @staticmethod
    def _build_initial_messages(
        messages: list[Dict[str, Any]] | None,
        user_message: str | None,
    ) -> list[Dict[str, Any]]:
        if messages is not None:
            return [message.copy() for message in messages]

        resolved_user_message = user_message or "Execute the task."
        return [{"role": "user", "content": resolved_user_message}]

    def _with_system_prompt(self, messages: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        if messages and messages[0].get("role") == "system":
            return [message.copy() for message in messages]

        return [{"role": "system", "content": self._system_prompt}, *[message.copy() for message in messages]]

    @staticmethod
    def _strip_system_message(messages: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        if messages and messages[0].get("role") == "system":
            return messages[1:]

        return messages

    @staticmethod
    def _extract_text_output(response: Any) -> str:
        """Extract text content from a Responses API response."""
        text_parts = []
        for item in response.output:
            if item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        text_parts.append(content.text)
        return "\n".join(text_parts) if text_parts else getattr(response, "output_text", "")
