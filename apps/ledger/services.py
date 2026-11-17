from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

Rupiah = int


@dataclass(frozen=True)
class JournalLine:
    account_id: int
    debit: Rupiah
    credit: Rupiah


@dataclass(frozen=True)
class Journal:
    entity_id: int
    business_date: str
    source_type: str
    source_id: str
    lines: Iterable[JournalLine]


def post(journal: Journal) -> None:
    """Satu-satunya jalur tulis ke ledger. Validasi keseimbangan di sini."""
    total_debit = sum(line.debit for line in journal.lines)
    total_credit = sum(line.credit for line in journal.lines)
    if total_debit != total_credit:
        raise ValueError("jurnal tidak seimbang: debit != credit")
    if total_debit <= 0:
        raise ValueError("nominal jurnal harus > 0")
    # TODO: persist ke DB dalam transaksi (implementasi repository).