from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence
from uuid import UUID

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Account, AccountingPeriod, JournalEntry, JournalLineRecord, PeriodStatus

Rupiah = int


class LedgerError(Exception):
    """Base error for ledger domain operations."""


class InvalidJournalError(LedgerError):
    """The journal input violates a financial invariant."""


class AuthorizationError(LedgerError):
    """The actor is not allowed to perform this financial operation."""


class PeriodNotFoundError(LedgerError):
    """No accounting period covers the journal business date."""


class PeriodClosedError(LedgerError):
    """The requested operation targets a closed accounting period."""


class PeriodConfigurationError(LedgerError):
    """More than one accounting period covers the same business date."""


class AccountNotFoundError(LedgerError):
    """An account is missing, inactive, or outside the entity scope."""


class DuplicateJournalError(LedgerError):
    """A source key was reused with different journal contents."""


class MakerCheckerError(LedgerError):
    """The maker and checker must be different active finance administrators."""


@dataclass(frozen=True, slots=True)
class JournalLine:
    account_id: UUID
    debit: Rupiah
    credit: Rupiah
    description: str = ""


@dataclass(frozen=True, slots=True)
class Journal:
    entity_id: int
    business_date: date
    source_type: str
    source_id: str
    lines: Sequence[JournalLine]
    description: str = ""


def validate_journal(journal: Journal) -> None:
    """Validate a journal without performing database I/O."""
    if (
        not isinstance(journal.entity_id, int)
        or isinstance(journal.entity_id, bool)
        or journal.entity_id <= 0
    ):
        raise InvalidJournalError("entity_id harus berupa bilangan bulat positif.")
    if not isinstance(journal.business_date, date) or isinstance(journal.business_date, datetime):
        raise InvalidJournalError("business_date harus berupa tanggal tanpa komponen waktu.")
    if not isinstance(journal.source_type, str) or not journal.source_type.strip():
        raise InvalidJournalError("source_type wajib diisi.")
    if len(journal.source_type) > 64:
        raise InvalidJournalError("source_type maksimal 64 karakter.")
    if not isinstance(journal.source_id, str) or not journal.source_id.strip():
        raise InvalidJournalError("source_id wajib diisi.")
    if len(journal.source_id) > 128:
        raise InvalidJournalError("source_id maksimal 128 karakter.")
    if not isinstance(journal.description, str) or len(journal.description) > 500:
        raise InvalidJournalError("description harus berupa teks maksimal 500 karakter.")
    if len(journal.lines) < 2:
        raise InvalidJournalError("Jurnal minimal memiliki dua baris.")

    debit_total = 0
    credit_total = 0
    for line in journal.lines:
        if not isinstance(line.account_id, UUID):
            raise InvalidJournalError("account_id harus berupa UUID.")
        if not isinstance(line.debit, int) or isinstance(line.debit, bool):
            raise InvalidJournalError("Nominal debit harus berupa integer Rupiah.")
        if not isinstance(line.credit, int) or isinstance(line.credit, bool):
            raise InvalidJournalError("Nominal kredit harus berupa integer Rupiah.")
        if line.debit < 0 or line.credit < 0:
            raise InvalidJournalError("Nominal debit/kredit tidak boleh negatif.")
        if (line.debit > 0) == (line.credit > 0):
            raise InvalidJournalError("Setiap baris harus berisi debit atau kredit, bukan keduanya.")
        if not isinstance(line.description, str) or len(line.description) > 255:
            raise InvalidJournalError("Deskripsi baris harus berupa teks maksimal 255 karakter.")
        debit_total += line.debit
        credit_total += line.credit

    if debit_total <= 0:
        raise InvalidJournalError("Nominal jurnal harus lebih besar dari nol.")
    if debit_total != credit_total:
        raise InvalidJournalError("Jurnal tidak seimbang: total debit harus sama dengan kredit.")
    if debit_total > 9_223_372_036_854_775_807:
        raise InvalidJournalError("Total jurnal melebihi batas integer Rupiah yang didukung.")


def _is_same_source(existing: JournalEntry, journal: Journal) -> bool:
    existing_lines = list(existing.lines.all())
    expected_lines = list(journal.lines)
    if len(existing_lines) != len(expected_lines):
        return False
    return (
        existing.entity_id == journal.entity_id
        and existing.business_date == journal.business_date
        and existing.description == journal.description
        and all(
            stored.account_id == expected.account_id
            and stored.debit == expected.debit
            and stored.credit == expected.credit
            and stored.description == expected.description
            for stored, expected in zip(existing_lines, expected_lines, strict=True)
        )
    )


