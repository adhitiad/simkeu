from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import cast
from uuid import UUID

from django.db.models import Sum

from .models import Account, JournalLineRecord


class InvalidTrialBalanceRequest(ValueError):
    """The trial balance request has invalid scope or date values."""


@dataclass(frozen=True, slots=True)
class TrialBalanceAccount:
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    debit_activity: int
    credit_activity: int
    closing_debit: int
    closing_credit: int


@dataclass(frozen=True, slots=True)
class TrialBalance:
    entity_id: int
    as_of: date
    accounts: tuple[TrialBalanceAccount, ...]
    total_debit_activity: int
    total_credit_activity: int
    total_closing_debit: int
    total_closing_credit: int
    is_balanced: bool


def build_trial_balance(*, entity_id: int, as_of: date) -> TrialBalance:
    """
    Calculate account balances from all posted journals through as_of.

    Opening balances must be represented by posted opening journals. Values
    are integer Rupiah and each account is included, even with zero activity.
    """
    if not isinstance(entity_id, int) or isinstance(entity_id, bool) or entity_id <= 0:
        raise InvalidTrialBalanceRequest("entity_id harus berupa integer positif.")
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise InvalidTrialBalanceRequest("as_of harus berupa tanggal.")

    grouped = (
        JournalLineRecord.objects.filter(
            entity_id=entity_id,
            entry__entity_id=entity_id,
            entry__business_date__lte=as_of,
        )
        .values("account_id")
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
    )
    balances: dict[UUID, tuple[int, int]] = {
        cast(UUID, row["account_id"]): (
            int(row["debit_total"] or 0),
            int(row["credit_total"] or 0),
        )
        for row in grouped
    }

    rows: list[TrialBalanceAccount] = []
    for account in Account.objects.filter(entity_id=entity_id).order_by("code"):
        debit_activity, credit_activity = balances.get(account.pk, (0, 0))
        net_balance = debit_activity - credit_activity
        rows.append(
            TrialBalanceAccount(
                account_id=account.pk,
                account_code=account.code,
                account_name=account.name,
                account_type=account.account_type,
                normal_balance=account.normal_balance,
                debit_activity=debit_activity,
                credit_activity=credit_activity,
                closing_debit=max(net_balance, 0),
                closing_credit=max(-net_balance, 0),
            )
        )

    total_debit_activity = sum(row.debit_activity for row in rows)
    total_credit_activity = sum(row.credit_activity for row in rows)
    total_closing_debit = sum(row.closing_debit for row in rows)
    total_closing_credit = sum(row.closing_credit for row in rows)

    return TrialBalance(
        entity_id=entity_id,
        as_of=as_of,
        accounts=tuple(rows),
        total_debit_activity=total_debit_activity,
        total_credit_activity=total_credit_activity,
        total_closing_debit=total_closing_debit,
        total_closing_credit=total_closing_credit,
        is_balanced=(
            total_debit_activity == total_credit_activity
            and total_closing_debit == total_closing_credit
        ),
    )
