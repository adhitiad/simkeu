from typing import ClassVar

from django.db import models


class OutboxEvent(models.Model):
    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_outbox"
        ordering: ClassVar[list[str]] = ["created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id}"