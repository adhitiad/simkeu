from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction

from apps.ledger.models import Account, AccountingPeriod, JournalEntry, JournalLineRecord, PeriodStatus
from apps.ledger.services import (
    DuplicateJournalError,
    InvalidJournalError,
    Journal,
    JournalLine,
    PeriodClosedError,
    close_period,
    post,
    validate_journal,
)


def _journal(
    account_debit: UUID,
    account_credit: UUID,
    *,
    source_id: str = "payment-001",
    debit: int = 100_000,
    credit: int = 100_000,
) -> Journal:
    return Journal(
        entity_id=10,
        business_date=date(2026, 11, 17),
        source_type="payment",
        source_id=source_id,
        description="Pembayaran mahasiswa",
        lines=[
            JournalLine(account_id=account_debit, debit=debit, credit=0),
            JournalLine(account_id=account_credit, debit=0, credit=credit),
        ],
    )


def _ledger_fixture() -> tuple[User, AccountingPeriod, Account, Account]:
    actor = User.objects.create_user(
        username=f"finance-{uuid4().hex[:10]}",
        password="test-password-only",
        is_staff=True,
    )
    cash = Account.objects.create(
        entity_id=10,
        code="1101",
        name="Kas Bank",
        account_type="asset",
        normal_balance="debit",
        created_by=actor,
    )
    receivable = Account.objects.create(
        entity_id=10,
        code="1201",
        name="Piutang Mahasiswa",
        account_type="asset",
        normal_balance="debit",
        created_by=actor,
    )
    period = AccountingPeriod.objects.create(
        entity_id=10,
        name="November 2026",
        starts_on=date(2026, 11, 1),
        ends_on=date(2026, 11, 30),
        created_by=actor,
    )
    return actor, period, cash, receivable


def test_journal_balanced() -> None:
    journal = _journal(uuid4(), uuid4())
    validate_journal(journal)


def test_journal_unbalanced_rejected() -> None:
    journal = _journal(uuid4(), uuid4(), debit=100_000, credit=50_000)
    with pytest.raises(InvalidJournalError):
        validate_journal(journal)


def test_journal_requires_integer_rupiah() -> None:
    journal = _journal(uuid4(), uuid4())
    invalid_line = JournalLine(
        account_id=journal.lines[0].account_id,
        debit=True,
        credit=0,
    )
    invalid = Journal(
        entity_id=journal.entity_id,
        business_date=journal.business_date,
        source_type=journal.source_type,
        source_id=journal.source_id,
        lines=[invalid_line, journal.lines[1]],
    )
    with pytest.raises(InvalidJournalError):
        validate_journal(invalid)


@pytest.mark.django_db
def test_post_persists_balanced_immutable_journal() -> None:
    actor, period, cash, receivable = _ledger_fixture()
    entry = post(_journal(cash.pk, receivable.pk), actor_id=actor.pk)

    lines = list(JournalLineRecord.objects.filter(entry=entry).order_by("line_number"))
    assert entry.period_id == period.pk
    assert len(lines) == 2
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines) == 100_000

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            JournalEntry.objects.filter(pk=entry.pk).update(description="diubah")


@pytest.mark.django_db
def test_post_is_idempotent_for_same_source_and_payload() -> None:
    actor, _, cash, receivable = _ledger_fixture()
    journal = _journal(cash.pk, receivable.pk)
    first = post(journal, actor_id=actor.pk)
    second = post(journal, actor_id=actor.pk)

    assert first.pk == second.pk
    assert JournalEntry.objects.count() == 1
    assert JournalLineRecord.objects.count() == 2


@pytest.mark.django_db
def test_same_source_with_different_payload_is_rejected() -> None:
    actor, _, cash, receivable = _ledger_fixture()
    post(_journal(cash.pk, receivable.pk), actor_id=actor.pk)

    changed = _journal(cash.pk, receivable.pk, debit=200_000, credit=200_000)
    with pytest.raises(DuplicateJournalError):
        post(changed, actor_id=actor.pk)


@pytest.mark.django_db
def test_post_to_closed_period_is_rejected() -> None:
    actor, period, cash, receivable = _ledger_fixture()
    period.status = PeriodStatus.CLOSED
    period.save(update_fields=["status"])

    with pytest.raises(PeriodClosedError):
        post(_journal(cash.pk, receivable.pk), actor_id=actor.pk)


@pytest.mark.django_db
def test_period_close_requires_two_distinct_staff_users() -> None:
    maker, period, _, _ = _ledger_fixture()
    checker = User.objects.create_user(
        username=f"checker-{uuid4().hex[:10]}",
        password="test-password-only",
        is_staff=True,
    )

    with pytest.raises(Exception):
        close_period(period.pk, maker_id=maker.pk, checker_id=maker.pk)

    closed = close_period(period.pk, maker_id=maker.pk, checker_id=checker.pk)
    assert closed.status == PeriodStatus.CLOSED
    assert closed.close_requested_by_id == maker.pk
    assert closed.closed_by_id == checker.pk
