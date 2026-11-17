from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class FiscalYearStatus(models.TextChoices):
    OPEN = "open", "Terbuka"
    CLOSED = "closed", "Ditutup"


class BudgetPlanType(models.TextChoices):
    RKAT = "RKAT", "Rencana Kerja dan Anggaran Tahunan"
    RAPBU = "RAPBU", "Rencana Anggaran Pendapatan dan Belanja Universitas"
    APBU = "APBU", "Anggaran Pendapatan dan Belanja Universitas"


class BudgetPlanStatus(models.TextChoices):
    DRAFT = "draft", "Draf"
    SUBMITTED = "submitted", "Diajukan"
    REVIEW = "review", "Dalam review"
    APPROVED = "approved", "Disetujui"
    ACTIVE = "active", "Aktif"
    SUPERSEDED = "superseded", "Digantikan"
    REJECTED = "rejected", "Ditolak"


class AllocationStatus(models.TextChoices):
    ACTIVE = "active", "Aktif"
    SUPERSEDED = "superseded", "Digantikan"


class RevisionStatus(models.TextChoices):
    DRAFT = "draft", "Draf"
    SUBMITTED = "submitted", "Diajukan"
    VERIFIED = "verified", "Terverifikasi"
    EFFECTIVE = "effective", "Berlaku"
    REJECTED = "rejected", "Ditolak"


class CommitmentStatus(models.TextChoices):
    RESERVED = "reserved", "Dicadangkan"
    FULFILLED = "fulfilled", "Direalisasikan"
    RELEASED = "released", "Dilepaskan"


class FiscalYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=100)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(
        max_length=8,
        choices=FiscalYearStatus.choices,
        default=FiscalYearStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."fiscal_years"'
        ordering: ClassVar[list[str]] = ["-starts_on"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity_id", "code"],
                name="budget_fy_entity_code_uniq",
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="budget_fy_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in FiscalYearStatus]),
                name="budget_fy_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["entity_id", "status", "starts_on"], name="budget_fy_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.ends_on < self.starts_on:
            raise ValidationError(
                {"ends_on": "Tanggal akhir harus sama atau setelah tanggal mulai."}
            )
        overlapping = FiscalYear.objects.filter(
            entity_id=self.entity_id,
            starts_on__lte=self.ends_on,
            ends_on__gte=self.starts_on,
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError(
                "Tahun buku pada badan hukum yang sama tidak boleh tumpang tindih."
            )


class BudgetPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="plans",
    )
    unit_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    plan_type = models.CharField(max_length=8, choices=BudgetPlanType.choices)
    version = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=160)
    status = models.CharField(
        max_length=16,
        choices=BudgetPlanStatus.choices,
        default=BudgetPlanStatus.DRAFT,
    )
    notes = models.TextField(blank=True)
    previous_version = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="next_versions",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."budget_plans"'
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity_id", "fiscal_year", "plan_type", "unit_id", "version"],
                name="budget_plan_version_uniq",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=Q(plan_type__in=[choice.value for choice in BudgetPlanType]),
                name="budget_plan_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in BudgetPlanStatus]),
                name="budget_plan_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(plan_type=BudgetPlanType.RKAT, unit_id__isnull=False)
                    | Q(
                        plan_type__in=[BudgetPlanType.RAPBU, BudgetPlanType.APBU],
                        unit_id__isnull=True,
                    )
                ),
                name="budget_plan_scope_valid",
            ),
            models.UniqueConstraint(
                fields=["entity_id", "fiscal_year"],
                condition=Q(plan_type=BudgetPlanType.APBU, status=BudgetPlanStatus.ACTIVE),
                name="budget_one_active_apbu_uniq",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["entity_id", "fiscal_year", "plan_type", "status"],
                name="budget_plan_scope_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.plan_type} v{self.version} — {self.title}"

    def clean(self) -> None:
        super().clean()
        if self.fiscal_year_id and self.entity_id != self.fiscal_year.entity_id:
            raise ValidationError(
                {"fiscal_year": "Tahun buku harus berasal dari badan hukum yang sama."}
            )
        if self.plan_type == BudgetPlanType.RKAT and self.unit_id is None:
            raise ValidationError({"unit_id": "RKAT wajib memiliki unit penanggung jawab."})
        if self.plan_type != BudgetPlanType.RKAT and self.unit_id is not None:
            raise ValidationError(
                {"unit_id": "RAPBU/APBU merupakan dokumen konsolidasi tingkat entitas."}
            )


class BudgetLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    plan = models.ForeignKey(BudgetPlan, on_delete=models.PROTECT, related_name="lines")
    line_number = models.PositiveSmallIntegerField()
    unit_id = models.PositiveBigIntegerField(db_index=True)
    account_id = models.UUIDField()
    program_code = models.CharField(max_length=40, blank=True)
    funding_source = models.CharField(max_length=40)
    description = models.CharField(max_length=500)
    objective = models.CharField(max_length=500, blank=True)
    output = models.CharField(max_length=500, blank=True)
    indicator = models.CharField(max_length=255, blank=True)
    schedule_start = models.DateField(null=True, blank=True)
    schedule_end = models.DateField(null=True, blank=True)
    amount = models.PositiveBigIntegerField()
    is_restricted = models.BooleanField(default=False)
    restriction_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."budget_lines"'
        ordering: ClassVar[list[str]] = ["line_number"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["plan", "line_number"], name="budget_line_number_uniq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="budget_line_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(schedule_start__isnull=True, schedule_end__isnull=True)
                    | Q(
                        schedule_start__isnull=False,
                        schedule_end__isnull=False,
                        schedule_end__gte=models.F("schedule_start"),
                    )
                ),
                name="budget_line_schedule_valid",
            ),
            models.CheckConstraint(
                condition=Q(is_restricted=False) | ~Q(restriction_note=""),
                name="budget_line_restriction_note_ck",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["entity_id", "unit_id", "plan"], name="budget_line_scope_idx"),
            models.Index(fields=["account_id"], name="budget_line_account_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.line_number}. {self.description}"

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.entity_id != self.plan.entity_id:
            raise ValidationError(
                {"plan": "Baris anggaran harus berada pada badan hukum yang sama."}
            )
        if (
            self.plan_id
            and self.plan.plan_type == BudgetPlanType.RKAT
            and self.unit_id != self.plan.unit_id
        ):
            raise ValidationError(
                {"unit_id": "Unit baris RKAT harus sama dengan unit pemilik RKAT."}
            )
        if self.is_restricted and not self.restriction_note.strip():
            raise ValidationError(
                {"restriction_note": "Tujuan dan syarat dana terikat wajib dicantumkan."}
            )
        if self.schedule_start and self.schedule_end and self.schedule_end < self.schedule_start:
            raise ValidationError(
                {"schedule_end": "Tanggal akhir kegiatan tidak boleh sebelum tanggal mulai."}
            )


class BudgetAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    budget_line = models.OneToOneField(
        BudgetLine,
        on_delete=models.PROTECT,
        related_name="allocation",
    )
    unit_id = models.PositiveBigIntegerField(db_index=True)
    account_id = models.UUIDField()
    funding_source = models.CharField(max_length=40)
    allocated_amount = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=12,
        choices=AllocationStatus.choices,
        default=AllocationStatus.ACTIVE,
    )
    effective_from = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."pagu_allocations"'
        ordering: ClassVar[list[str]] = ["unit_id", "account_id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(allocated_amount__gte=0),
                name="budget_pagu_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in AllocationStatus]),
                name="budget_pagu_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["entity_id", "fiscal_year", "status"],
                name="budget_pagu_scope_idx",
            ),
            models.Index(fields=["unit_id", "status"], name="budget_pagu_unit_idx"),
        ]

    def __str__(self) -> str:
        return f"Pagu {self.unit_id}: Rp{self.allocated_amount}"


class BudgetRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    status = models.CharField(
        max_length=12,
        choices=RevisionStatus.choices,
        default=RevisionStatus.DRAFT,
    )
    reason = models.TextField()
    effective_date = models.DateField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."budget_revisions"'
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in RevisionStatus]),
                name="budget_revision_status_valid",
            ),
            models.CheckConstraint(condition=~Q(reason=""), name="budget_revision_reason_ck"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["entity_id", "fiscal_year", "status"],
                name="budget_revision_scope_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Revisi {self.id}"


class BudgetRevisionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    revision = models.ForeignKey(
        BudgetRevision,
        on_delete=models.PROTECT,
        related_name="items",
    )
    allocation = models.ForeignKey(
        BudgetAllocation,
        on_delete=models.PROTECT,
        related_name="revision_items",
    )
    previous_amount = models.PositiveBigIntegerField()
    requested_amount = models.PositiveBigIntegerField()
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."budget_revision_items"'
        ordering: ClassVar[list[str]] = ["created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["revision", "allocation"],
                name="budget_revision_alloc_uniq",
            ),
            models.CheckConstraint(
                condition=Q(requested_amount__gte=0),
                name="budget_revision_amount_nonnegative",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["entity_id", "allocation"], name="budget_revision_item_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"Revisi {self.revision_id}: pagu {self.allocation_id}"


class BudgetCommitment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    allocation = models.ForeignKey(
        BudgetAllocation,
        on_delete=models.PROTECT,
        related_name="commitments",
    )
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=128)
    description = models.CharField(max_length=500)
    amount = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=12,
        choices=CommitmentStatus.choices,
        default=CommitmentStatus.RESERVED,
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = '"budget"."budget_commitments"'
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity_id", "source_type", "source_id"],
                name="budget_commitment_source_uniq",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="budget_commitment_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[choice.value for choice in CommitmentStatus]),
                name="budget_commitment_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=CommitmentStatus.RELEASED,
                        released_by__isnull=False,
                        released_at__isnull=False,
                    )
                    | ~Q(status=CommitmentStatus.RELEASED)
                ),
                name="budget_commitment_release_meta_ck",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["allocation", "status"], name="budget_commit_alloc_status_idx"),
            models.Index(fields=["entity_id", "created_at"], name="budget_commit_entity_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id} — Rp{self.amount}"
