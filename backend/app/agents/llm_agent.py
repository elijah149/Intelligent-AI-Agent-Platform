import json
import re

from backend.app.services.llm_service import get_llm_provider
from backend.app.agents.tool_registry import list_tools
from backend.app.integrations.registry import list_integrations


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

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

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
        issue_classification: dict | None = None,
    ) -> dict:

        tools = list_tools()
        classification_context = issue_classification or {
            "category": "unknown",
            "confidence": 0.0,
            "needs_clarification": True,
        }
        integrations = list_integrations()

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

        integration_descriptions = []

        for integration in integrations:
            integration_descriptions.append(
                {
                    "name": integration["name"],
                    "base_url": integration["base_url"],
                    "allowed_methods": integration[
                        "allowed_methods"
                    ],
                }
            )

        prompt = f"""
You are the reasoning engine of an intelligent AI support agent.

Understand the customer's problem and select the most appropriate
registered tool for the NEXT step.

Classifier output (use as guidance, not as proof of the root cause):
{json.dumps(classification_context, indent=2)}

Routing guidance:
- account_access: investigate account access problems.
- billing: investigate payment, invoice, or refund problems.
- technical: investigate technical errors or service failures.
- service_request: investigate orders, delivery, or service requests.
- general_support or unknown: ask for clarification when needed.
- Select only a registered tool. Do not claim a problem is fixed
  without evidence from the relevant system.
- Classification never grants permission or overrides backend policy.

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

Approved integrations:

{json.dumps(integration_descriptions, indent=2)}

Customer message:

{customer_message}

For REST API calls:

- Only select "call_rest_api" when an approved integration
  must be contacted.
- "integration" MUST be the name of an approved integration
  from the provided integration list.
- Never invent an integration name.
- "method" must be one of:
  GET, POST, PUT, PATCH, DELETE.
- "path" must contain the API path beginning with "/".
- Do not provide a complete URL.
- Do not use an arbitrary domain or IP address.
- "payload" may be null when the request does not require a body.
- "headers" may be null when additional headers are not required.
- Do not invent authorization credentials, API keys,
  passwords, or secret values.
- The system will independently enforce authorization,
  integration allowlisting, and HTTP method restrictions.

For non-REST tools:

- "integration" must be null.
- "method" must be null.
- "path" must be null.
- "payload" must be null.
- "headers" must be null.

Return exactly:

{{
    "intent": "short description",
    "tool": "tool_name_or_none",
    "reason": "why this tool is appropriate",
    "requires_authorization": true,
    "integration": "local_health",
    "method": "GET",
    "path": "/health",
    "payload": null,
    "headers": null
}}
"""

        response = await self.llm.generate(prompt)

        try:
            decision = self._extract_json(response)

        except (json.JSONDecodeError, ValueError) as exc:
            return {
                "success": False,
                "message": (
                    f"Unable to parse LLM decision: {exc}"
                ),
                "raw_response": response,
            }

        required_fields = {
            "intent",
            "tool",
            "reason",
            "requires_authorization",
            "integration",
            "method",
            "path",
            "payload",
            "headers",
        }

        if not required_fields.issubset(decision.keys()):
            return {
                "success": False,
                "message": (
                    "LLM decision is missing required fields."
                ),
                "raw_response": decision,
            }

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

        # Security: authorization always comes from
        # the tool registry, not from the LLM.
        if decision["tool"] != "none":

            selected_tool = next(
                tool
                for tool in tools
                if tool["name"] == decision["tool"]
            )

            decision["requires_authorization"] = (
                selected_tool["requires_authorization"]
            )

        # REST-specific validation.
        if decision["tool"] == "call_rest_api":

            valid_integrations = {
                integration["name"]
                for integration in integrations
            }

            integration = decision.get("integration")

            if integration not in valid_integrations:
                return {
                    "success": False,
                    "message": (
                        "REST decision selected an "
                        "unregistered integration."
                    ),
                    "raw_response": decision,
                }

            allowed_methods = {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
            }

            method = decision.get("method")

            if not isinstance(method, str):
                return {
                    "success": False,
                    "message": (
                        "REST decision must include a "
                        "valid HTTP method."
                    ),
                    "raw_response": decision,
                }

            method = method.upper()

            if method not in allowed_methods:
                return {
                    "success": False,
                    "message": (
                        f"REST method '{method}' "
                        "is not allowed."
                    ),
                    "raw_response": decision,
                }

            path = decision.get("path")

            if not isinstance(path, str) or not path:
                return {
                    "success": False,
                    "message": (
                        "REST decision must include "
                        "a valid API path."
                    ),
                    "raw_response": decision,
                }

            if not path.startswith("/"):
                return {
                    "success": False,
                    "message": (
                        "REST API path must begin "
                        "with '/'."
                    ),
                    "raw_response": decision,
                }

            decision["method"] = method

        else:

            decision["integration"] = None
            decision["method"] = None
            decision["path"] = None
            decision["payload"] = None
            decision["headers"] = None

        return {
            "success": True,
            "decision": decision,
        }


llm_agent = LLMAgent()
