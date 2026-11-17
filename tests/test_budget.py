from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.budget.models import (
    BudgetAllocation,
    BudgetPlan,
    BudgetPlanStatus,
    BudgetPlanType,
    CommitmentStatus,
    FiscalYear,
    RevisionStatus,
)
from apps.budget.services import (
    BudgetDuplicateSourceError,
    BudgetInsufficientPaguError,
    BudgetMakerCheckerError,
    BudgetStateError,
    BudgetValidationError,
    add_budget_line,
    approve_plan,
    approve_revision,
    consolidate_rkat_into_rapbu,
    create_apbu_from_rapbu,
    create_commitment,
    create_fiscal_year,
    create_plan,
    create_revision,
    release_commitment,
    review_plan,
    submit_plan,
    submit_revision,
    verify_revision,
)
from apps.ledger.models import Account
from apps.platform_app.models import Entity, OrganizationalUnit, Permission, Role, RolePermission
from apps.platform_app.services import seed_roles


def _user(label: str) -> User:
    return User.objects.create_superuser(
        username=f"{label}-simkeu-budget",
        email="",
        password="test-only-password",
    )


def _environment() -> tuple[User, User, User, Entity, OrganizationalUnit, Account]:
    maker = _user("maker")
    reviewer = _user("reviewer")
    approver = _user("approver")
    entity = Entity.objects.create(
        code="BUDGET-PTS",
        name="Yayasan Pendidikan Anggaran",
        legal_form="foundation",
    )
    unit = OrganizationalUnit.objects.create(
        entity=entity,
        code="FAK-01",
        name="Fakultas Contoh",
        unit_type="faculty",
        is_cost_center=True,
    )
    account = Account.objects.create(
        entity_id=entity.pk,
        code="6101",
        name="Beban Operasional",
        account_type="expense",
        normal_balance="debit",
        created_by=maker,
    )
    return maker, reviewer, approver, entity, unit, account


def _approved_apbu() -> tuple[
    User,
    User,
    User,
    Entity,
    OrganizationalUnit,
    Account,
    FiscalYear,
    BudgetAllocation,
]:
    maker, reviewer, approver, entity, unit, account = _environment()
    fiscal_year = create_fiscal_year(
        actor_id=maker.pk,
        entity_id=entity.pk,
        code="FY-2027",
        name="Tahun Buku 2027",
        starts_on=date(2027, 1, 1),
        ends_on=date(2027, 12, 31),
    )
    rkat = create_plan(
        actor_id=maker.pk,
        entity_id=entity.pk,
        fiscal_year_id=fiscal_year.pk,
        plan_type=BudgetPlanType.RKAT,
        title="RKAT Fakultas Contoh",
        unit_id=unit.pk,
    )
    add_budget_line(
        actor_id=maker.pk,
        plan_id=rkat.pk,
        unit_id=unit.pk,
        account_id=account.pk,
        funding_source="operasional",
        description="Program layanan akademik",
        objective="Mendukung layanan akademik",
        output="Layanan berjalan",
        indicator="Capaian layanan",
        amount=100_000,
    )
    submit_plan(actor_id=maker.pk, plan_id=rkat.pk)
    review_plan(actor_id=reviewer.pk, plan_id=rkat.pk)
    approve_plan(actor_id=approver.pk, plan_id=rkat.pk)

    rapbu = consolidate_rkat_into_rapbu(
        actor_id=approver.pk,
        entity_id=entity.pk,
        fiscal_year_id=fiscal_year.pk,
        title="RAPBU 2027",
    )
    submit_plan(actor_id=approver.pk, plan_id=rapbu.pk)
    review_plan(actor_id=maker.pk, plan_id=rapbu.pk)
    approve_plan(actor_id=reviewer.pk, plan_id=rapbu.pk)

    apbu = create_apbu_from_rapbu(actor_id=reviewer.pk, rapbu_id=rapbu.pk)
    submit_plan(actor_id=reviewer.pk, plan_id=apbu.pk)
    review_plan(actor_id=maker.pk, plan_id=apbu.pk)
    approved = approve_plan(actor_id=approver.pk, plan_id=apbu.pk)
    allocation = BudgetAllocation.objects.get(budget_line__plan=approved)
    return maker, reviewer, approver, entity, unit, account, fiscal_year, allocation