def post(journal: Journal, *, actor_id: int) -> JournalEntry:
    """
    Persist one balanced journal atomically.

    This is the only application write path for posted ledger entries. The
    database independently enforces period state, source uniqueness,
    line ownership, balance, and append-only behavior.
    """
    validate_journal(journal)

    actor = User.objects.filter(pk=actor_id, is_active=True, is_staff=True).first()
    if actor is None:
        raise AuthorizationError("Hanya pengguna aktif dengan hak administrasi keuangan yang dapat mem-posting jurnal.")

    with transaction.atomic():
        existing = (
            JournalEntry.objects.filter(
                entity_id=journal.entity_id,
                source_type=journal.source_type,
                source_id=journal.source_id,
            )
            .prefetch_related("lines")
            .first()
        )
        if existing is not None:
            if _is_same_source(existing, journal):
                return existing
            raise DuplicateJournalError("Kunci sumber jurnal sudah digunakan dengan isi yang berbeda.")

        periods = AccountingPeriod.objects.select_for_update().filter(
            entity_id=journal.entity_id,
            starts_on__lte=journal.business_date,
            ends_on__gte=journal.business_date,
        )
        try:
            period = periods.get()
        except AccountingPeriod.DoesNotExist as exc:
            raise PeriodNotFoundError("Tidak ada periode akuntansi yang mencakup tanggal jurnal.") from exc
        except AccountingPeriod.MultipleObjectsReturned as exc:
            raise PeriodConfigurationError("Konfigurasi periode tumpang tindih untuk tanggal jurnal.") from exc

        if period.status != PeriodStatus.OPEN:
            raise PeriodClosedError("Jurnal tidak dapat diposting ke periode yang sudah ditutup.")

        account_ids = sorted({line.account_id for line in journal.lines}, key=str)
        accounts = {
            account.pk: account
            for account in Account.objects.select_for_update()
            .filter(entity_id=journal.entity_id, pk__in=account_ids)
            .order_by("pk")
        }
        if len(accounts) != len(account_ids) or any(not account.is_active for account in accounts.values()):
            raise AccountNotFoundError("Satu atau lebih akun tidak ditemukan, tidak aktif, atau di luar entitas.")

        try:
            with transaction.atomic():
                entry = JournalEntry.objects.create(
                    entity_id=journal.entity_id,
                    period=period,
                    business_date=journal.business_date,
                    source_type=journal.source_type,
                    source_id=journal.source_id,
                    description=journal.description,
                    posted_at=timezone.now(),
                    created_by=actor,
                )
                JournalLineRecord.objects.bulk_create(
                    [
                        JournalLineRecord(
                            entity_id=journal.entity_id,
                            entry=entry,
                            account=accounts[line.account_id],
                            line_number=index,
                            description=line.description,
                            debit=line.debit,
                            credit=line.credit,
                            created_by=actor,
                        )
                        for index, line in enumerate(journal.lines, start=1)
                    ]
                )
        except IntegrityError as exc:
            duplicate = (
                JournalEntry.objects.filter(
                    entity_id=journal.entity_id,
                    source_type=journal.source_type,
                    source_id=journal.source_id,
                )
                .prefetch_related("lines")
                .first()
            )
            if duplicate is not None:
                if _is_same_source(duplicate, journal):
                    return duplicate
                raise DuplicateJournalError(
                    "Kunci sumber jurnal sudah digunakan dengan isi yang berbeda."
                ) from exc
            raise

        return entry


def close_period(period_id: UUID, *, maker_id: int, checker_id: int) -> AccountingPeriod:
    """Close an accounting period using a two-person approval."""
    if maker_id == checker_id:
        raise MakerCheckerError("Pembuat dan penyetuju penutupan periode harus berbeda.")

    users = {
        user.pk: user
        for user in User.objects.filter(
            pk__in=[maker_id, checker_id],
            is_active=True,
            is_staff=True,
        )
    }
    if len(users) != 2:
        raise AuthorizationError("Pembuat dan penyetuju harus pengguna aktif dengan hak administrasi keuangan.")

    with transaction.atomic():
        try:
            period = AccountingPeriod.objects.select_for_update().get(pk=period_id)
        except AccountingPeriod.DoesNotExist as exc:
            raise PeriodNotFoundError("Periode akuntansi tidak ditemukan.") from exc

        if period.status != PeriodStatus.OPEN:
            raise PeriodClosedError("Periode akuntansi sudah ditutup.")
        period.status = PeriodStatus.CLOSED
        period.close_requested_by = users[maker_id]
        period.closed_by = users[checker_id]
        period.closed_at = timezone.now()
        period.save(
            update_fields=["status", "close_requested_by", "closed_by", "closed_at"],
        )
        return period
