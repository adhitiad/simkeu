from __future__ import annotations

import structlog
from celery import shared_task
from django.utils import timezone

from .models import OutboxEvent

logger = structlog.get_logger(__name__)


@shared_task  # type: ignore[untyped-decorator]
def relay_outbox(limit: int = 100) -> int:
    """Relay at-least-once. Consumer wajib idempotent per event_id."""
    events = list(
        OutboxEvent.objects.filter(published_at__isnull=True).order_by("created_at")[:limit]
    )
    for event in events:
        # Implementasi transport (webhook/event bus/SIAKAD) di sini.
        logger.info("outbox_publish", event_id=str(event.event_id), event_type=event.event_type)
        event.published_at = timezone.now()
        event.save(update_fields=["published_at"])
    return len(events)