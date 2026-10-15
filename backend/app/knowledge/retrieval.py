import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.database import KnowledgeDocument


def _tokens(text: str) -> set[str]:
    """Extract useful search terms without requiring another ML model."""
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_]+", text.lower())
        if len(token) > 1
    }


def retrieve_knowledge(
    db: Session,
    query: str,
    limit: int = 3,
) -> list[dict]:
    """Return active documents ranked by keyword overlap."""
    query_terms = _tokens(query)

    if not query_terms:
        return []

    documents = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.is_active.is_(True)
        )
    ).all()

    ranked = []

    for document in documents:
        content_terms = _tokens(
            f"{document.title} {document.content}"
        )
        overlap = query_terms & content_terms

        if not overlap:
            continue

        score = len(overlap) / len(query_terms)

        ranked.append({
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "content": document.content,
            "score": round(score, 4),
            "matched_terms": sorted(overlap),
        })

    ranked.sort(
        key=lambda item: (item["score"], len(item["matched_terms"])),
        reverse=True,
    )

    return ranked[:max(1, min(limit, 5))]
