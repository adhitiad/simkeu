from __future__ import annotations

import structlog
from celery import shared_task

from .integrations import SiakadClient, SimpegClient

logger = structlog.get_logger(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def sync_student(student_number: str) -> dict[str, object]:
    data = SiakadClient().get_student(student_number)
    logger.info("siakad_sync_ok", student_number=student_number)
    return data


@shared_task(  # type: ignore[untyped-decorator]
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def sync_employee(employee_id: str) -> dict[str, object]:
    data = SimpegClient().get_employee(employee_id)
    logger.info("simpeg_sync_ok", employee_id=employee_id)
    return data