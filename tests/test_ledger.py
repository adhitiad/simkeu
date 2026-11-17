import pytest

from apps.ledger.services import Journal, JournalLine, post


def _journal(debit: int, credit: int) -> Journal:
    return Journal(
        entity_id=1,
        business_date="2026-11-17",
        source_type="payment",
        source_id="p-1",
        lines=[
            JournalLine(account_id=1, debit=debit, credit=0),
            JournalLine(account_id=2, debit=0, credit=credit),
        ],
    )


def test_journal_balanced() -> None:
    post(_journal(100_000, 100_000))


def test_journal_unbalanced_rejected() -> None:
    with pytest.raises(ValueError):
        post(_journal(100_000, 50_000))