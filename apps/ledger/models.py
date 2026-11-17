from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class AccountType(models.TextChoices):
    ASSET = "asset", "Aset"
    LIABILITY = "liability", "Liabilitas"
    NET_ASSETS = "net_assets", "Aset Neto"
    REVENUE = "revenue", "Pendapatan"
    EXPENSE = "expense", "Beban"


class NormalBalance(models.TextChoices):
    DEBIT = "debit", "Debit"
    CREDIT = "credit", "Kredit"


class PeriodStatus(models.TextChoices):
    OPEN = "open", "Terbuka"
    CLOSED = "closed", "Ditutup"


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    normal_balance = models.CharField(max_length=6, choices=NormalBalance.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"ledger"."accounts"'
        ordering: ClassVar[list[str]] = ["entity_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["entity_id", "code"], name="ledger_account_entity_code_uniq"),
            models.CheckConstraint(
                condition=Q(account_type__in=[choice.value for choice in AccountType]),
                name="ledger_account_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(normal_balance__in=[choice.value for choice in NormalBalance]),
                name="ledger_account_balance_valid",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.parent_id and self.parent.entity_id != self.entity_id:
            raise ValidationError({"parent": "Akun induk harus berasal dari entitas yang sama."})

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class AccountingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    name = models.CharField(max_length=64)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(
        max_length=8,
        choices=PeriodStatus.choices,
        default=PeriodStatus.OPEN,
    )
    close_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"ledger"."accounting_periods"'
        ordering: ClassVar[list[str]] = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["entity_id", "name"], name="ledger_period_entity_name_uniq"),
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")),
                name="ledger_period_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in PeriodStatus]),
                name="ledger_period_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["entity_id", "status", "starts_on"], name="ledger_period_scope_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Tanggal akhir tidak boleh sebelum tanggal mulai."})
        if self.entity_id and self.starts_on and self.ends_on:
            overlapping = AccountingPeriod.objects.filter(
                entity_id=self.entity_id,
                starts_on__lte=self.ends_on,
                ends_on__gte=self.starts_on,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("Periode akuntansi tidak boleh saling tumpang tindih.")

    def __str__(self) -> str:
        return self.name


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    period = models.ForeignKey(
        AccountingPeriod,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    business_date = models.DateField()
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=128)
    description = models.CharField(max_length=500, blank=True)
    posted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"ledger"."journal_entries"'
        ordering: ClassVar[list[str]] = ["-business_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity_id", "source_type", "source_id"],
                name="ledger_journal_source_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["entity_id", "business_date", "id"],
                name="ledger_jrnl_ent_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.business_date} · {self.source_type}:{self.source_id}"


class JournalLineRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    line_number = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255, blank=True)
    debit = models.PositiveBigIntegerField(default=0)
    credit = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"ledger"."journal_lines"'
        ordering: ClassVar[list[str]] = ["line_number"]
        constraints = [
            models.UniqueConstraint(fields=["entry", "line_number"], name="ledger_line_number_uniq"),
            models.CheckConstraint(
                condition=Q(debit__gt=0, credit=0) | Q(debit=0, credit__gt=0),
                name="ledger_line_one_sided_amount",
            ),
        ]
        indexes = [
            models.Index(fields=["entity_id", "entry"], name="ledger_line_ent_entry_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.entry_id} · {self.line_number}"
