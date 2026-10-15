from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.rbac import require_permission
from backend.app.core.database import SessionLocal
from backend.app.models.database import KnowledgeDocument, User


router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    source: str = Field(default="manual", max_length=300)
    content: str = Field(min_length=10, max_length=50000)


class DocumentResponse(BaseModel):
    id: int
    title: str
    source: str
    is_active: bool


class SearchResult(BaseModel):
    id: int
    title: str
    source: str
    content: str
    score: float
    matched_terms: list[str]


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=201,
)
def create_document(
    request: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("knowledge.manage")),
):
    document = KnowledgeDocument(
        title=request.title.strip(),
        source=request.source.strip() or "manual",
        content=request.content.strip(),
    )

    if not document.title or len(document.content) < 10:
        raise HTTPException(
            status_code=422,
            detail="A title and at least 10 content characters are required.",
        )

    db.add(document)
    db.commit()
    db.refresh(document)

    return DocumentResponse(
        id=document.id,
        title=document.title,
        source=document.source,
        is_active=document.is_active,
    )


@router.get("/search", response_model=list[SearchResult])
def search_documents(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(default=3, ge=1, le=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("knowledge.manage")),
):
    from backend.app.knowledge.retrieval import retrieve_knowledge

    return retrieve_knowledge(db, q, limit)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("knowledge.manage")),
):
    documents = db.scalars(
        select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
    ).all()

    return [
        DocumentResponse(
            id=document.id,
            title=document.title,
            source=document.source,
            is_active=document.is_active,
        )
        for document in documents
    ]
