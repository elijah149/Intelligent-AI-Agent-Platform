import json
import re

from backend.app.services.llm_service import get_llm_provider
from backend.app.agents.tool_registry import list_tools


class LLMAgent:
    """
    LLM-powered reasoning layer.

    The LLM decides which registered tool should be used.
    It does not execute tools directly.
    """

    def __init__(self):
        self.llm = get_llm_provider()

    def _extract_json(self, response: str) -> dict:
        """
        Extract the first JSON object from the LLM response.
        """

        response = response.strip()

        # First try the complete response.
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting a JSON object from surrounding text.
        match = re.search(
            r"\{.*\}",
            response,
            re.DOTALL,
        )

        if not match:
            raise ValueError(
                "No valid JSON object found in LLM response."
            )

        return json.loads(match.group(0))

    async def decide(
        self,
        customer_message: str,
    ) -> dict:
        tools = list_tools()

        tool_descriptions = []

        for tool in tools:
            tool_descriptions.append(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "read_only": tool["read_only"],
                    "requires_authorization": tool[
                        "requires_authorization"
                    ],
                }
            )

        prompt = f"""
You are the reasoning engine of an intelligent AI support agent.

Understand the customer's problem and select the most appropriate
registered tool for the NEXT step.

IMPORTANT:

- Only use tools from the provided tool list.
- Never invent a tool.
- Never execute a tool.
- Never grant yourself authorization.
- If a tool requires authorization, report that requirement.
- Return ONLY a JSON object.
- Do not write explanations before or after the JSON.
- Do not use markdown code fences.

Available tools:

{json.dumps(tool_descriptions, indent=2)}

Customer message:

{customer_message}

Return exactly:

{{
    "intent": "short description",
    "tool": "tool_name_or_none",
    "reason": "why this tool is appropriate",
    "requires_authorization": true
}}
"""

        response = await self.llm.generate(prompt)

        try:
            decision = self._extract_json(response)

        except (json.JSONDecodeError, ValueError) as exc:
            return {
                "success": False,
                "message": f"Unable to parse LLM decision: {exc}",
                "raw_response": response,
            }

        required_fields = {
            "intent",
            "tool",
            "reason",
            "requires_authorization",
        }

        if not required_fields.issubset(decision.keys()):
            return {
                "success": False,
                "message": "LLM decision is missing required fields.",
                "raw_response": decision,
            }

        # Security: only registered tools may be selected.
        valid_tools = {
            tool["name"]
            for tool in tools
        }

        if (
            decision["tool"] != "none"
            and decision["tool"] not in valid_tools
        ):
            return {
                "success": False,
                "message": (
                    f"LLM selected an unregistered tool: "
                    f"{decision['tool']}"
                ),
                "raw_response": decision,
            }

        # Security: authorization must come from the registry,
        # not from the LLM.
        if decision["tool"] != "none":
            selected_tool = next(
                tool
                for tool in tools
                if tool["name"] == decision["tool"]
            )

            decision["requires_authorization"] = (
                selected_tool["requires_authorization"]
            )

        return {
            "success": True,
            "decision": decision,
        }


llm_agent = LLMAgent()
