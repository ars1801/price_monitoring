from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source


class SourceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(self, *, name: str, base_url: str) -> Source:
        source = self._db.scalar(select(Source).where(Source.name == name))
        if source:
            if not source.base_url:
                source.base_url = base_url
            return source

        source = Source(name=name, base_url=base_url)
        self._db.add(source)
        self._db.flush()
        return source