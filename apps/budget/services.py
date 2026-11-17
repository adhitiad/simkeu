from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date
from typing import Final
from uuid import UUID

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ledger.models import Account
from apps.platform_app.models import Entity, OrganizationalUnit, OutboxEvent
from apps.platform_app.services import record_audit, require_permission

from .models import (
    AllocationStatus,
    BudgetAllocation,
    BudgetCommitment,
    BudgetLine,
    BudgetPlan,
    BudgetPlanStatus,
    BudgetPlanType,
    BudgetRevision,
    BudgetRevisionItem,
    CommitmentStatus,
    FiscalYear,
    FiscalYearStatus,
    RevisionStatus,
)

ACTIVE_COMMITMENT_STATUSES: Final[tuple[str, ...]] = (
    CommitmentStatus.RESERVED,
    CommitmentStatus.FULFILLED,
)
MAX_REVISION_ITEMS: Final[int] = 100


class BudgetError(Exception):
    """Base exception for budget domain operations."""


class BudgetNotFoundError(BudgetError):
    """A requested budget resource does not exist in the actor's scope."""


class BudgetStateError(BudgetError):
    """The requested state transition is not allowed."""


class BudgetValidationError(BudgetError):
    """The budget input violates a domain invariant."""


class BudgetInsufficientPaguError(BudgetError):
    """The requested commitment or revision exceeds available pagu."""


class BudgetDuplicateSourceError(BudgetError):
    """An idempotency source key was reused with different data."""


class BudgetMakerCheckerError(BudgetError):
    """A sensitive financial operation was approved by its maker."""


def _actor(actor_id: int) -> User:
    actor = User.objects.filter(pk=actor_id, is_active=True).first()
    if actor is None:
        raise BudgetNotFoundError("Pengguna aktif tidak ditemukan.")
    return actor


def _require(
    actor: User,
    permission: str,
    *,
    entity_id: int,
    unit_id: int | None = None,
) -> None:
    require_permission(
        actor,
        permission,
        entity_id=entity_id,
        unit_id=unit_id,
    )


def _audit(
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: UUID,
    entity_id: int,
    unit_id: int | None = None,
    after_state: dict[str, object],
) -> None:
    record_audit(
        actor=actor,
        action=f"budget.{action}",
        target_type=target_type,
        target_id=str(target_id),
        entity_id=entity_id,
        unit_id=unit_id,
        after_state=after_state,
    )
    OutboxEvent.objects.create(
        event_id=uuid.uuid7(),
        event_type=f"budget.{action}.v1",
        version=1,
        payload={
            "target_type": target_type,
            "target_id": str(target_id),
            "entity_id": entity_id,
            "unit_id": unit_id,
            "actor_id": actor.pk,
            **after_state,
        },
    )


def _line_unit_ids(plan: BudgetPlan) -> list[int]:
    return list(plan.lines.order_by("unit_id").values_list("unit_id", flat=True).distinct())


def _require_plan_scope(actor: User, permission: str, plan: BudgetPlan) -> None:
    if plan.unit_id is not None:
        _require(actor, permission, entity_id=plan.entity_id, unit_id=plan.unit_id)
        return
    units = _line_unit_ids(plan)
    if not units:
        _require(actor, permission, entity_id=plan.entity_id)
        return
    for unit_id in units:
        _require(actor, permission, entity_id=plan.entity_id, unit_id=unit_id)


def create_fiscal_year(
    *,
    actor_id: int,
    entity_id: int,
    code: str,
    name: str,
    starts_on: date,
    ends_on: date,
) -> FiscalYear:
    actor = _actor(actor_id)
    _require(actor, "budget.fiscal_year.manage", entity_id=entity_id)
    if not code.strip() or len(code) > 16 or not name.strip() or len(name) > 100:
        raise BudgetValidationError("Kode (maks. 16) dan nama tahun buku (maks. 100) wajib diisi.")
    fiscal_year = FiscalYear(
        entity_id=entity_id,
        code=code.strip(),
        name=name.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        created_by=actor,
    )
    try:
        with transaction.atomic():
            entity = (
                Entity.objects.select_for_update()
                .filter(
                    pk=entity_id,
                    is_active=True,
                )
                .first()
            )
            if entity is None:
                raise BudgetNotFoundError("Badan hukum tidak ditemukan atau tidak aktif.")
            fiscal_year.full_clean()
            fiscal_year.save()
            _audit(
                actor=actor,
                action="fiscal_year.created",
                target_type="FiscalYear",
                target_id=fiscal_year.pk,
                entity_id=entity_id,
                after_state={
                    "code": fiscal_year.code,
                    "starts_on": starts_on.isoformat(),
                    "ends_on": ends_on.isoformat(),
                },
            )
    except ValidationError as exc:
        raise BudgetValidationError("; ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise BudgetValidationError(
            "Kode tahun buku sudah digunakan atau tanggalnya bentrok."
        ) from exc
    return fiscal_year