@pytest.mark.django_db
def test_fiscal_year_overlap_is_rejected() -> None:
    maker, _, _, entity, _, _ = _environment()
    create_fiscal_year(
        actor_id=maker.pk,
        entity_id=entity.pk,
        code="FY-2027",
        name="Tahun Buku 2027",
        starts_on=date(2027, 1, 1),
        ends_on=date(2027, 12, 31),
    )

    with pytest.raises(BudgetValidationError):
        create_fiscal_year(
            actor_id=maker.pk,
            entity_id=entity.pk,
            code="FY-2027-Q2",
            name="Tahun Buku Kuartal Kedua 2027",
            starts_on=date(2027, 4, 1),
            ends_on=date(2027, 6, 30),
        )


@pytest.mark.django_db
def test_rkat_rapbu_apbu_approval_opens_pagu() -> None:
    maker, _, _, _, _, _, _, allocation = _approved_apbu()

    assert allocation.allocated_amount == 100_000
    assert allocation.status == "active"
    assert allocation.created_by_id != maker.pk
    assert allocation.budget_line.plan.status == BudgetPlanStatus.ACTIVE
    assert allocation.budget_line.plan.plan_type == BudgetPlanType.APBU


@pytest.mark.django_db
def test_commitment_is_idempotent_and_cannot_exceed_remaining_pagu() -> None:
    maker, reviewer, _, _, _, _, _, allocation = _approved_apbu()

    first = create_commitment(
        actor_id=maker.pk,
        allocation_id=allocation.pk,
        source_type="purchase_request",
        source_id="PR-2027-0001",
        description="Pengadaan perlengkapan laboratorium",
        amount=80_000,
    )
    duplicate = create_commitment(
        actor_id=maker.pk,
        allocation_id=allocation.pk,
        source_type="purchase_request",
        source_id="PR-2027-0001",
        description="Pengadaan perlengkapan laboratorium",
        amount=80_000,
    )
    assert first.pk == duplicate.pk

    with pytest.raises(BudgetDuplicateSourceError):
        create_commitment(
            actor_id=maker.pk,
            allocation_id=allocation.pk,
            source_type="purchase_request",
            source_id="PR-2027-0001",
            description="Nominal berbeda",
            amount=70_000,
        )

    with pytest.raises(BudgetInsufficientPaguError):
        create_commitment(
            actor_id=maker.pk,
            allocation_id=allocation.pk,
            source_type="purchase_request",
            source_id="PR-2027-0002",
            description="Belanja melebihi sisa pagu",
            amount=20_001,
        )

    released = release_commitment(
        actor_id=reviewer.pk,
        commitment_id=first.pk,
        reason="Pengadaan dibatalkan unit",
    )
    assert released.status == CommitmentStatus.RELEASED
    assert released.released_by_id == reviewer.pk


@pytest.mark.django_db
def test_active_apbu_cannot_be_replaced_while_commitments_exist() -> None:
    maker, reviewer, approver, entity, _, _, _, allocation = _approved_apbu()
    create_commitment(
        actor_id=maker.pk,
        allocation_id=allocation.pk,
        source_type="contract",
        source_id="APBU-LOCK-001",
        description="Komitmen yang menahan pergantian APBU",
        amount=10_000,
    )
    approved_rapbu = BudgetPlan.objects.get(
        entity_id=entity.pk,
        plan_type=BudgetPlanType.RAPBU,
        status=BudgetPlanStatus.APPROVED,
    )
    next_apbu = create_apbu_from_rapbu(
        actor_id=reviewer.pk,
        rapbu_id=approved_rapbu.pk,
        title="APBU 2027 versi berikutnya",
    )
    submit_plan(actor_id=reviewer.pk, plan_id=next_apbu.pk)
    review_plan(actor_id=maker.pk, plan_id=next_apbu.pk)

    with pytest.raises(BudgetStateError):
        approve_plan(actor_id=approver.pk, plan_id=next_apbu.pk)

    allocation.refresh_from_db()
    next_apbu.refresh_from_db()
    assert allocation.status == "active"
    assert next_apbu.status == BudgetPlanStatus.REVIEW


