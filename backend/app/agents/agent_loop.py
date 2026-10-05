import json

from sqlalchemy.orm import Session

from backend.app.agents.llm_agent import llm_agent
from backend.app.agents.tool_executor import execute_tool
from backend.app.agents.tool_registry import list_tools
from backend.app.agents.execution_policy import execution_policy


class AgentLoop:
    """
    Multi-step reasoning and tool execution loop.

    The LLM decides what to do.
    The system validates and executes the decision.
    The result is returned to the LLM for the next decision.
    """

    async def run(
        self,
        db: Session,
        customer_message: str,
        username: str,
        incident_id: int,
        authorized: bool = False,
        max_steps: int = 5,
    ) -> dict:

        history = []

        # Initial reasoning
        decision_result = await llm_agent.decide(
            customer_message
        )

        if not decision_result["success"]:
            return decision_result

        decision = decision_result["decision"]

        for step in range(1, max_steps + 1):

            tool_name = decision["tool"]

            history.append({
                "step": step,
                "decision": decision,
            })

            # No tool selected
            if tool_name == "none":
                return {
                    "success": True,
                    "status": "completed",
                    "history": history,
                }

            # ------------------------------------------------
            # SECURITY: Verify that the selected tool exists
            # ------------------------------------------------

            registered_tools = {
                tool["name"]: tool
                for tool in list_tools()
            }

            if tool_name not in registered_tools:
                return {
                    "success": False,
                    "status": "blocked",
                    "message": (
                        f"Tool '{tool_name}' is not registered."
                    ),
                    "history": history,
                }

            tool = registered_tools[tool_name]

            # ------------------------------------------------
            # Execution Policy
            # ------------------------------------------------

            allowed, policy_message, required_next_tool = (
                execution_policy.can_execute(
                    tool_name=tool_name,
                    history=history,
                    authorized=authorized,
                )
            )

            if not allowed:

                # The policy may require a safe investigation
                # before the requested action can continue.
                if required_next_tool:
                    tool_name = required_next_tool

                    decision = {
                        "intent": "Perform required investigation first",
                        "tool": required_next_tool,
                        "reason": policy_message,
                        "requires_authorization": False,
                    }

                    history[-1]["policy"] = {
                        "blocked_tool": history[-1]["decision"]["tool"],
                        "message": policy_message,
                        "required_next_tool": required_next_tool,
                    }

                    # Continue the loop with the safe investigation tool.
                    continue

                return {
                    "success": True,
                    "status": "policy_blocked",
                    "tool": tool_name,
                    "message": policy_message,
                    "history": history,
                }

            # ------------------------------------------------
            # Authorization boundary
            # ------------------------------------------------

            if (
                tool["requires_authorization"]
                and not authorized
            ):
                return {
                    "success": True,
                    "status": "awaiting_authorization",
                    "tool": tool_name,
                    "message": (
                        f"Authorization is required for "
                        f"'{tool_name}'."
                    ),
                    "history": history,
                }

            # ------------------------------------------------
            # Build parameters
            # ------------------------------------------------

            parameters = {}

            if tool_name == "get_customer_account":
                parameters = {
                    "username": username,
                }

            elif tool_name == "unlock_account":
                parameters = {
                    "username": username,
                    "incident_id": incident_id,
                    "authorized": authorized,
                }

            elif tool_name in {
                "diagnose_incident",
                "verify_incident_resolution",
                "resolve_incident",
                "close_incident",
            }:
                parameters = {
                    "incident_id": incident_id,
                }

            else:
                return {
                    "success": False,
                    "status": "unsupported_tool",
                    "tool": tool_name,
                    "message": (
                        "The selected tool does not yet have "
                        "an execution parameter mapping."
                    ),
                    "history": history,
                }

            # ------------------------------------------------
            # Execute tool
            # ------------------------------------------------

            execution = execute_tool(
                db=db,
                tool_name=tool_name,
                parameters=parameters,
                authorized=authorized,
            )

            history[-1]["execution"] = execution

            if not execution["success"]:
                return {
                    "success": False,
                    "status": "tool_failed",
                    "tool": tool_name,
                    "message": execution["message"],
                    "history": history,
                }

            # ------------------------------------------------
            # Resolution Guard
            # ------------------------------------------------
            #
            # If the investigation confirms that the account
            # is already active, unlocked, and has no failed
            # login attempts, do not allow the LLM to repeat
            # the corrective action.
            #
            # Instead, force the formal verification step.
            # ------------------------------------------------

            if tool_name == "get_customer_account":

                account_result = execution["result"]

                if account_result.get("found"):

                    account = account_result.get("account", {})

                    account_is_recovered = (
                        account.get("status") == "active"
                        and account.get("failed_login_attempts") == 0
                        and account.get("is_locked") is False
                    )

                    if account_is_recovered:

                        verification = execute_tool(
                            db=db,
                            tool_name="verify_incident_resolution",
                            parameters={
                                "incident_id": incident_id,
                            },
                            authorized=authorized,
                        )

                        history.append({
                            "step": step + 1,
                            "decision": {
                                "intent": (
                                    "Verify successful account recovery"
                                ),
                                "tool": "verify_incident_resolution",
                                "reason": (
                                    "The account is active, unlocked, "
                                    "and has zero failed login attempts."
                                ),
                                "requires_authorization": False,
                            },
                            "execution": verification,
                        })

                        if not verification["success"]:
                            return {
                                "success": False,
                                "status": "verification_failed",
                                "tool": "verify_incident_resolution",
                                "message": verification["message"],
                                "history": history,
                            }

                        verification_result = verification["result"]

                        if not verification_result.get("verified"):
                            return {
                                "success": False,
                                "status": "verification_failed",
                                "tool": "verify_incident_resolution",
                                "message": verification_result.get(
                                    "message",
                                    "Account recovery verification failed.",
                                ),
                                "history": history,
                            }

                        resolution = execute_tool(
                            db=db,
                            tool_name="resolve_incident",
                            parameters={
                                "incident_id": incident_id,
                            },
                            authorized=authorized,
                        )

                        history.append({
                            "step": step + 2,
                            "decision": {
                                "intent": "Resolve recovered incident",
                                "tool": "resolve_incident",
                                "reason": (
                                    "Verification confirmed that the "
                                    "account recovery was successful."
                                ),
                                "requires_authorization": False,
                            },
                            "execution": resolution,
                        })

                        if not resolution["success"]:
                            return {
                                "success": False,
                                "status": "resolution_failed",
                                "tool": "resolve_incident",
                                "message": resolution["message"],
                                "history": history,
                            }

                        return {
                            "success": True,
                            "status": "resolved",
                            "incident_id": incident_id,
                            "diagnosis": (
                                "The customer account was successfully "
                                "recovered and verified."
                            ),
                            "verification": verification_result.get(
                                "message",
                                "Account recovery successfully verified.",
                            ),
                            "resolution": resolution["result"].get(
                                "message",
                                "Incident successfully resolved.",
                            ),
                            "history": history,
                        }

            # ------------------------------------------------
            # Feed result back to LLM
            # ------------------------------------------------

            result = execution["result"]

            follow_up_message = f"""
Original customer message:
{customer_message}

Username:
{username}

The system executed this tool:

{tool_name}

Tool result:

{json.dumps(result, indent=2)}

Based on the actual tool result, decide the NEXT step.

Available tools:

{json.dumps(list_tools(), indent=2)}

Remember:

- Do not invent tools.
- Do not execute tools yourself.
- Choose only one next tool.
- If authorization is required, report it.
- If the problem is resolved, choose "none".
- Return ONLY valid JSON.

Return:

{{
    "intent": "short description",
    "tool": "tool_name_or_none",
    "reason": "why this is the next step",
    "requires_authorization": true_or_false
}}
"""

            response = await llm_agent.llm.generate(
                follow_up_message
            )

            try:
                decision = llm_agent._extract_json(response)

            except (json.JSONDecodeError, ValueError):
                return {
                    "success": False,
                    "status": "invalid_llm_response",
                    "message": (
                        "LLM returned an invalid next decision."
                    ),
                    "history": history,
                }

            # ------------------------------------------------
            # Security: validate next tool
            # ------------------------------------------------

            if (
                decision["tool"] != "none"
                and decision["tool"] not in registered_tools
            ):
                return {
                    "success": False,
                    "status": "blocked",
                    "message": (
                        f"LLM selected an unregistered tool: "
                        f"{decision['tool']}"
                    ),
                    "history": history,
                }

            # Registry remains source of truth
            if decision["tool"] != "none":
                selected_tool = registered_tools[
                    decision["tool"]
                ]

                decision["requires_authorization"] = (
                    selected_tool["requires_authorization"]
                )

        return {
            "success": False,
            "status": "max_steps_reached",
            "message": (
                f"Agent reached the maximum of "
                f"{max_steps} reasoning steps."
            ),
            "history": history,
        }


agent_loop = AgentLoop()
