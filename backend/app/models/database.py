from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    username: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="customer",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )


class LoginAuditLog(Base):
    __tablename__ = "login_audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    event: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False,
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="accounts",
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
    )

    issue: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    diagnosis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="open",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="incidents",
    )

    actions: Mapped[list["AgentAction"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    performed_by: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    incident: Mapped["Incident"] = relationship(
        back_populates="actions",
    )


class Invoice(Base):
    """Demo invoice record used for read-only billing investigations."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    invoice_number: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="TZS",
    )

    invoice_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unpaid",
    )

    payment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )


class KnowledgeDocument(Base):
    """A source document used by the customer-support knowledge base."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="manual",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
class IncidentApproval(Base):
    __tablename__ = "incident_approvals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    target_username: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    requested_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    incident: Mapped["Incident"] = relationship()