def create_plan(
    *,
    actor_id: int,
    entity_id: int,
    fiscal_year_id: UUID,
    plan_type: str,
    title: str,
    unit_id: int | None = None,
    notes: str = "",
) -> BudgetPlan:
    actor = _actor(actor_id)
    if plan_type not in BudgetPlanType.values:
        raise BudgetValidationError("Jenis dokumen anggaran tidak dikenal.")
    if plan_type != BudgetPlanType.RKAT:
        raise BudgetValidationError(
            "RAPBU dibuat melalui konsolidasi RKAT disetujui; APBU dibuat dari RAPBU disetujui."
        )
    if not title.strip() or len(title) > 160:
        raise BudgetValidationError("Judul wajib diisi dan maksimal 160 karakter.")
    if plan_type == BudgetPlanType.RKAT and unit_id is None:
        raise BudgetValidationError("RKAT wajib memiliki unit penanggung jawab.")
    _require(
        actor,
        "budget.plan.create",
        entity_id=entity_id,
        unit_id=unit_id,
    )
    with transaction.atomic():
        fiscal_year = (
            FiscalYear.objects.select_for_update()
            .filter(
                pk=fiscal_year_id,
                entity_id=entity_id,
                status=FiscalYearStatus.OPEN,
            )
            .first()
        )
        if fiscal_year is None:
            raise BudgetNotFoundError(
                "Tahun buku tidak ditemukan, tidak aktif, atau di luar entitas."
            )
        latest_version = (
            BudgetPlan.objects.select_for_update()
            .filter(
                entity_id=entity_id,
                fiscal_year=fiscal_year,
                plan_type=plan_type,
                unit_id=unit_id,
            )
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        plan = BudgetPlan.objects.create(
            entity_id=entity_id,
            fiscal_year=fiscal_year,
            unit_id=unit_id,
            plan_type=plan_type,
            version=(latest_version or 0) + 1,
            title=title.strip(),
            notes=notes.strip(),
            created_by=actor,
        )
        _audit(
            actor=actor,
            action="plan.created",
            target_type="BudgetPlan",
            target_id=plan.pk,
            entity_id=entity_id,
            unit_id=unit_id,
            after_state={
                "plan_type": plan_type,
                "version": plan.version,
                "fiscal_year_id": str(fiscal_year.pk),
                "title": plan.title,
            },
        )
    return plan


def add_budget_line(
    *,
    actor_id: int,
    plan_id: UUID,
    unit_id: int,
    account_id: UUID,
    funding_source: str,
    description: str,
    amount: int,
    program_code: str = "",
    objective: str = "",
    output: str = "",
    indicator: str = "",
    schedule_start: date | None = None,
    schedule_end: date | None = None,
    is_restricted: bool = False,
    restriction_note: str = "",
) -> BudgetLine:
    actor = _actor(actor_id)
    with transaction.atomic():
        plan = (
            BudgetPlan.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(pk=plan_id)
            .first()
        )
        if plan is None:
            raise BudgetNotFoundError("Dokumen anggaran tidak ditemukan.")
        if plan.fiscal_year.status != FiscalYearStatus.OPEN:
            raise BudgetStateError("Tahun buku sudah ditutup; rincian RKAT tidak dapat diubah.")
        _require(actor, "budget.line.create", entity_id=plan.entity_id, unit_id=unit_id)
        if plan.status != BudgetPlanStatus.DRAFT:
            raise BudgetStateError("Baris hanya dapat ditambahkan pada dokumen berstatus draf.")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise BudgetValidationError("Nominal wajib berupa integer Rupiah lebih besar dari nol.")
        if not funding_source.strip() or len(funding_source) > 40:
            raise BudgetValidationError("Sumber dana wajib diisi (maksimal 40 karakter).")
        if not description.strip() or len(description) > 500:
            raise BudgetValidationError("Uraian wajib diisi (maksimal 500 karakter).")

        unit = OrganizationalUnit.objects.filter(
            pk=unit_id,
            entity_id=plan.entity_id,
            is_active=True,
        ).first()
        if unit is None:
            raise BudgetNotFoundError("Unit anggaran tidak ditemukan atau tidak aktif.")
        if plan.unit_id is not None and plan.unit_id != unit.pk:
            raise BudgetValidationError("Unit baris tidak sama dengan unit pemilik RKAT.")
        account = Account.objects.filter(
            pk=account_id,
            entity_id=plan.entity_id,
            is_active=True,
        ).first()
        if account is None:
            raise BudgetNotFoundError(
                "Akun COA tidak ditemukan, tidak aktif, atau di luar entitas."
            )
        line_number = (
            BudgetLine.objects.filter(plan=plan)
            .order_by("-line_number")
            .values_list("line_number", flat=True)
            .first()
            or 0
        ) + 1
        line = BudgetLine(
            entity_id=plan.entity_id,
            plan=plan,
            line_number=line_number,
            unit_id=unit.pk,
            account_id=account.pk,
            program_code=program_code.strip(),
            funding_source=funding_source.strip(),
            description=description.strip(),
            objective=objective.strip(),
            output=output.strip(),
            indicator=indicator.strip(),
            schedule_start=schedule_start,
            schedule_end=schedule_end,
            amount=amount,
            is_restricted=is_restricted,
            restriction_note=restriction_note.strip(),
            created_by=actor,
        )
        try:
            line.full_clean()
            line.save()
        except ValidationError as exc:
            raise BudgetValidationError("; ".join(exc.messages)) from exc
        _audit(
            actor=actor,
            action="line.created",
            target_type="BudgetLine",
            target_id=line.pk,
            entity_id=plan.entity_id,
            unit_id=unit.pk,
            after_state={
                "plan_id": str(plan.pk),
                "account_id": str(account.pk),
                "funding_source": line.funding_source,
                "amount": amount,
                "line_number": line_number,
            },
        )
        return line


def submit_plan(*, actor_id: int, plan_id: UUID) -> BudgetPlan:
    actor = _actor(actor_id)
    with transaction.atomic():
        plan = (
            BudgetPlan.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(pk=plan_id)
            .first()
        )
        if plan is None:
            raise BudgetNotFoundError("Dokumen anggaran tidak ditemukan.")
        if plan.fiscal_year.status != FiscalYearStatus.OPEN:
            raise BudgetStateError("Tahun buku sudah ditutup; dokumen tidak dapat diajukan.")
        _require_plan_scope(actor, "budget.plan.submit", plan)
        if plan.status != BudgetPlanStatus.DRAFT:
            raise BudgetStateError("Hanya dokumen draf yang dapat diajukan.")
        if not plan.lines.exists():
            raise BudgetValidationError("Dokumen harus memiliki minimal satu baris anggaran.")
        plan.status = BudgetPlanStatus.SUBMITTED
        plan.submitted_by = actor
        plan.submitted_at = timezone.now()
        plan.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        _audit(
            actor=actor,
            action="plan.submitted",
            target_type="BudgetPlan",
            target_id=plan.pk,
            entity_id=plan.entity_id,
            unit_id=plan.unit_id,
            after_state={"status": plan.status},
        )
        return plan


def review_plan(*, actor_id: int, plan_id: UUID) -> BudgetPlan:
    actor = _actor(actor_id)
    with transaction.atomic():
        plan = BudgetPlan.objects.select_for_update().filter(pk=plan_id).first()
        if plan is None:
            raise BudgetNotFoundError("Dokumen anggaran tidak ditemukan.")
        _require_plan_scope(actor, "budget.plan.review", plan)
        if plan.status != BudgetPlanStatus.SUBMITTED:
            raise BudgetStateError("Dokumen harus berstatus diajukan sebelum direview.")
        if plan.created_by_id == actor.pk or plan.submitted_by_id == actor.pk:
            raise BudgetMakerCheckerError("Pembuat/pengaju dokumen tidak boleh melakukan review.")
        plan.status = BudgetPlanStatus.REVIEW
        plan.reviewed_by = actor
        plan.reviewed_at = timezone.now()
        plan.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        _audit(
            actor=actor,
            action="plan.reviewed",
            target_type="BudgetPlan",
            target_id=plan.pk,
            entity_id=plan.entity_id,
            unit_id=plan.unit_id,
            after_state={"status": plan.status},
        )
        return plan


def approve_plan(*, actor_id: int, plan_id: UUID) -> BudgetPlan:
    actor = _actor(actor_id)
    with transaction.atomic():
        plan = (
            BudgetPlan.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(pk=plan_id)
            .first()
        )
        if plan is None:
            raise BudgetNotFoundError("Dokumen anggaran tidak ditemukan.")
        _require_plan_scope(actor, "budget.plan.approve", plan)
        if plan.fiscal_year.status != FiscalYearStatus.OPEN:
            raise BudgetStateError("Tahun buku sudah ditutup; dokumen tidak dapat disetujui.")
        if plan.status != BudgetPlanStatus.REVIEW:
            raise BudgetStateError("Dokumen harus selesai direview sebelum disetujui.")
        if (
            plan.created_by_id == actor.pk
            or plan.submitted_by_id == actor.pk
            or plan.reviewed_by_id == actor.pk
        ):
            raise BudgetMakerCheckerError(
                "Pembuat, pengaju, atau reviewer tidak boleh menyetujui dokumen."
            )
        lines = list(plan.lines.order_by("unit_id", "line_number"))
        if not lines:
            raise BudgetValidationError("Dokumen tidak memiliki baris anggaran.")

        if plan.plan_type == BudgetPlanType.APBU:
            current = list(
                BudgetPlan.objects.select_for_update().filter(
                    entity_id=plan.entity_id,
                    fiscal_year=plan.fiscal_year,
                    plan_type=BudgetPlanType.APBU,
                    status=BudgetPlanStatus.ACTIVE,
                )
            )
            for old_plan in current:
                has_open_commitments = BudgetAllocation.objects.filter(
                    budget_line__plan=old_plan,
                    commitments__status__in=ACTIVE_COMMITMENT_STATUSES,
                ).exists()
                if has_open_commitments:
                    raise BudgetStateError(
                        "APBU aktif masih memiliki komitmen. Gunakan revisi pagu agar "
                        "histori dan komitmen tetap terjaga."
                    )
            for old_plan in current:
                old_plan.status = BudgetPlanStatus.SUPERSEDED
                old_plan.save(update_fields=["status", "updated_at"])
                BudgetAllocation.objects.filter(
                    budget_line__plan=old_plan,
                    status=AllocationStatus.ACTIVE,
                ).update(status=AllocationStatus.SUPERSEDED, updated_at=timezone.now())

            for line in lines:
                BudgetAllocation.objects.create(
                    entity_id=plan.entity_id,
                    fiscal_year=plan.fiscal_year,
                    budget_line=line,
                    unit_id=line.unit_id,
                    account_id=line.account_id,
                    funding_source=line.funding_source,
                    allocated_amount=line.amount,
                    status=AllocationStatus.ACTIVE,
                    effective_from=plan.fiscal_year.starts_on,
                    created_by=actor,
                )
            plan.status = BudgetPlanStatus.ACTIVE
            plan.effective_at = timezone.now()
        else:
            plan.status = BudgetPlanStatus.APPROVED

        plan.approved_by = actor
        plan.approved_at = timezone.now()
        plan.save(
            update_fields=["status", "approved_by", "approved_at", "effective_at", "updated_at"]
        )
        _audit(
            actor=actor,
            action="plan.approved",
            target_type="BudgetPlan",
            target_id=plan.pk,
            entity_id=plan.entity_id,
            unit_id=plan.unit_id,
            after_state={
                "status": plan.status,
                "plan_type": plan.plan_type,
                "line_count": len(lines),
                "effective_at": plan.effective_at.isoformat() if plan.effective_at else None,
            },
        )
        return plan


def consolidate_rkat_into_rapbu(
    *,
    actor_id: int,
    entity_id: int,
    fiscal_year_id: UUID,
    title: str,
) -> BudgetPlan:
    actor = _actor(actor_id)
    _require(actor, "budget.plan.create", entity_id=entity_id)

    with transaction.atomic():
        fiscal_year = (
            FiscalYear.objects.select_for_update()
            .filter(
                pk=fiscal_year_id,
                entity_id=entity_id,
                status=FiscalYearStatus.OPEN,
            )
            .first()
        )
        if fiscal_year is None:
            raise BudgetNotFoundError("Tahun buku tidak ditemukan atau tidak aktif.")

        candidates = (
            BudgetPlan.objects.filter(
                entity_id=entity_id,
                fiscal_year=fiscal_year,
                plan_type=BudgetPlanType.RKAT,
                status=BudgetPlanStatus.APPROVED,
            )
            .prefetch_related("lines")
            .order_by("unit_id", "-version")
        )
        latest_by_unit: dict[int, BudgetPlan] = {}
        for candidate in candidates:
            if candidate.unit_id is not None and candidate.unit_id not in latest_by_unit:
                latest_by_unit[candidate.unit_id] = candidate
        if not latest_by_unit:
            raise BudgetValidationError(
                "Belum ada RKAT unit berstatus disetujui untuk dikonsolidasikan."
            )

        latest_version = (
            BudgetPlan.objects.filter(
                entity_id=entity_id,
                fiscal_year=fiscal_year,
                plan_type=BudgetPlanType.RAPBU,
                unit_id__isnull=True,
            )
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or 0
        )
        rapbu = BudgetPlan.objects.create(
            entity_id=entity_id,
            fiscal_year=fiscal_year,
            plan_type=BudgetPlanType.RAPBU,
            version=latest_version + 1,
            title=title.strip()[:160] or f"RAPBU {fiscal_year.code}",
            created_by=actor,
        )
        line_number = 1
        copied_lines: list[BudgetLine] = []
        for source_plan in latest_by_unit.values():
            for source in source_plan.lines.all():
                copied_lines.append(
                    BudgetLine(
                        entity_id=entity_id,
                        plan=rapbu,
                        line_number=line_number,
                        unit_id=source.unit_id,
                        account_id=source.account_id,
                        program_code=source.program_code,
                        funding_source=source.funding_source,
                        description=source.description,
                        objective=source.objective,
                        output=source.output,
                        indicator=source.indicator,
                        schedule_start=source.schedule_start,
                        schedule_end=source.schedule_end,
                        amount=source.amount,
                        is_restricted=source.is_restricted,
                        restriction_note=source.restriction_note,
                        created_by=actor,
                    )
                )
                line_number += 1
        BudgetLine.objects.bulk_create(copied_lines, batch_size=500)
        _audit(
            actor=actor,
            action="rapbu.consolidated",
            target_type="BudgetPlan",
            target_id=rapbu.pk,
            entity_id=entity_id,
            after_state={
                "plan_type": BudgetPlanType.RAPBU,
                "version": rapbu.version,
                "source_rkat_count": len(latest_by_unit),
                "line_count": len(copied_lines),
            },
        )
        return rapbu


def create_apbu_from_rapbu(
    *,
    actor_id: int,
    rapbu_id: UUID,
    title: str = "",
) -> BudgetPlan:
    actor = _actor(actor_id)
    source = (
        BudgetPlan.objects.select_related("fiscal_year")
        .filter(
            pk=rapbu_id,
            plan_type=BudgetPlanType.RAPBU,
            status=BudgetPlanStatus.APPROVED,
            fiscal_year__status=FiscalYearStatus.OPEN,
        )
        .first()
    )
    if source is None:
        raise BudgetNotFoundError("RAPBU disetujui pada tahun buku terbuka tidak ditemukan.")
    _require(actor, "budget.plan.create", entity_id=source.entity_id)

    with transaction.atomic():
        fiscal_year = (
            FiscalYear.objects.select_for_update()
            .filter(
                pk=source.fiscal_year_id,
                entity_id=source.entity_id,
                status=FiscalYearStatus.OPEN,
            )
            .first()
        )
        if fiscal_year is None:
            raise BudgetStateError("Tahun buku RAPBU sudah ditutup.")
        source = (
            BudgetPlan.objects.select_for_update()
            .select_related("fiscal_year")
            .prefetch_related("lines")
            .filter(
                pk=rapbu_id,
                plan_type=BudgetPlanType.RAPBU,
                status=BudgetPlanStatus.APPROVED,
                fiscal_year=fiscal_year,
            )
            .first()
        )
        if source is None:
            raise BudgetStateError("RAPBU tidak lagi berstatus disetujui.")

        latest_version = (
            BudgetPlan.objects.filter(
                entity_id=source.entity_id,
                fiscal_year=fiscal_year,
                plan_type=BudgetPlanType.APBU,
                unit_id__isnull=True,
            )
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or 0
        )
        apbu = BudgetPlan.objects.create(
            entity_id=source.entity_id,
            fiscal_year=fiscal_year,
            plan_type=BudgetPlanType.APBU,
            version=latest_version + 1,
            title=title.strip()[:160] or f"APBU {fiscal_year.code}",
            notes=f"Dibentuk dari RAPBU {source.pk}",
            previous_version=source,
            created_by=actor,
        )
        copied = [
            BudgetLine(
                entity_id=source.entity_id,
                plan=apbu,
                line_number=line.line_number,
                unit_id=line.unit_id,
                account_id=line.account_id,
                program_code=line.program_code,
                funding_source=line.funding_source,
                description=line.description,
                objective=line.objective,
                output=line.output,
                indicator=line.indicator,
                schedule_start=line.schedule_start,
                schedule_end=line.schedule_end,
                amount=line.amount,
                is_restricted=line.is_restricted,
                restriction_note=line.restriction_note,
                created_by=actor,
            )
            for line in source.lines.all()
        ]
        BudgetLine.objects.bulk_create(copied, batch_size=500)
        _audit(
            actor=actor,
            action="apbu.created_from_rapbu",
            target_type="BudgetPlan",
            target_id=apbu.pk,
            entity_id=source.entity_id,
            after_state={
                "plan_type": BudgetPlanType.APBU,
                "version": apbu.version,
                "source_rapbu_id": str(source.pk),
                "line_count": len(copied),
            },
        )
        return apbu


def create_revision(
    *,
    actor_id: int,
    entity_id: int,
    fiscal_year_id: UUID,
    reason: str,
    effective_date: date,
    requested_amounts: Mapping[UUID, int],
) -> BudgetRevision:
    actor = _actor(actor_id)
    if not reason.strip() or len(reason.strip()) < 8:
        raise BudgetValidationError("Alasan revisi wajib diisi minimal 8 karakter.")
    if not requested_amounts or len(requested_amounts) > MAX_REVISION_ITEMS:
        raise BudgetValidationError(f"Revisi harus memiliki 1-{MAX_REVISION_ITEMS} baris pagu.")
    with transaction.atomic():
        fiscal_year = (
            FiscalYear.objects.select_for_update()
            .filter(
                pk=fiscal_year_id,
                entity_id=entity_id,
                status=FiscalYearStatus.OPEN,
            )
            .first()
        )
        if fiscal_year is None:
            raise BudgetNotFoundError("Tahun buku tidak ditemukan atau tidak aktif.")
        if not fiscal_year.starts_on <= effective_date <= fiscal_year.ends_on:
            raise BudgetValidationError("Tanggal efektif revisi harus berada di dalam tahun buku.")
        allocation_ids = sorted(requested_amounts, key=str)
        allocations = list(
            BudgetAllocation.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(
                pk__in=allocation_ids,
                entity_id=entity_id,
                fiscal_year=fiscal_year,
                status=AllocationStatus.ACTIVE,
            )
            .order_by("pk")
        )
        if len(allocations) != len(allocation_ids):
            raise BudgetNotFoundError("Satu atau lebih pagu tidak ditemukan atau tidak aktif.")
        for allocation in allocations:
            _require(
                actor,
                "budget.revision.create",
                entity_id=entity_id,
                unit_id=allocation.unit_id,
            )
            requested = requested_amounts[allocation.pk]
            if not isinstance(requested, int) or isinstance(requested, bool) or requested < 0:
                raise BudgetValidationError("Pagu baru wajib berupa integer Rupiah nol atau lebih.")
            if requested == allocation.allocated_amount:
                raise BudgetValidationError("Revisi tidak memuat perubahan nominal.")
        revision = BudgetRevision.objects.create(
            entity_id=entity_id,
            fiscal_year=fiscal_year,
            reason=reason.strip(),
            effective_date=effective_date,
            created_by=actor,
        )
        items = [
            BudgetRevisionItem(
                entity_id=entity_id,
                revision=revision,
                allocation=allocation,
                previous_amount=allocation.allocated_amount,
                requested_amount=requested_amounts[allocation.pk],
                created_by=actor,
            )
            for allocation in allocations
        ]
        BudgetRevisionItem.objects.bulk_create(items)
        _audit(
            actor=actor,
            action="revision.created",
            target_type="BudgetRevision",
            target_id=revision.pk,
            entity_id=entity_id,
            after_state={"reason": revision.reason, "item_count": len(items)},
        )
        return revision


def submit_revision(*, actor_id: int, revision_id: UUID) -> BudgetRevision:
    actor = _actor(actor_id)
    with transaction.atomic():
        revision = BudgetRevision.objects.select_for_update().filter(pk=revision_id).first()
        if revision is None:
            raise BudgetNotFoundError("Revisi anggaran tidak ditemukan.")
        if revision.status != RevisionStatus.DRAFT:
            raise BudgetStateError("Hanya revisi draf yang dapat diajukan.")
        items = list(revision.items.select_related("allocation"))
        if not items:
            raise BudgetValidationError("Revisi tidak memiliki baris pagu.")
        for item in items:
            _require(
                actor,
                "budget.revision.submit",
                entity_id=revision.entity_id,
                unit_id=item.allocation.unit_id,
            )
        revision.status = RevisionStatus.SUBMITTED
        revision.submitted_at = timezone.now()
        revision.save(update_fields=["status", "submitted_at"])
        _audit(
            actor=actor,
            action="revision.submitted",
            target_type="BudgetRevision",
            target_id=revision.pk,
            entity_id=revision.entity_id,
            after_state={"status": revision.status},
        )
        return revision


def verify_revision(*, actor_id: int, revision_id: UUID) -> BudgetRevision:
    actor = _actor(actor_id)
    with transaction.atomic():
        revision = BudgetRevision.objects.select_for_update().filter(pk=revision_id).first()
        if revision is None:
            raise BudgetNotFoundError("Revisi anggaran tidak ditemukan.")
        if revision.status != RevisionStatus.SUBMITTED:
            raise BudgetStateError("Revisi harus diajukan sebelum diverifikasi.")
        if revision.created_by_id == actor.pk:
            raise BudgetMakerCheckerError(
                "Pembuat revisi tidak boleh memverifikasi revisinya sendiri."
            )
        items = list(revision.items.select_related("allocation"))
        for item in items:
            _require(
                actor,
                "budget.revision.verify",
                entity_id=revision.entity_id,
                unit_id=item.allocation.unit_id,
            )
        revision.status = RevisionStatus.VERIFIED
        revision.verified_by = actor
        revision.verified_at = timezone.now()
        revision.save(update_fields=["status", "verified_by", "verified_at"])
        _audit(
            actor=actor,
            action="revision.verified",
            target_type="BudgetRevision",
            target_id=revision.pk,
            entity_id=revision.entity_id,
            after_state={"status": revision.status},
        )
        return revision


def approve_revision(*, actor_id: int, revision_id: UUID) -> BudgetRevision:
    actor = _actor(actor_id)
    with transaction.atomic():
        revision = (
            BudgetRevision.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(pk=revision_id)
            .first()
        )
        if revision is None:
            raise BudgetNotFoundError("Revisi anggaran tidak ditemukan.")
        if revision.fiscal_year.status != FiscalYearStatus.OPEN:
            raise BudgetStateError("Tahun buku sudah ditutup; revisi tidak dapat diberlakukan.")
        if revision.status != RevisionStatus.VERIFIED:
            raise BudgetStateError("Revisi harus diverifikasi sebelum disetujui.")
        if revision.created_by_id == actor.pk or revision.verified_by_id == actor.pk:
            raise BudgetMakerCheckerError("Pembuat atau verifikator tidak boleh menyetujui revisi.")
        items = list(revision.items.select_related("allocation").order_by("allocation_id"))
        for item in items:
            _require(
                actor,
                "budget.revision.approve",
                entity_id=revision.entity_id,
                unit_id=item.allocation.unit_id,
            )
        allocation_ids = [item.allocation_id for item in items]
        locked_allocations = {
            allocation.pk: allocation
            for allocation in BudgetAllocation.objects.select_for_update()
            .filter(pk__in=allocation_ids, status=AllocationStatus.ACTIVE)
            .order_by("pk")
        }
        if len(locked_allocations) != len(items):
            raise BudgetStateError("Pagu berubah status saat revisi diproses.")
        for item in items:
            allocation = locked_allocations[item.allocation_id]
            if allocation.allocated_amount != item.previous_amount:
                raise BudgetStateError(
                    "Nominal pagu berubah sejak revisi dibuat; buat revisi baru."
                )
            committed = (
                allocation.commitments.filter(status__in=ACTIVE_COMMITMENT_STATUSES).aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            )
            if item.requested_amount < committed:
                raise BudgetInsufficientPaguError(
                    "Pagu baru tidak boleh lebih kecil daripada komitmen aktif pada pos tersebut."
                )
        for item in items:
            allocation = locked_allocations[item.allocation_id]
            allocation.allocated_amount = item.requested_amount
            allocation.save(update_fields=["allocated_amount", "updated_at"])
        revision.status = RevisionStatus.EFFECTIVE
        revision.approved_by = actor
        revision.approved_at = timezone.now()
        revision.save(update_fields=["status", "approved_by", "approved_at"])
        _audit(
            actor=actor,
            action="revision.effective",
            target_type="BudgetRevision",
            target_id=revision.pk,
            entity_id=revision.entity_id,
            after_state={
                "status": revision.status,
                "effective_date": revision.effective_date.isoformat(),
                "item_count": len(items),
            },
        )
        return revision


def create_commitment(
    *,
    actor_id: int,
    allocation_id: UUID,
    source_type: str,
    source_id: str,
    description: str,
    amount: int,
) -> BudgetCommitment:
    actor = _actor(actor_id)
    if not source_type.strip() or len(source_type) > 64:
        raise BudgetValidationError("Jenis dokumen sumber wajib diisi (maksimal 64 karakter).")
    if not source_id.strip() or len(source_id) > 128:
        raise BudgetValidationError("ID dokumen sumber wajib diisi (maksimal 128 karakter).")
    if not description.strip() or len(description) > 500:
        raise BudgetValidationError("Uraian komitmen wajib diisi (maksimal 500 karakter).")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise BudgetValidationError(
            "Nominal komitmen wajib berupa integer Rupiah lebih besar dari nol."
        )

    with transaction.atomic():
        allocation = (
            BudgetAllocation.objects.select_for_update()
            .select_related("fiscal_year")
            .filter(pk=allocation_id, status=AllocationStatus.ACTIVE)
            .first()
        )
        if allocation is None:
            raise BudgetNotFoundError("Pagu aktif tidak ditemukan.")
        if allocation.fiscal_year.status != FiscalYearStatus.OPEN:
            raise BudgetStateError(
                "Tahun buku sudah ditutup; komitmen baru tidak dapat dicadangkan."
            )
        _require(
            actor,
            "budget.commitment.create",
            entity_id=allocation.entity_id,
            unit_id=allocation.unit_id,
        )
        existing = BudgetCommitment.objects.filter(
            entity_id=allocation.entity_id,
            source_type=source_type.strip(),
            source_id=source_id.strip(),
        ).first()
        if existing is not None:
            same = (
                existing.allocation_id == allocation.pk
                and existing.description == description.strip()
                and existing.amount == amount
            )
            if same:
                return existing
            raise BudgetDuplicateSourceError(
                "Kunci sumber komitmen sudah digunakan dengan data berbeda."
            )

        committed = (
            BudgetCommitment.objects.filter(
                allocation=allocation,
                status__in=ACTIVE_COMMITMENT_STATUSES,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        available = allocation.allocated_amount - committed
        if amount > available:
            raise BudgetInsufficientPaguError(
                f"Sisa pagu tidak cukup. Tersedia Rp{available}; diminta Rp{amount}."
            )
        try:
            with transaction.atomic():
                commitment = BudgetCommitment.objects.create(
                    entity_id=allocation.entity_id,
                    allocation=allocation,
                    source_type=source_type.strip(),
                    source_id=source_id.strip(),
                    description=description.strip(),
                    amount=amount,
                    created_by=actor,
                )
        except IntegrityError as exc:
            existing = BudgetCommitment.objects.filter(
                entity_id=allocation.entity_id,
                source_type=source_type.strip(),
                source_id=source_id.strip(),
            ).first()
            if existing is None:
                raise
            same = (
                existing.allocation_id == allocation.pk
                and existing.description == description.strip()
                and existing.amount == amount
            )
            if same:
                return existing
            raise BudgetDuplicateSourceError(
                "Kunci sumber komitmen sudah digunakan dengan data berbeda."
            ) from exc
        _audit(
            actor=actor,
            action="commitment.reserved",
            target_type="BudgetCommitment",
            target_id=commitment.pk,
            entity_id=allocation.entity_id,
            unit_id=allocation.unit_id,
            after_state={
                "allocation_id": str(allocation.pk),
                "source_type": commitment.source_type,
                "source_id": commitment.source_id,
                "amount": amount,
                "available_after": available - amount,
            },
        )
        return commitment


def release_commitment(
    *,
    actor_id: int,
    commitment_id: UUID,
    reason: str,
) -> BudgetCommitment:
    actor = _actor(actor_id)
    if len(reason.strip()) < 8 or len(reason) > 500:
        raise BudgetValidationError("Alasan pelepasan wajib diisi minimal 8 karakter.")
    with transaction.atomic():
        commitment = (
            BudgetCommitment.objects.select_for_update()
            .select_related("allocation")
            .filter(pk=commitment_id)
            .first()
        )
        if commitment is None:
            raise BudgetNotFoundError("Komitmen anggaran tidak ditemukan.")
        _require(
            actor,
            "budget.commitment.release",
            entity_id=commitment.entity_id,
            unit_id=commitment.allocation.unit_id,
        )
        if commitment.status != CommitmentStatus.RESERVED:
            raise BudgetStateError("Hanya komitmen yang masih dicadangkan yang dapat dilepaskan.")
        if commitment.created_by_id == actor.pk:
            raise BudgetMakerCheckerError("Pembuat komitmen tidak boleh menyetujui pelepasannya.")
        commitment.status = CommitmentStatus.RELEASED
        commitment.released_by = actor
        commitment.released_at = timezone.now()
        commitment.release_reason = reason.strip()
        commitment.save(update_fields=["status", "released_by", "released_at", "release_reason"])
        _audit(
            actor=actor,
            action="commitment.released",
            target_type="BudgetCommitment",
            target_id=commitment.pk,
            entity_id=commitment.entity_id,
            unit_id=commitment.allocation.unit_id,
            after_state={
                "status": commitment.status,
                "amount": commitment.amount,
                "reason": commitment.release_reason,
            },
        )
        return commitment


def fulfill_commitment(*, actor_id: int, commitment_id: UUID) -> BudgetCommitment:
    actor = _actor(actor_id)
    with transaction.atomic():
        commitment = (
            BudgetCommitment.objects.select_for_update()
            .select_related("allocation")
            .filter(pk=commitment_id)
            .first()
        )
        if commitment is None:
            raise BudgetNotFoundError("Komitmen anggaran tidak ditemukan.")
        _require(
            actor,
            "budget.commitment.fulfill",
            entity_id=commitment.entity_id,
            unit_id=commitment.allocation.unit_id,
        )
        if commitment.status != CommitmentStatus.RESERVED:
            raise BudgetStateError("Hanya komitmen yang dicadangkan yang dapat direalisasikan.")
        if commitment.created_by_id == actor.pk:
            raise BudgetMakerCheckerError(
                "Pembuat komitmen tidak boleh mengonfirmasi realisasinya."
            )
        commitment.status = CommitmentStatus.FULFILLED
        commitment.save(update_fields=["status"])
        _audit(
            actor=actor,
            action="commitment.fulfilled",
            target_type="BudgetCommitment",
            target_id=commitment.pk,
            entity_id=commitment.entity_id,
            unit_id=commitment.allocation.unit_id,
            after_state={"status": commitment.status, "amount": commitment.amount},
        )
        return commitment
