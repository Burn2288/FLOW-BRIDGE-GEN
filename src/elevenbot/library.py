"""Read-only projection of the existing service history; no media storage of its own."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LibraryItem:
    id: str
    kind: str
    model: str | None
    status: str
    available: bool
    created_at: datetime
    price: str | None

    @classmethod
    def from_history(cls, row: Any):
        return cls(id=str(row['id']), kind=row['kind'], model=row['model_id'],
                   status=row['status'], available=bool(row['file_available']),
                   created_at=row['created_at'],
                   price=str(row['price']) if row['price'] is not None else None)

    def as_dict(self):
        return {'id': self.id, 'kind': self.kind, 'model': self.model,
                'status': self.status, 'available': self.available,
                'created_at': self.created_at.isoformat(), 'price': self.price}
