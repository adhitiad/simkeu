from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from apps.ledger.models import JournalEntry
from apps.platform_app.models import (
    AuditEvent,
    Entity,
    OrganizationalUnit,
    OutboxEvent,
    Role,
    UnitType,
    UserRole,
)
from apps.platform_app.services import (
    IamError,
    assign_role,
    entities_for_user,
    has_permission_any_entity,
    record_audit,
    require_permission,
    role_codes,
    visible_unit_ids,
)


def _forbidden(request: HttpRequest) -> HttpResponseForbidden:
    return HttpResponseForbidden(render(request, "platform/forbidden.html").content)


def _request_context(request: HttpRequest) -> tuple[str, str | None]:
    return str(request.headers.get("X-Request-ID", "")), request.META.get("REMOTE_ADDR")


def dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities = entities_for_user(request.user)
    raw_entity = request.GET.get("entity")
    entity = next((item for item in entities if str(item.pk) == raw_entity), None)
    if entity is None:
        entity = entities[0] if entities else None
    if entity is None:
        return render(request, "platform/dashboard.html", {"roles": set(), "entity": None})

    try:
        require_permission(request.user, "dashboard.read", entity_id=entity.pk)
    except IamError:
        return _forbidden(request)

    journal_qs = JournalEntry.objects.filter(entity_id=entity.pk)
    context = {
        "entity": entity,
        "entities": entities,
        "roles": role_codes(request.user, entity.pk),
        "journal_count": journal_qs.count(),
        "outbox_pending": OutboxEvent.objects.filter(published_at__isnull=True).count(),
        "unit_count": OrganizationalUnit.objects.filter(entity=entity, is_active=True).count(),
        "audit_count": AuditEvent.objects.filter(entity_id=entity.pk).count(),
    }
    return render(request, "platform/dashboard.html", context)


def login_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request_id, ip_address = _request_context(request)
            record_audit(
                actor=user,
                action="auth.login",
                target_type="User",
                target_id=str(user.pk),
                request_id=request_id,
                ip_address=ip_address,
            )
            return redirect("dashboard")
    else:
        form = AuthenticationForm(request)
    return render(request, "registration/login.html", {"form": form})


def entity_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if not has_permission_any_entity(request.user, "iam.entity.read"):
        return _forbidden(request)
    return render(
        request, "platform/entity_list.html", {"entities": entities_for_user(request.user)}
    )


def entity_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if not has_permission_any_entity(request.user, "iam.entity.create"):
        return _forbidden(request)
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        if not code or not name or len(code) > 32 or len(name) > 160:
            messages.error(request, "Kode dan nama entitas wajib diisi dengan panjang valid.")
        else:
            try:
                entity = Entity.objects.create(code=code, name=name)
            except IntegrityError:
                messages.error(request, "Kode entitas sudah digunakan.")
            else:
                request_id, ip_address = _request_context(request)
                record_audit(
                    actor=request.user,
                    action="iam.entity.create",
                    target_type="Entity",
                    target_id=str(entity.pk),
                    entity_id=entity.pk,
                    before_state=None,
                    after_state={"code": code, "name": name},
                    request_id=request_id,
                    ip_address=ip_address,
                )
                messages.success(request, "Entitas berhasil dibuat.")
                return redirect("entity_list")
    return render(request, "platform/entity_form.html")


def unit_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities = entities_for_user(request.user)
    raw_entity = request.GET.get("entity")
    entity = next((item for item in entities if str(item.pk) == raw_entity), None)
    if entity is None:
        entity = entities[0] if entities else None
    if entity is None:
        return render(request, "platform/unit_list.html", {"entity": None, "units": []})
    try:
        require_permission(request.user, "iam.unit.read", entity_id=entity.pk)
    except IamError:
        return _forbidden(request)
    units = OrganizationalUnit.objects.filter(entity=entity).select_related("parent")
    visible = visible_unit_ids(request.user, entity.pk, "iam.unit.read")
    if visible is not None:
        units = units.filter(pk__in=visible)
    return render(
        request, "platform/unit_list.html", {"entity": entity, "entities": entities, "units": units}
    )


