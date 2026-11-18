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
    result_url: str | None

    @classmethod
    def from_history(cls, row: Any):
        return cls(id=str(row['id']), kind=row['kind'], model=row['model_id'],
                   status=row['status'], available=bool(row['file_available']),
                   created_at=row['created_at'],
                   price=str(row['price']) if row['price'] is not None else None,
                   result_url=result_url(row))

    def as_dict(self):
        return {'id': self.id, 'kind': self.kind, 'model': self.model,
                'status': self.status, 'available': self.available,
                'created_at': self.created_at.isoformat(), 'price': self.price,
                'result_url': self.result_url}


def result_url(row):
    """A result link exists only for a saved, available work of a supported kind."""
    kind = row['kind']
    if row['status'] != 'succeeded' or not row['file_available'] or kind not in ('image', 'video', 'audio', 'chat'):
        return None
    return f"/api/v1/works/{kind}/{row['id']}"


def project_history(row):
    """Preserve original fields and IDs for the Telegram and Mini App consumers."""
    result = dict(row)
    result['result_url'] = result_url(row)
    return result