@pytest.mark.django_db
def test_revision_rejects_pagu_below_existing_commitment_and_preserves_snapshot() -> None:
    maker, reviewer, approver, entity, _, _, fiscal_year, allocation = _approved_apbu()
    commitment = create_commitment(
        actor_id=maker.pk,
        allocation_id=allocation.pk,
        source_type="contract",
        source_id="KONTRAK-001",
        description="Kontrak layanan tahunan",
        amount=80_000,
    )

    revision = create_revision(
        actor_id=maker.pk,
        entity_id=entity.pk,
        fiscal_year_id=fiscal_year.pk,
        reason="Penyesuaian pagu setelah evaluasi kebutuhan unit",
        effective_date=date(2027, 7, 1),
        requested_amounts={allocation.pk: 70_000},
    )
    submit_revision(actor_id=maker.pk, revision_id=revision.pk)
    verify_revision(actor_id=reviewer.pk, revision_id=revision.pk)
    with pytest.raises(BudgetInsufficientPaguError):
        approve_revision(actor_id=approver.pk, revision_id=revision.pk)

    revision.refresh_from_db()
    item = revision.items.get(allocation=allocation)
    allocation.refresh_from_db()
    assert revision.status == RevisionStatus.VERIFIED
    assert item.previous_amount == 100_000
    assert item.requested_amount == 70_000
    assert allocation.allocated_amount == 100_000
    assert commitment.status == CommitmentStatus.RESERVED


@pytest.mark.django_db
def test_revision_requires_separate_maker_verifier_and_approver() -> None:
    maker, reviewer, approver, entity, _, _, fiscal_year, allocation = _approved_apbu()
    revision = create_revision(
        actor_id=maker.pk,
        entity_id=entity.pk,
        fiscal_year_id=fiscal_year.pk,
        reason="Kenaikan biaya operasional yang telah ditinjau",
        effective_date=date(2027, 8, 1),
        requested_amounts={allocation.pk: 120_000},
    )
    submit_revision(actor_id=maker.pk, revision_id=revision.pk)
    with pytest.raises(BudgetMakerCheckerError):
        verify_revision(actor_id=maker.pk, revision_id=revision.pk)

    verify_revision(actor_id=reviewer.pk, revision_id=revision.pk)
    effective = approve_revision(actor_id=approver.pk, revision_id=revision.pk)
    allocation.refresh_from_db()

    assert effective.status == RevisionStatus.EFFECTIVE
    assert allocation.allocated_amount == 120_000


@pytest.mark.django_db
def test_seed_roles_includes_budget_permissions() -> None:
    seed_roles()
    finance = Role.objects.get(code=Role.FINANCE_MANAGER)
    permission = Permission.objects.get(code="budget.plan.create")
    assert RolePermission.objects.filter(role=finance, permission=permission).exists()


@pytest.mark.django_db
def test_budget_dashboard_requires_login_and_scopes_superuser() -> None:
    client = Client()
    assert client.get("/budgets/").status_code == 302

    user = _user("dashboard")
    entity = Entity.objects.create(code="DASH-PTS", name="PTS Dasbor")
    client.force_login(user)
    response = client.get(f"/budgets/?entity={entity.pk}")
    assert response.status_code == 200
    assert b"P1" in response.content