def unit_create(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities = entities_for_user(request.user)
    raw_entity = request.GET.get("entity") or request.POST.get("entity")
    entity = next((item for item in entities if str(item.pk) == raw_entity), None)
    if entity is None:
        return _forbidden(request)
    try:
        require_permission(request.user, "iam.unit.create", entity_id=entity.pk, unit_id=None)
    except IamError:
        return _forbidden(request)

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        unit_type = request.POST.get("unit_type", "")
        raw_parent_id = request.POST.get("parent") or None
        parent_pk: int | None = None
        if raw_parent_id is not None:
            try:
                parent_pk = int(raw_parent_id)
            except ValueError:
                parent_pk = None
        try:
            with transaction.atomic():
                parent = None
                if parent_pk is not None:
                    parent = OrganizationalUnit.objects.filter(pk=parent_pk, entity=entity).first()
                unit = OrganizationalUnit(
                    entity=entity,
                    parent=parent,
                    code=code,
                    name=name,
                    unit_type=unit_type,
                )
                unit.full_clean()
                unit.save()
        except (IntegrityError, ValueError) as exc:
            messages.error(request, f"Unit tidak valid: {exc}")
        else:
            request_id, ip_address = _request_context(request)
            record_audit(
                actor=request.user,
                action="iam.unit.create",
                target_type="OrganizationalUnit",
                target_id=str(unit.pk),
                entity_id=entity.pk,
                unit_id=unit.pk,
                after_state={"code": code, "name": name, "unit_type": unit_type},
                request_id=request_id,
                ip_address=ip_address,
            )
            messages.success(request, "Unit organisasi berhasil dibuat.")
            return redirect("unit_list")
    return render(
        request,
        "platform/unit_form.html",
        {
            "entity": entity,
            "unit_types": UnitType.choices,
            "parents": OrganizationalUnit.objects.filter(entity=entity, is_active=True),
        },
    )


def role_assignment_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    entities = entities_for_user(request.user)
    raw_entity = request.GET.get("entity")
    entity = next((item for item in entities if str(item.pk) == raw_entity), None)
    if entity is None:
        entity = entities[0] if entities else None
    if entity is None:
        return render(request, "platform/role_assignment_list.html", {"entity": None})
    try:
        require_permission(request.user, "iam.role.read", entity_id=entity.pk)
    except IamError:
        return _forbidden(request)
    assignments = UserRole.objects.filter(entity=entity).select_related("user", "role", "unit")
    return render(
        request,
        "platform/role_assignment_list.html",
        {
            "entity": entity,
            "entities": entities,
            "assignments": assignments,
            "roles": Role.objects.filter(is_active=True),
            "users": User.objects.filter(is_active=True),
            "units": OrganizationalUnit.objects.filter(entity=entity, is_active=True),
        },
    )


def role_assign(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method != "POST":
        return _forbidden(request)
    try:
        entity = Entity.objects.get(pk=int(request.POST.get("entity", "0")))
        user = User.objects.get(pk=int(request.POST.get("user", "0")))
        role = Role.objects.get(pk=int(request.POST.get("role", "0")))
        unit_id = request.POST.get("unit") or None
        unit = (
            OrganizationalUnit.objects.filter(pk=unit_id, entity=entity).first()
            if unit_id
            else None
        )
        request_id, ip_address = _request_context(request)
        assign_role(
            actor=request.user,
            user=user,
            role=role,
            entity=entity,
            unit=unit,
            request_id=request_id,
            ip_address=ip_address,
        )
    except (Entity.DoesNotExist, User.DoesNotExist, Role.DoesNotExist, ValueError, IamError) as exc:
        messages.error(request, f"Penugasan gagal: {exc}")
    else:
        messages.success(request, "Peran berhasil diberikan.")
    return redirect("role_assignment_list")
