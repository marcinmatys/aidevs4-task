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

    def run(self, user_message: str = "Execute the task.") -> str:
        """Run the agent loop until a text response or iteration limit is reached."""
        messages: list[Dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(1, self._max_iterations + 1):
            logger.info("=== Agent iteration %d / %d ===", iteration, self._max_iterations)

            response = self._service.generate_with_tools(
                messages=messages,
                tools=self._tools,
            )

            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]

            if not function_calls:
                final_text = self._extract_text_output(response)
                logger.info("Agent finished with text response: %s", final_text[:500])
                return final_text

            # Execute each tool call and append results to messages
            # First, append all function_call items to messages so the model sees them
            for fc in function_calls:
                messages.append(fc)

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

                messages.append({
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": result,
                })

        logger.warning("Agent reached max iterations (%d) without finishing.", self._max_iterations)
        return "Agent reached maximum iterations without producing a final answer."

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
