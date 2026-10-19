import json
import re

from sqlalchemy.orm import Session
from backend.app.models.database import Incident, IncidentApproval
from backend.app.services.approval_service import create_unlock_approval

from backend.app.agents.llm_agent import llm_agent
from backend.app.agents.tool_executor import execute_tool
from backend.app.agents.tool_registry import list_tools
from backend.app.integrations.registry import list_integrations
from backend.app.agents.execution_policy import execution_policy
from backend.app.agents.issue_classifier import classify_issue
from backend.app.agents.issue_router import route_issue


def incident_belongs_to_customer(
    db: Session,
    incident_id: int | None,
    customer_id: int | None,
) -> bool:
    """Return True only when the incident belongs to this customer."""
    if incident_id is None or customer_id is None:
        return False

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    return (
        incident is not None
        and incident.customer_id == customer_id
    )


class AgentLoop:
    """
    Multi-step reasoning and tool execution loop.

    Architecture:

    LLM reasoning
        ↓
    Investigation
        ↓
    Formal Diagnosis
        ↓
    Authorization
        ↓
    Action
        ↓
    Verification
        ↓
    Resolution

    The LLM recommends what should happen.
    The system validates and executes the decision.
    """

    async def run(
        self,
        db: Session,
        customer_message: str,
        username: str,
        incident_id: int | None = None,
        authorized: bool = False,
        permissions: set[str] | None = None,
        actor_username: str | None = None,
        max_steps: int = 7,
    ) -> dict:

        # Classify the issue for routing and support context.
        issue_classification = classify_issue(customer_message)
        issue_route = route_issue(issue_classification)

        # Permissions must come from trusted server-side RBAC.
        # The legacy authorized flag must never grant tool permissions.
        effective_permissions = set(permissions or ())

        history = [{
            "type": "issue_classification",
            "classification": issue_classification,
        }, {
            "type": "issue_routing",
            "routing": issue_route,
        }]

        # Prevent formal diagnosis from running repeatedly
        # after the account has already been diagnosed.
        diagnosis_completed = False

        # Track whether a corrective action has actually
        # been executed during this incident.
        corrective_action_executed = False

        # Store the verified customer ID obtained during
        # account investigation.
        customer_id = None
        incident_created = incident_id is not None

        # ------------------------------------------------
        # Initial LLM reasoning
        # ------------------------------------------------

        decision_result = await llm_agent.decide(
            customer_message,
            issue_classification=issue_classification,
        )

        if not decision_result["success"]:
            return decision_result

        decision = decision_result["decision"]

        # Account-access issues must begin with account investigation.
        # Other support categories follow the registered-tool decision
        # selected by the LLM. Backend authorization remains authoritative.
        if issue_route["workflow"] == "account_investigation":
            decision = {
                "intent": decision.get(
                    "intent",
                    "Investigate customer account",
                ),
                "tool": "get_customer_account",
                "reason": (
                    "Account-access issues require account investigation "
                    "before corrective actions or incident resolution."
                ),
                "requires_authorization": False,
                "integration": None,
                "method": None,
                "path": None,
                "payload": None,
                "headers": None,
            }
        elif issue_route["workflow"] == "billing_investigation":
            decision = {
                "intent": "Investigate customer invoice",
                "tool": "lookup_invoice",
                "reason": (
                    "Billing issues must use the read-only invoice "
                    "investigation tool."
                ),
                "requires_authorization": True,
                "integration": None,
                "method": None,
                "path": None,
                "payload": None,
                "headers": None,
            }
        elif issue_route["workflow"] == "clarify":
            return {
                "success": True,
                "status": "clarification_required",
                "message": (
                    "Please provide more details about the problem "
                    "so the support agent can route it correctly."
                ),
                "classification": issue_classification,
                "routing": issue_route,
                "history": history,
            }

        # Global sequential counter for audit history.
        history_step = 0

        # Normalize possible null tool values.
        if decision.get("tool") is None:
            decision["tool"] = "none"

        for step in range(1, max_steps + 1):

            history_step += 1

            tool_name = decision.get("tool")

            # Normalize null again in case the LLM
            # returned null in a later decision.
            if tool_name is None:
                tool_name = "none"
                decision["tool"] = "none"

            history.append({
                "step": history_step,
                "decision": decision,
            })

            # ------------------------------------------------
            # No tool selected
            # ------------------------------------------------

            if tool_name == "none":

                return {
                    "success": True,
                    "status": "completed",
                    "history": history,
                }

            # ------------------------------------------------
            # SECURITY: Verify selected tool exists
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
                    permissions=effective_permissions,
                )
            )

            if not allowed:

                if required_next_tool:

                    history[-1]["policy"] = {
                        "blocked_tool": (
                            history[-1]["decision"]["tool"]
                        ),
                        "message": policy_message,
                        "required_next_tool": required_next_tool,
                    }

                    decision = {
                        "intent": (
                            "Perform required investigation first"
                        ),
                        "tool": required_next_tool,
                        "reason": policy_message,
                        "requires_authorization": False,
                    }

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

            required_permission = tool.get("required_permission")
            if (
                required_permission is not None
                and required_permission not in effective_permissions
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

            elif tool_name == "lookup_invoice":

                match = re.search(
                    r"\bINV-[A-Z0-9-]+\b",
                    customer_message,
                    re.IGNORECASE,
                )

                if not match:
                    return {
                        "success": True,
                        "status": "clarification_required",
                        "message": (
                            "Please provide the invoice number, "
                            "for example INV-DEMO-001."
                        ),
                        "history": history,
                    }

                parameters = {
                    "username": username,
                    "invoice_number": match.group(0).upper(),
                }

            elif tool_name == "unlock_account":

                parameters = {
                    "username": username,
                    "incident_id": incident_id,
                    "authorized": authorized,
                    "performed_by": actor_username,
                }

            elif tool_name == "create_incident":

                if customer_id is None:
                    return {
                        "success": False,
                        "status": "missing_customer",
                        "tool": tool_name,
                        "message": (
                            "Customer ID is required before "
                            "creating an incident."
                        ),
                        "history": history,
                    }

                parameters = {
                    "customer_id": customer_id,
                    "issue": customer_message,
                }

            elif tool_name == "diagnose_incident":

                parameters = {
                    "incident_id": incident_id,
                    "username": username,
                }

            elif tool_name in {
                "verify_incident_resolution",
                "resolve_incident",
            }:

                parameters = {
                    "incident_id": incident_id,
                }

            elif tool_name == "call_rest_api":

                parameters = {
                    "integration": decision.get(
                        "integration"
                    ),
                    "method": decision.get(
                        "method",
                        "GET",
                    ),
                    "path": decision.get(
                        "path",
                        "/",
                    ),
                    "payload": decision.get(
                        "payload"
                    ),
                    "headers": decision.get(
                        "headers"
                    ),
                }

                if not parameters["integration"]:

                    return {
                        "success": False,
                        "status": "missing_integration",
                        "tool": tool_name,
                        "message": (
                            "An approved integration is "
                            "required before calling the "
                            "REST API."
                        ),
                        "history": history,
                    }

            else:

                return {
                    "success": False,
                    "status": "unsupported_tool",
                    "tool": tool_name,
                    "message": (
                        "The selected tool does not yet have "
                        "an execution parameter mapping. "
                        f"tool_name={tool_name!r}"
                    ),
                    "history": history,
                }

            # ------------------------------------------------
            # Execute tool
            # ------------------------------------------------

            execution = await execute_tool(
                db=db,
                tool_name=tool_name,
                parameters=parameters,
                authorized=authorized,
                    permissions=effective_permissions,
            )

            history[-1]["execution"] = execution

            # Capture the verified customer ID from the
            # account investigation result.
            if (
                tool_name == "get_customer_account"
                and execution.get("success")
            ):
                result = execution.get("result", {})

                if result.get("found"):
                    customer = result.get("customer", {})
                    customer_id = customer.get("id")

            if not execution["success"]:

                return {
                    "success": False,
                    "status": "tool_failed",
                    "tool": tool_name,
                    "message": execution["message"],
                    "history": history,
                }

            # ------------------------------------------------
            # Billing investigation: return verified tool data
            # without another LLM decision.
            # ------------------------------------------------

            if tool_name == "lookup_invoice":
                invoice_result = execution.get("result", {})

                if not invoice_result.get("found"):
                    return {
                        "success": True,
                        "status": "completed",
                        "tool": tool_name,
                        "message": invoice_result.get(
                            "message",
                            "Account or invoice not found.",
                        ),
                        "invoice": invoice_result,
                        "history": history,
                    }

                if invoice_result.get("paid_but_unpaid_invoice"):
                    message = (
                        f"Invoice {invoice_result.get('invoice_number')} "
                        "has a billing discrepancy: payment is marked "
                        "paid, but the invoice is marked unpaid. "
                        "The record requires billing-team review."
                    )
                else:
                    message = (
                        f"Invoice {invoice_result.get('invoice_number')} "
                        "was found. No paid-but-unpaid mismatch was "
                        "detected in the available record."
                    )

                return {
                    "success": True,
                    "status": "completed",
                    "tool": tool_name,
                    "message": message,
                    "invoice": invoice_result,
                    "history": history,
                }

            # ------------------------------------------------
            # SECURITY: Validate supplied incident ownership
            # before diagnosis or any subsequent incident action.
            # ------------------------------------------------

            if (
                tool_name == "get_customer_account"
                and incident_created
                and not incident_belongs_to_customer(
                    db=db,
                    incident_id=incident_id,
                    customer_id=customer_id,
                )
            ):
                return {
                    "success": False,
                    "status": "incident_customer_mismatch",
                    "message": (
                        "The supplied incident does not belong "
                        "to the investigated account's customer, "
                        "or the incident/customer could not be found."
                    ),
                    "incident_id": incident_id,
                    "history": history,
                }

            # ------------------------------------------------
            # Handle successful incident creation
            # ------------------------------------------------
            #
            # A newly created incident becomes the active
            # incident for all following diagnosis,
            # verification and resolution steps.
            # ------------------------------------------------

            if tool_name == "create_incident":

                result = execution.get("result", {})

                new_incident_id = result.get("incident_id")

                if new_incident_id is not None:
                    incident_id = new_incident_id

            # ------------------------------------------------
            # Track corrective action
            # ------------------------------------------------
            #
            # A corrective action counts as executed only
            # when the actual tool result reports success.
            # ------------------------------------------------

            if tool_name == "unlock_account":

                result = execution.get("result", {})

                action_succeeded = (
                    result.get("success") is True
                )

                if action_succeeded:
                    corrective_action_executed = True
                else:
                    return {
                        "success": False,
                        "status": "action_failed",
                        "tool": tool_name,
                        "message": result.get(
                            "message",
                            "Corrective action failed.",
                        ),
                        "incident_id": incident_id,
                        "history": history,
                    }

            # ------------------------------------------------
            # FORMAL DIAGNOSIS ENGINE
            # ------------------------------------------------
            #
            # Only perform the formal diagnosis after the
            # initial account investigation.
            #
            # It must NOT run again after the corrective
            # action has already been performed.
            # ------------------------------------------------

            if (
                tool_name == "get_customer_account"
                and not incident_created
                and customer_id is not None
            ):

                incident_creation = await execute_tool(
                    db=db,
                    tool_name="create_incident",
                    parameters={
                        "customer_id": customer_id,
                        "issue": customer_message,
                    },
                    authorized=authorized,
                    permissions=effective_permissions,
                )

                history_step += 1

                history.append({
                    "step": history_step,
                    "decision": {
                        "intent": (
                            "Create incident for customer support tracking"
                        ),
                        "tool": "create_incident",
                        "reason": (
                            "Customer account investigation identified "
                            "the customer. An incident must be created "
                            "before formal diagnosis."
                        ),
                        "requires_authorization": False,
                    },
                    "execution": incident_creation,
                })

                if not incident_creation["success"]:
                    return {
                        "success": False,
                        "status": "incident_creation_failed",
                        "tool": "create_incident",
                        "message": incident_creation["message"],
                        "history": history,
                    }

                incident_result = incident_creation.get(
                    "result",
                    {},
                )

                new_incident_id = incident_result.get(
                    "incident_id"
                )

                if new_incident_id is None:
                    return {
                        "success": False,
                        "status": "incident_creation_failed",
                        "tool": "create_incident",
                        "message": (
                            "Incident was created but no incident ID "
                            "was returned."
                        ),
                        "history": history,
                    }

                incident_id = new_incident_id
                incident_created = True

            if (
                tool_name == "get_customer_account"
                and incident_created
                and not diagnosis_completed
            ):

                diagnosis_execution = await execute_tool(
                    db=db,
                    tool_name="diagnose_incident",
                    parameters={
                        "incident_id": incident_id,
                        "username": username,
                    },
                    authorized=authorized,
                    permissions=effective_permissions,
                )

                history_step += 1

                history.append({
                    "step": history_step,
                    "decision": {
                        "intent": (
                            "Perform formal incident diagnosis"
                        ),
                        "tool": "diagnose_incident",
                        "reason": (
                            "Account investigation completed. "
                            "The system must determine the "
                            "root cause using actual database state."
                        ),
                        "requires_authorization": False,
                    },
                    "execution": diagnosis_execution,
                })

                if not diagnosis_execution["success"]:

                    return {
                        "success": False,
                        "status": "diagnosis_failed",
                        "tool": "diagnose_incident",
                        "message": (
                            diagnosis_execution["message"]
                        ),
                        "history": history,
                    }

                diagnosis_result = (
                    diagnosis_execution["result"]
                )

                diagnosis_completed = True

                # ------------------------------------------------
                # Formal diagnosis is authoritative
                # ------------------------------------------------

                recommended_action = (
                    diagnosis_result.get(
                        "recommended_action"
                    )
                )

                # ------------------------------------------------
                # Locked account
                # ------------------------------------------------

                if recommended_action == "unlock_account":

                    if "account.unlock" not in effective_permissions:

                        if incident_id is None:
                            return {
                                "success": False,
                                "status": "approval_request_failed",
                                "message": "An incident ID is required for approval.",
                                "history": history,
                            }

                        approval = (
                            db.query(IncidentApproval)
                            .filter(
                                IncidentApproval.incident_id == incident_id,
                                IncidentApproval.action == "unlock_account",
                                IncidentApproval.target_username == username,
                                IncidentApproval.status == "pending",
                            )
                            .first()
                        )

                        if approval is None:
                            approval = create_unlock_approval(
                                db=db,
                                incident_id=incident_id,
                                username=username,
                                requested_by=actor_username or username,
                            )

                        return {
                            "success": True,
                            "status": "awaiting_authorization",
                            "tool": "unlock_account",
                            "approval_id": approval.id,
                            "approval_status": approval.status,
                            "incident_id": incident_id,
                            "message": (
                                "The formal diagnosis determined "
                                "that the account is locked. "
                                "Authorization is required before "
                                "the account can be unlocked."
                            ),
                            "diagnosis": diagnosis_result,
                            "history": history,
                        }

                    decision = {
                        "intent": (
                            "Unlock the locked customer account"
                        ),
                        "tool": "unlock_account",
                        "reason": (
                            "Formal diagnosis confirmed that "
                            "the account is locked."
                        ),
                        "requires_authorization": True,
                    }

                    continue

                # ------------------------------------------------
                # Further investigation
                # ------------------------------------------------
                #
                # The formal diagnosis is authoritative.
                # If no account-level corrective action was
                # identified, do not allow the LLM to create
                # another incident automatically.
                #
                # The current incident remains the active
                # incident and should be escalated when the
                # available tools cannot resolve the issue.
                # ------------------------------------------------

                if recommended_action == "further_investigation":

                    return {
                        "success": False,
                        "status": "needs_escalation",
                        "incident_id": incident_id,
                        "message": (
                            f"Incident #{incident_id}: further investigation is required.\n"
                            f"Root cause: {diagnosis_result.get('root_cause', 'Not confirmed.')}\n"
                            f"Account status: {diagnosis_result.get('account', {}).get('status', 'Unknown')}\n"
                            f"Account locked: {diagnosis_result.get('account', {}).get('is_locked', 'Unknown')}\n"
                            f"Evidence:\n"
                            + "\n".join(
                                f"- {item}"
                                for item in diagnosis_result.get("evidence", [])
                            )
                            + "\nNext steps: inspect authentication-service logs and "
                            "verify the login failure reason. No account changes were made."
                        ),
                        "diagnosis": diagnosis_result,
                        "history": history,
                    }

                # ------------------------------------------------
                # Other diagnosis
                # ------------------------------------------------

                follow_up_message = f"""
Original customer message:
{customer_message}

Username:
{username}

FORMAL DIAGNOSIS:

{json.dumps(diagnosis_result, indent=2)}

The diagnosis engine is authoritative.

Do not invent or modify the diagnosis.

Based on the diagnosis and available tools,
decide the NEXT appropriate step.

Available tools:

{json.dumps(list_tools(), indent=2)}

Approved integrations:

{json.dumps(list_integrations(), indent=2)}

Rules:

- Do not invent tools.
- Do not execute tools yourself.
- Use the formal diagnosis as the source of truth.
- If authorization is required, report it.
- If the problem is resolved, choose "none".
- Return ONLY valid JSON.

For REST API calls:

- Only use "call_rest_api" with an approved integration.
- "integration" must be an integration from the approved list.
- Never invent an integration.
- "method" must be GET, POST, PUT, PATCH, or DELETE.
- "path" must begin with "/".
- Never provide an arbitrary complete URL.
- "payload" may be null.
- "headers" may be null.
- Never invent credentials or secrets.

For non-REST tools:

- "integration" must be null.
- "method" must be null.
- "path" must be null.
- "payload" must be null.
- "headers" must be null.

Return:

{{
    "intent": "short description",
    "tool": "tool_name_or_none",
    "reason": "why this is the next step",
    "requires_authorization": true_or_false,
    "integration": "local_health",
    "method": "GET",
    "path": "/health",
    "payload": null,
    "headers": null
}}
"""

                response = await llm_agent.llm.generate(
                    follow_up_message
                )

                try:

                    decision = llm_agent._extract_json(
                        response
                    )

                except (
                    json.JSONDecodeError,
                    ValueError,
                ):

                    return {
                        "success": False,
                        "status": "invalid_llm_response",
                        "message": (
                            "LLM returned an invalid next decision."
                        ),
                        "history": history,
                    }

                # Handle LLM JSON null.
                if decision.get("tool") is None:
                    decision["tool"] = "none"

                continue

            # ------------------------------------------------
            # Resolution Guard
            # ------------------------------------------------
            #
            # IMPORTANT:
            # Only consider an already-recovered account
            # resolved automatically if a corrective action
            # was actually executed.
            #
            # This prevents a healthy account from being
            # incorrectly treated as recovered simply because
            # it was already active before the agent started.
            # ------------------------------------------------

            if (
                tool_name == "get_customer_account"
                and corrective_action_executed
            ):

                account_result = execution["result"]

                if account_result.get("found"):

                    account = account_result.get(
                        "account",
                        {}
                    )

                    account_is_recovered = (
                        account.get("status") == "active"
                        and account.get(
                            "failed_login_attempts"
                        ) == 0
                        and account.get(
                            "is_locked"
                        ) is False
                    )

                    if account_is_recovered:

                        # ------------------------------------------------
                        # Verification
                        # ------------------------------------------------

                        verification = await execute_tool(
                            db=db,
                            tool_name="verify_incident_resolution",
                            parameters={
                                "incident_id": incident_id,
                            },
                            authorized=authorized,
                    permissions=effective_permissions,
                        )

                        history_step += 1

                        history.append({
                            "step": history_step,
                            "decision": {
                                "intent": (
                                    "Verify successful account recovery"
                                ),
                                "tool": (
                                    "verify_incident_resolution"
                                ),
                                "reason": (
                                    "The corrective action was "
                                    "executed and the account is "
                                    "now active, unlocked, and "
                                    "has zero failed login attempts."
                                ),
                                "requires_authorization": False,
                            },
                            "execution": verification,
                        })

                        if not verification["success"]:

                            return {
                                "success": False,
                                "status": "verification_failed",
                                "tool": (
                                    "verify_incident_resolution"
                                ),
                                "message": (
                                    verification["message"]
                                ),
                                "history": history,
                            }

                        verification_result = (
                            verification["result"]
                        )

                        if not verification_result.get(
                            "verified"
                        ):

                            return {
                                "success": False,
                                "status": "verification_failed",
                                "tool": (
                                    "verify_incident_resolution"
                                ),
                                "message": (
                                    verification_result.get(
                                        "message",
                                        "Account recovery "
                                        "verification failed.",
                                    )
                                ),
                                "history": history,
                            }

                        # ------------------------------------------------
                        # Resolution
                        # ------------------------------------------------

                        resolution = await execute_tool(
                            db=db,
                            tool_name="resolve_incident",
                            parameters={
                                "incident_id": incident_id,
                            },
                            authorized=authorized,
                    permissions=effective_permissions,
                        )

                        history_step += 1

                        history.append({
                            "step": history_step,
                            "decision": {
                                "intent": (
                                    "Resolve recovered incident"
                                ),
                                "tool": "resolve_incident",
                                "reason": (
                                    "Verification confirmed "
                                    "that account recovery "
                                    "was successful."
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
                                "message": (
                                    resolution["message"]
                                ),
                                "history": history,
                            }

                        return {
                            "success": True,
                            "status": "resolved",
                            "incident_id": incident_id,
                            "diagnosis": (
                                "The formal diagnosis confirmed "
                                "that the customer account was "
                                "locked. The account was unlocked "
                                "and successfully verified."
                            ),
                            "verification": (
                                verification_result.get(
                                    "message",
                                    "Account recovery "
                                    "successfully verified.",
                                )
                            ),
                            "resolution": (
                                resolution["result"].get(
                                    "message",
                                    "Incident successfully "
                                    "resolved.",
                                )
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

Approved integrations:

{json.dumps(list_integrations(), indent=2)}

Remember:

- Do not invent tools.
- Do not execute tools yourself.
- Choose only one next tool.
- If authorization is required, report it.
- If the problem is resolved, choose "none".
- Return ONLY valid JSON.

For REST API calls:

- Only use "call_rest_api" with an approved integration.
- "integration" must be an integration from the approved list.
- Never invent an integration.
- "method" must be GET, POST, PUT, PATCH, or DELETE.
- "path" must begin with "/".
- Never provide an arbitrary complete URL.
- "payload" may be null.
- "headers" may be null.
- Never invent credentials or secrets.

For non-REST tools:

- "integration" must be null.
- "method" must be null.
- "path" must be null.
- "payload" must be null.
- "headers" must be null.

Return:

{{
    "intent": "short description",
    "tool": "tool_name_or_none",
    "reason": "why this is the next step",
    "requires_authorization": true_or_false,
    "integration": "local_health",
    "method": "GET",
    "path": "/health",
    "payload": null,
    "headers": null
}}
"""

            response = await llm_agent.llm.generate(
                follow_up_message
            )

            try:

                decision = llm_agent._extract_json(
                    response
                )

            except (
                json.JSONDecodeError,
                ValueError,
            ):

                return {
                    "success": False,
                    "status": "invalid_llm_response",
                    "message": (
                        "LLM returned an invalid next decision."
                    ),
                    "history": history,
                }

            # ------------------------------------------------
            # Normalize null tool
            # ------------------------------------------------

            if decision.get("tool") is None:
                decision["tool"] = "none"

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

            # ------------------------------------------------
            # Registry remains source of truth
            # ------------------------------------------------

            if decision["tool"] != "none":

                selected_tool = registered_tools[
                    decision["tool"]
                ]

                decision["requires_authorization"] = (
                    selected_tool[
                        "requires_authorization"
                    ]
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
