from __future__ import annotations

import base64
import binascii
from datetime import date
from typing import ClassVar, cast
from uuid import UUID

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import JournalEntry
from .serializers import JournalCreateSerializer, JournalReadSerializer
from .services import (
    AccountNotFoundError,
    AuthorizationError,
    DuplicateJournalError,
    InvalidJournalError,
    Journal,
    JournalLine,
    LedgerError,
    PeriodClosedError,
    PeriodConfigurationError,
    PeriodNotFoundError,
    post,
)


def _encode_cursor(entry: JournalEntry) -> str:
    raw = f"{entry.business_date.isoformat()}:{entry.pk}"
    return base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> tuple[date, UUID]:
    padded = value + ("=" * (-len(value) % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
        date_value, id_value = decoded.split(":", maxsplit=1)
        return date.fromisoformat(date_value), UUID(id_value)
    except (ValueError, UnicodeDecodeError, UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("Cursor tidak valid.") from exc


class JournalCollectionView(APIView):
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAdminUser]

    def get(self, request: Request) -> Response:
        raw_entity_id = request.query_params.get("entity_id")
        if raw_entity_id is None:
            return Response(
                {"detail": "Parameter entity_id wajib diisi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            entity_id = int(raw_entity_id)
            limit = int(request.query_params.get("limit", "50"))
        except ValueError:
            return Response(
                {"detail": "entity_id dan limit harus berupa integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if entity_id <= 0 or not 1 <= limit <= 100:
            return Response(
                {"detail": "entity_id harus positif dan limit berada pada rentang 1-100."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            JournalEntry.objects.filter(entity_id=entity_id)
            .select_related("period", "created_by")
            .prefetch_related("lines__account")
        )
        raw_cursor = request.query_params.get("cursor")
        if raw_cursor:
            try:
                cursor_date, cursor_id = _decode_cursor(raw_cursor)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(
                Q(business_date__lt=cursor_date) | Q(business_date=cursor_date, id__lt=cursor_id)
            )

        rows = list(queryset.order_by("-business_date", "-id")[: limit + 1])
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = _encode_cursor(page[-1]) if has_more and page else None
        return Response(
            {
                "results": JournalReadSerializer(page, many=True).data,
                "next_cursor": next_cursor,
            }
        )

    def post(self, request: Request) -> Response:
        serializer = JournalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = cast(dict[str, object], serializer.validated_data)
        raw_lines = cast(list[dict[str, object]], values["lines"])
        journal_lines = tuple(
            JournalLine(
                account_id=cast(UUID, line["account_id"]),
                debit=cast(int, line["debit"]),
                credit=cast(int, line["credit"]),
                description=cast(str, line["description"]),
            )
            for line in raw_lines
        )
        journal = Journal(
            entity_id=cast(int, values["entity_id"]),
            business_date=cast(date, values["business_date"]),
            source_type=cast(str, values["source_type"]),
            source_id=cast(str, values["source_id"]),
            description=cast(str, values["description"]),
            lines=journal_lines,
        )
        actor_id = request.user.pk
        if not isinstance(actor_id, int) or isinstance(actor_id, bool):
            return Response(
                {"detail": "Identitas pengguna tidak valid."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            entry = post(journal, actor_id=actor_id)
        except AuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except DuplicateJournalError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (
            AccountNotFoundError,
            InvalidJournalError,
            PeriodClosedError,
            PeriodConfigurationError,
            PeriodNotFoundError,
        ) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LedgerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            JournalReadSerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )
