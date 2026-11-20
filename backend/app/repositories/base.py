from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Small reusable query pattern; add domain repositories for domain behavior."""

    def __init__(self, session: Session, model: type[ModelType]) -> None:
        self.session = session
        self.model = model

    def add(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        return entity

    def get(self, entity_id: object) -> ModelType | None:
        return self.session.get(self.model, entity_id)

    def list(self) -> Sequence[ModelType]:
        return self.session.scalars(select(self.model)).all()
