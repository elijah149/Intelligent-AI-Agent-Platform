"""Classify customer support issues before the agent chooses an action."""

import re
from typing import Any


ISSUE_PATTERNS = {
    "account_access": (
        r"\blog[\s-]?in\b", r"\bsign[\s-]?in\b", r"\bpassword\b",
        r"\blocked account\b", r"\baccount locked\b", r"\baccount is locked\b", r"\bforgot password\b",
        r"\bcan't access\b", r"\bcannot access\b", r"\bverification code\b",
        r"\bfailed login\b", r"\bakaunti\b", r"\bnenosiri\b",
    ),
    "billing": (
        r"\bbill(?:ing)?\b", r"\bpayment\b", r"\bpaid\b", r"\bpay(?:ment)?\b",
        r"\binvoice\b", r"\brefund\b", r"\bcharged\b", r"\btransaction\b",
        r"\bsubscription\b", r"\bmalipo\b", r"\bnimelipia\b", r"\bpesa\b",
    ),
    "technical": (
        r"\berror\b", r"\bbug\b", r"\bcrash(?:es|ed)?\b",
        r"\bnot working\b", r"\bdoesn't work\b", r"\bfailed\b",
        r"\bslow\b", r"\bserver\b", r"\bapi\b", r"\bdatabase\b",
        r"\bexception\b", r"\btechnical\b", r"\bhaifunguki\b",
        r"\bimeharibika\b",
    ),
    "service_request": (
        r"\border\b", r"\bdelivery\b", r"\bservice request\b",
        r"\btrack\b", r"\bstatus\b", r"\bcancel\b", r"\bbooking\b",
        r"\boda\b", r"\bhuduma\b", r"\bkuchelewa\b",
    ),
}


def classify_issue(message: str) -> dict[str, Any]:
    """Return a predictable category and matched keywords for a support message."""
    text = re.sub(r"\s+", " ", (message or "").strip().lower())

    if not text:
        return {
            "category": "unknown",
            "confidence": 0.0,
            "matched_keywords": [],
            "needs_clarification": True,
        }

    scores: dict[str, list[str]] = {}

    for category, patterns in ISSUE_PATTERNS.items():
        matches = [
            pattern.strip("\\b")
            for pattern in patterns
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        if matches:
            scores[category] = matches

    if not scores:
        return {
            "category": "general_support",
            "confidence": 0.3,
            "matched_keywords": [],
            "needs_clarification": False,
        }

    # Select the category with the most matched patterns.
    # Ties are reported as ambiguous instead of guessing.
    highest = max(len(matches) for matches in scores.values())
    winners = [
        category for category, matches in scores.items()
        if len(matches) == highest
    ]

    if len(winners) != 1:
        return {
            "category": "multiple_issues",
            "confidence": 0.4,
            "matched_keywords": sorted(
                {keyword for matches in scores.values() for keyword in matches}
            ),
            "needs_clarification": True,
        }

    category = winners[0]
    count = len(scores[category])
    confidence = min(0.95, 0.55 + (count - 1) * 0.15)

    return {
        "category": category,
        "confidence": round(confidence, 2),
        "matched_keywords": scores[category],
        "needs_clarification": False,
    }
