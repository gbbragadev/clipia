from __future__ import annotations

import uuid

from sqlalchemy import JSON, CHAR
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


JsonType = JSON().with_variant(JSONB, "postgresql")


class GUID(TypeDecorator):
    """Portable UUID storage for PostgreSQL and SQLite test databases."""

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value if dialect.name == "postgresql" else str(value)
        parsed = uuid.UUID(str(value))
        return parsed if dialect.name == "postgresql" else str(parsed)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
