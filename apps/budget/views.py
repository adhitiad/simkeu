from __future__ import annotations

from typing import cast
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import BigIntegerField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.ledger.models import Account
from apps.platform_app.models import Entity, OrganizationalUnit
from apps.platform_app.services import (
    IamError,
    entities_for_user,
    has_permission,
    visible_unit_ids,
)

from .forms import (
    BudgetLineForm,
    BudgetPlanForm,
    CommitmentForm,
    FiscalYearForm,
    RevisionForm,
)
from .models import (
    AllocationStatus,
    BudgetAllocation,
    BudgetCommitment,
    BudgetPlan,
    BudgetPlanStatus,
    BudgetPlanType,
    BudgetRevision,
    CommitmentStatus,
    FiscalYear,
)
from .services import (
    BudgetError,
    add_budget_line,
    approve_plan,
    approve_revision,
    consolidate_rkat_into_rapbu,
    create_apbu_from_rapbu,
    create_commitment,
    create_fiscal_year,
    create_plan,
    create_revision,
    fulfill_commitment,
    release_commitment,
    review_plan,
    submit_plan,
    submit_revision,
    verify_revision,
)


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


def _forbidden(request: HttpRequest) -> HttpResponseForbidden:
    return HttpResponseForbidden(render(request, "platform/forbidden.html").content)


def _entities_for_request(request: HttpRequest) -> tuple[list[Entity], Entity | None]:
    entities = entities_for_user(_user(request))
    raw_id = request.GET.get("entity") or request.POST.get("entity")
    selected = next((entity for entity in entities if str(entity.pk) == raw_id), None)
    if selected is None and not raw_id and entities:
        selected = entities[0]
    return entities, selected


def _visible_units(user: User, entity_id: int, permission: str) -> set[int] | None:
    return visible_unit_ids(user, entity_id, permission)


def _form_errors(request: HttpRequest, form: object) -> None:
    errors = getattr(form, "errors", {})
    messages.error(request, f"Periksa input: {errors}")


def dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return render(request, "budget/dashboard.html", {"entities": entities, "entity": None})
    user = _user(request)
    unit_ids = _visible_units(user, entity.pk, "budget.read")
    plan_create_units = _visible_units(user, entity.pk, "budget.plan.create")
    if unit_ids == set():
        return _forbidden(request)

    fiscal_years = list(FiscalYear.objects.filter(entity_id=entity.pk).order_by("-starts_on"))
    requested_year = request.GET.get("fiscal_year_id", "")
    selected_fiscal_year = next(
        (year for year in fiscal_years if str(year.pk) == requested_year),
        fiscal_years[0] if fiscal_years else None,
    )
    plans = BudgetPlan.objects.filter(entity_id=entity.pk).select_related("fiscal_year")
    allocations = BudgetAllocation.objects.filter(
        entity_id=entity.pk,
        status=AllocationStatus.ACTIVE,
    )
    if selected_fiscal_year is not None:
        plans = plans.filter(fiscal_year=selected_fiscal_year)
        allocations = allocations.filter(fiscal_year=selected_fiscal_year)
    else:
        plans = plans.none()
        allocations = allocations.none()
    if unit_ids is not None:
        plans = plans.filter(Q(unit_id__in=unit_ids) | Q(lines__unit_id__in=unit_ids)).distinct()
        allocations = allocations.filter(unit_id__in=unit_ids)

    pagu_total = allocations.aggregate(
        total=Coalesce(Sum("allocated_amount"), Value(0), output_field=BigIntegerField())
    )["total"]
    committed_total = BudgetCommitment.objects.filter(
        allocation__in=allocations,
        status__in=[CommitmentStatus.RESERVED, CommitmentStatus.FULFILLED],
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=BigIntegerField()))["total"]
    context = {
        "entities": entities,
        "entity": entity,
        "fiscal_years": fiscal_years,
        "selected_fiscal_year": selected_fiscal_year,
        "plans": plans.order_by("-created_at")[:30],
        "pagu_total": pagu_total,
        "committed_total": committed_total,
        "available_total": pagu_total - committed_total,
        "can_create": (plan_create_units is None or bool(plan_create_units)),
        "can_manage_fiscal_year": has_permission(
            user, "budget.fiscal_year.manage", entity_id=entity.pk
        ),
        "can_consolidate": has_permission(user, "budget.plan.create", entity_id=entity.pk),
    }
    return render(request, "budget/dashboard.html", context)


def fiscal_year_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return _forbidden(request)
    form = FiscalYearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_fiscal_year(
                actor_id=_user(request).pk,
                entity_id=entity.pk,
                code=str(data["code"]),
                name=str(data["name"]),
                starts_on=data["starts_on"],
                ends_on=data["ends_on"],
            )
        except (BudgetError, IamError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Tahun buku berhasil dibuat.")
            return redirect(f"/budgets/?entity={entity.pk}")
    elif request.method == "POST":
        _form_errors(request, form)
    return render(
        request,
        "budget/fiscal_year_form.html",
        {"entities": entities, "entity": entity, "form": form},
    )


def plan_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return _forbidden(request)
    form = BudgetPlanForm(request.POST or None)
    units = OrganizationalUnit.objects.filter(entity=entity, is_active=True).order_by("code")
    unit_ids = _visible_units(_user(request), entity.pk, "budget.plan.create")
    if unit_ids == set():
        return _forbidden(request)
    if unit_ids is not None:
        units = units.filter(pk__in=unit_ids)
        form.fields["plan_type"].choices = [(BudgetPlanType.RKAT, BudgetPlanType.RKAT.label)]
    fiscal_years = FiscalYear.objects.filter(
        entity_id=entity.pk,
        status="open",
    ).order_by("-starts_on")
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            plan = create_plan(
                actor_id=_user(request).pk,
                entity_id=entity.pk,
                fiscal_year_id=data["fiscal_year_id"],
                plan_type=str(data["plan_type"]),
                title=str(data["title"]),
                unit_id=data["unit_id"],
                notes=str(data["notes"]),
            )
        except (BudgetError, IamError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Dokumen anggaran berhasil dibuat.")
            return redirect("budget:plan_detail", plan_id=plan.pk)
    elif request.method == "POST":
        _form_errors(request, form)
    return render(
        request,
        "budget/plan_form.html",
        {
            "entities": entities,
            "entity": entity,
            "form": form,
            "units": units,
            "fiscal_years": fiscal_years,
        },
    )


def plan_detail(request: HttpRequest, plan_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    plan = get_object_or_404(BudgetPlan.objects.select_related("fiscal_year"), pk=plan_id)
    user = _user(request)
    unit_ids = _visible_units(user, plan.entity_id, "budget.plan.read")
    if unit_ids == set():
        return _forbidden(request)
    if plan.unit_id is not None and unit_ids is not None and plan.unit_id not in unit_ids:
        return _forbidden(request)
    lines = plan.lines.all().select_related("plan")
    if unit_ids is not None:
        lines = lines.filter(unit_id__in=unit_ids)
    if not lines.exists() and plan.lines.exists():
        return _forbidden(request)

    form = BudgetLineForm()
    if request.method == "POST":
        return _forbidden(request)

    line_unit_ids = _visible_units(user, plan.entity_id, "budget.line.create")
    available_units = OrganizationalUnit.objects.filter(
        entity_id=plan.entity_id,
        is_active=True,
    ).order_by("code")
    if plan.unit_id is not None:
        available_units = available_units.filter(pk=plan.unit_id)
    elif line_unit_ids is not None:
        available_units = available_units.filter(pk__in=line_unit_ids)
    account_rows = Account.objects.filter(entity_id=plan.entity_id, is_active=True).order_by("code")
    form.fields["unit_id"] = forms.ChoiceField(
        label="Unit anggaran",
        choices=[("", "Pilih unit")]
        + [(str(unit.pk), f"{unit.code} — {unit.name}") for unit in available_units],
    )
    form.fields["account_id"] = forms.ChoiceField(
        label="Akun COA",
        choices=[("", "Pilih akun")]
        + [(str(account.pk), f"{account.code} — {account.name}") for account in account_rows],
    )

    all_plan_unit_ids = list(
        plan.lines.order_by("unit_id").values_list("unit_id", flat=True).distinct()
    )

    def can_for_plan(permission: str) -> bool:
        target_units = all_plan_unit_ids or ([plan.unit_id] if plan.unit_id is not None else [])
        if unit_ids is None:
            return has_permission(user, permission, entity_id=plan.entity_id)
        if not target_units:
            return False
        return all(
            has_permission(user, permission, entity_id=plan.entity_id, unit_id=target)
            for target in target_units
        )

    can_add_line = (
        plan.status == BudgetPlanStatus.DRAFT
        and line_unit_ids != set()
        and bool(available_units.exists())
    )
    can_submit = can_for_plan("budget.plan.submit")
    can_review = can_for_plan("budget.plan.review")
    can_approve = can_for_plan("budget.plan.approve")
    total = lines.aggregate(total=Sum("amount"))["total"] or 0
    return render(
        request,
        "budget/plan_detail.html",
        {
            "plan": plan,
            "lines": lines,
            "form": form,
            "total": total,
            "can_add_line": can_add_line,
            "can_submit": can_submit,
            "can_review": can_review,
            "can_approve": can_approve,
            "can_create_apbu": (
                plan.plan_type == BudgetPlanType.RAPBU
                and plan.status == BudgetPlanStatus.APPROVED
                and has_permission(user, "budget.plan.create", entity_id=plan.entity_id)
            ),
        },
    )


def plan_line_create(request: HttpRequest, plan_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    plan = get_object_or_404(BudgetPlan, pk=plan_id)
    form = BudgetLineForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            add_budget_line(
                actor_id=_user(request).pk,
                plan_id=plan.pk,
                unit_id=int(data["unit_id"]),
                account_id=UUID(str(data["account_id"])),
                funding_source=str(data["funding_source"]),
                description=str(data["description"]),
                amount=int(data["amount"]),
                program_code=str(data["program_code"]),
                objective=str(data["objective"]),
                output=str(data["output"]),
                indicator=str(data["indicator"]),
                schedule_start=data["schedule_start"],
                schedule_end=data["schedule_end"],
                is_restricted=bool(data["is_restricted"]),
                restriction_note=str(data["restriction_note"]),
            )
        except (BudgetError, IamError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Baris anggaran berhasil ditambahkan.")
    else:
        _form_errors(request, form)
    return redirect("budget:plan_detail", plan_id=plan.pk)


def plan_action(request: HttpRequest, plan_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    action = request.POST.get("action", "")
    try:
        if action == "submit":
            submit_plan(actor_id=_user(request).pk, plan_id=plan_id)
            messages.success(request, "Dokumen berhasil diajukan.")
        elif action == "review":
            review_plan(actor_id=_user(request).pk, plan_id=plan_id)
            messages.success(request, "Review dokumen berhasil dicatat.")
        elif action == "approve":
            plan = approve_plan(actor_id=_user(request).pk, plan_id=plan_id)
            message = (
                "APBU aktif dan pagu telah dibuka."
                if plan.status == BudgetPlanStatus.ACTIVE
                else "Dokumen berhasil disetujui."
            )
            messages.success(request, message)
        else:
            messages.error(request, "Aksi dokumen tidak dikenal.")
    except (BudgetError, IamError) as exc:
        messages.error(request, str(exc))
    return redirect("budget:plan_detail", plan_id=plan_id)


def rapbu_consolidate(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    _entities, entity = _entities_for_request(request)
    if entity is None:
        return _forbidden(request)
    try:
        fiscal_year_id = UUID(request.POST.get("fiscal_year_id", ""))
        plan = consolidate_rkat_into_rapbu(
            actor_id=_user(request).pk,
            entity_id=entity.pk,
            fiscal_year_id=fiscal_year_id,
            title=request.POST.get("title", ""),
        )
    except (ValueError, BudgetError, IamError) as exc:
        messages.error(request, str(exc))
        return redirect(f"/budgets/?entity={entity.pk}")
    messages.success(request, "RKAT unit berhasil dikonsolidasikan menjadi RAPBU draf.")
    return redirect("budget:plan_detail", plan_id=plan.pk)


def apbu_from_rapbu(request: HttpRequest, rapbu_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    try:
        plan = create_apbu_from_rapbu(
            actor_id=_user(request).pk,
            rapbu_id=rapbu_id,
            title=request.POST.get("title", ""),
        )
    except (BudgetError, IamError) as exc:
        messages.error(request, str(exc))
        return redirect("budget:plan_detail", plan_id=rapbu_id)
    messages.success(request, "APBU draf berhasil dibuat dari RAPBU yang disetujui.")
    return redirect("budget:plan_detail", plan_id=plan.pk)


def allocation_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return render(request, "budget/allocations.html", {"entities": entities, "entity": None})
    unit_ids = _visible_units(_user(request), entity.pk, "budget.pagu.read")
    revision_unit_ids = _visible_units(_user(request), entity.pk, "budget.revision.create")
    if unit_ids == set():
        return _forbidden(request)
    allocations = (
        BudgetAllocation.objects.filter(
            entity_id=entity.pk,
            status=AllocationStatus.ACTIVE,
        )
        .select_related("fiscal_year", "budget_line", "budget_line__plan")
        .annotate(
            committed_amount=Coalesce(
                Sum(
                    "commitments__amount",
                    filter=Q(
                        commitments__status__in=[
                            CommitmentStatus.RESERVED,
                            CommitmentStatus.FULFILLED,
                        ]
                    ),
                ),
                Value(0),
                output_field=BigIntegerField(),
            )
        )
        .annotate(available_amount=F("allocated_amount") - F("committed_amount"))
    )
    if unit_ids is not None:
        allocations = allocations.filter(unit_id__in=unit_ids)
    return render(
        request,
        "budget/allocations.html",
        {
            "entities": entities,
            "entity": entity,
            "allocations": allocations.order_by("unit_id", "account_id"),
            "can_create_revision": revision_unit_ids is None or bool(revision_unit_ids),
        },
    )


def revision_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return _forbidden(request)
    form = RevisionForm(request.POST or None, initial={"effective_date": None})
    unit_ids = _visible_units(_user(request), entity.pk, "budget.revision.create")
    allocations = BudgetAllocation.objects.filter(
        entity_id=entity.pk,
        status=AllocationStatus.ACTIVE,
    ).select_related("budget_line", "budget_line__plan", "fiscal_year")
    if unit_ids == set():
        return _forbidden(request)
    if unit_ids is not None:
        allocations = allocations.filter(unit_id__in=unit_ids)
    if request.method == "POST" and form.is_valid():
        selected_ids = request.POST.getlist("allocation_ids")
        amounts: dict[UUID, int] = {}
        try:
            for raw_id in selected_ids:
                allocation_id = UUID(raw_id)
                raw_amount = request.POST.get(f"new_amount_{raw_id}", "")
                amounts[allocation_id] = int(raw_amount)
            revision = create_revision(
                actor_id=_user(request).pk,
                entity_id=entity.pk,
                fiscal_year_id=form.cleaned_data["fiscal_year_id"],
                reason=str(form.cleaned_data["reason"]),
                effective_date=form.cleaned_data["effective_date"],
                requested_amounts=amounts,
            )
        except (ValueError, BudgetError, IamError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Draf revisi anggaran berhasil dibuat.")
            return redirect("budget:revision_detail", revision_id=revision.pk)
    elif request.method == "POST":
        _form_errors(request, form)
    fiscal_years = FiscalYear.objects.filter(
        entity_id=entity.pk,
        status="open",
    ).order_by("-starts_on")
    return render(
        request,
        "budget/revision_form.html",
        {
            "entities": entities,
            "entity": entity,
            "form": form,
            "fiscal_years": fiscal_years,
            "allocations": allocations,
        },
    )


def revision_detail(request: HttpRequest, revision_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    revision = get_object_or_404(
        BudgetRevision.objects.select_related("fiscal_year"),
        pk=revision_id,
    )
    unit_ids = _visible_units(_user(request), revision.entity_id, "budget.revision.read")
    if unit_ids == set():
        return _forbidden(request)
    all_item_unit_ids = list(
        revision.items.values_list("allocation__unit_id", flat=True).distinct()
    )
    items = revision.items.select_related("allocation", "allocation__budget_line")
    if unit_ids is not None:
        items = items.filter(allocation__unit_id__in=unit_ids)
    if not items.exists():
        return _forbidden(request)
    return render(
        request,
        "budget/revision_detail.html",
        {
            "revision": revision,
            "items": items,
            "can_submit": bool(all_item_unit_ids)
            and all(
                has_permission(
                    _user(request),
                    "budget.revision.submit",
                    entity_id=revision.entity_id,
                    unit_id=unit_id,
                )
                for unit_id in all_item_unit_ids
            ),
            "can_verify": bool(all_item_unit_ids)
            and all(
                has_permission(
                    _user(request),
                    "budget.revision.verify",
                    entity_id=revision.entity_id,
                    unit_id=unit_id,
                )
                for unit_id in all_item_unit_ids
            ),
            "can_approve": bool(all_item_unit_ids)
            and all(
                has_permission(
                    _user(request),
                    "budget.revision.approve",
                    entity_id=revision.entity_id,
                    unit_id=unit_id,
                )
                for unit_id in all_item_unit_ids
            ),
        },
    )


def revision_action(request: HttpRequest, revision_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    action = request.POST.get("action", "")
    try:
        if action == "submit":
            submit_revision(actor_id=_user(request).pk, revision_id=revision_id)
            messages.success(request, "Revisi berhasil diajukan.")
        elif action == "verify":
            verify_revision(actor_id=_user(request).pk, revision_id=revision_id)
            messages.success(request, "Revisi berhasil diverifikasi.")
        elif action == "approve":
            approve_revision(actor_id=_user(request).pk, revision_id=revision_id)
            messages.success(request, "Revisi disetujui; nominal pagu telah diperbarui.")
        else:
            messages.error(request, "Aksi revisi tidak dikenal.")
    except (BudgetError, IamError) as exc:
        messages.error(request, str(exc))
    return redirect("budget:revision_detail", revision_id=revision_id)


def commitment_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return render(request, "budget/commitments.html", {"entities": entities, "entity": None})
    unit_ids = _visible_units(_user(request), entity.pk, "budget.commitment.read")
    create_unit_ids = _visible_units(_user(request), entity.pk, "budget.commitment.create")
    if unit_ids == set():
        return _forbidden(request)
    commitments = BudgetCommitment.objects.filter(entity_id=entity.pk).select_related(
        "allocation", "allocation__budget_line", "created_by", "released_by"
    )
    if unit_ids is not None:
        commitments = commitments.filter(allocation__unit_id__in=unit_ids)
    return render(
        request,
        "budget/commitments.html",
        {
            "entities": entities,
            "entity": entity,
            "commitments": commitments[:100],
            "can_create": create_unit_ids is None or bool(create_unit_ids),
        },
    )


def commitment_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities, entity = _entities_for_request(request)
    if entity is None:
        return _forbidden(request)
    form = CommitmentForm(request.POST or None)
    allocations = BudgetAllocation.objects.filter(
        entity_id=entity.pk,
        status=AllocationStatus.ACTIVE,
    ).select_related("budget_line", "fiscal_year")
    unit_ids = _visible_units(_user(request), entity.pk, "budget.commitment.create")
    if unit_ids == set():
        return _forbidden(request)
    if unit_ids is not None:
        allocations = allocations.filter(unit_id__in=unit_ids)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_commitment(
                actor_id=_user(request).pk,
                allocation_id=data["allocation_id"],
                source_type=str(data["source_type"]),
                source_id=str(data["source_id"]),
                description=str(data["description"]),
                amount=int(data["amount"]),
            )
        except (BudgetError, IamError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Komitmen berhasil dicadangkan.")
            return redirect("budget:commitment_list")
    elif request.method == "POST":
        _form_errors(request, form)
    return render(
        request,
        "budget/commitment_form.html",
        {
            "entities": entities,
            "entity": entity,
            "form": form,
            "allocations": allocations,
        },
    )


def commitment_action(request: HttpRequest, commitment_id: UUID) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    action = request.POST.get("action", "")
    try:
        if action == "release":
            release_commitment(
                actor_id=_user(request).pk,
                commitment_id=commitment_id,
                reason=request.POST.get("reason", ""),
            )
            messages.success(request, "Komitmen berhasil dilepaskan.")
        elif action == "fulfill":
            fulfill_commitment(actor_id=_user(request).pk, commitment_id=commitment_id)
            messages.success(request, "Komitmen ditandai telah direalisasikan.")
        else:
            messages.error(request, "Aksi komitmen tidak dikenal.")
    except (BudgetError, IamError) as exc:
        messages.error(request, str(exc))
    return redirect("budget:commitment_list")
