from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction

from .models import (
    AuditEvent,
    Entity,
    OrganizationalUnit,
    Permission,
    Role,
    RolePermission,
    UserRole,
)


class IamError(Exception):
    """Base error for identity and access operations."""


class IamPermissionDenied(IamError):
    """The actor does not hold the required permission in the requested scope."""


class IamValidationError(IamError):
    """The requested role assignment is inconsistent."""


@dataclass(frozen=True, slots=True)
class RoleScope:
    entity_id: int
    unit_id: int | None


def active_role_scopes(user: User, entity_id: int, permission_code: str) -> tuple[RoleScope, ...]:
    rows = (
        UserRole.objects.filter(
            user=user,
            entity_id=entity_id,
            is_active=True,
            role__is_active=True,
            role__role_permissions__permission__code=permission_code,
        )
        .values_list("entity_id", "unit_id")
        .distinct()
    )
    return tuple(RoleScope(entity_id=entity_id, unit_id=unit_id) for _, unit_id in rows)


def _unit_with_ancestors(unit_id: int) -> set[int]:
    result: set[int] = set()
    current: int | None = unit_id
    for _ in range(32):
        if current is None or current in result:
            break
        result.add(current)
        current = (
            OrganizationalUnit.objects.filter(pk=current)
            .values_list("parent_id", flat=True)
            .first()
        )
    return result


def has_permission(
    user: User,
    code: str,
    *,
    entity_id: int,
    unit_id: int | None = None,
) -> bool:
    """Deny by default. A grant on an ancestor unit covers its descendants."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    scopes = active_role_scopes(user, entity_id, code)
    if not scopes:
        return False
    if any(scope.unit_id is None for scope in scopes):
        return True
    if unit_id is None:
        return False
    granted = {scope.unit_id for scope in scopes if scope.unit_id is not None}
    return bool(granted.intersection(_unit_with_ancestors(unit_id)))


def require_permission(
    user: User,
    code: str,
    *,
    entity_id: int,
    unit_id: int | None = None,
) -> None:
    if not has_permission(user, code, entity_id=entity_id, unit_id=unit_id):
        raise IamPermissionDenied(f"Pengguna tidak memiliki izin {code} pada entitas {entity_id}.")


def has_permission_any_entity(user: User, code: str) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return UserRole.objects.filter(
        user=user,
        is_active=True,
        role__is_active=True,
        role__role_permissions__permission__code=code,
    ).exists()


def entities_for_user(user: User) -> list[Entity]:
    if not user.is_authenticated or not user.is_active:
        return []
    if user.is_superuser:
        return list(Entity.objects.filter(is_active=True))
    return list(
        Entity.objects.filter(
            is_active=True,
            user_roles__user=user,
            user_roles__is_active=True,
            user_roles__role__is_active=True,
        ).distinct()
    )


def visible_unit_ids(user: User, entity_id: int, permission_code: str) -> set[int] | None:
    """Return None for entity-wide access, otherwise the visible unit ids."""
    scopes = active_role_scopes(user, entity_id, permission_code)
    if not scopes:
        return set()
    if any(scope.unit_id is None for scope in scopes):
        return None
    visible: set[int] = set()
    for scope in scopes:
        if scope.unit_id is not None:
            visible.update(_descendants(scope.unit_id))
    return visible


def _descendants(root_id: int) -> set[int]:
    result = {root_id}
    frontier = [root_id]
    for _ in range(32):
        children = list(
            OrganizationalUnit.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)
        )
        new = [child for child in children if child not in result]
        if not new:
            break
        result.update(new)
        frontier = new
    return result


def record_audit(
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str,
    entity_id: int | None = None,
    unit_id: int | None = None,
    before_state: dict[str, object] | None = None,
    after_state: dict[str, object] | None = None,
    request_id: str = "",
    ip_address: str | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        entity_id=entity_id,
        unit_id=unit_id,
        before_state=before_state,
        after_state=after_state,
        request_id=request_id,
        ip_address=ip_address,
    )


@transaction.atomic
def assign_role(
    *,
    actor: User,
    user: User,
    role: Role,
    entity: Entity,
    unit: OrganizationalUnit | None = None,
    request_id: str = "",
    ip_address: str | None = None,
) -> UserRole:
    has_grant = has_permission(actor, "iam.role.assign", entity_id=entity.pk, unit_id=None)
    first_assignment = (
        actor.is_staff and not UserRole.objects.filter(entity=entity, is_active=True).exists()
    )
    if not has_grant and not first_assignment:
        raise IamPermissionDenied(
            f"Pengguna tidak memiliki izin iam.role.assign pada entitas {entity.pk}."
        )
    if unit is not None and unit.entity_id != entity.pk:
        raise IamValidationError("Unit harus berada pada entitas yang sama dengan peran.")
    assignment, created = UserRole.objects.get_or_create(
        user=user,
        role=role,
        entity=entity,
        unit=unit,
        defaults={"granted_by": actor, "is_active": True},
    )
    if not created and not assignment.is_active:
        assignment.is_active = True
        assignment.granted_by = actor
        assignment.save(update_fields=["is_active", "granted_by"])
    record_audit(
        actor=actor,
        action="iam.role.assign",
        target_type="UserRole",
        target_id=str(assignment.pk),
        entity_id=entity.pk,
        unit_id=unit.pk if unit else None,
        before_state={"is_active": not created},
        after_state={"is_active": True, "role": role.code},
        request_id=request_id,
        ip_address=ip_address,
    )
    return assignment


@transaction.atomic
def revoke_role(
    *,
    actor: User,
    assignment: UserRole,
    request_id: str = "",
    ip_address: str | None = None,
) -> None:
    require_permission(
        actor,
        "iam.role.assign",
        entity_id=assignment.entity_id,
        unit_id=assignment.unit_id,
    )
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    record_audit(
        actor=actor,
        action="iam.role.revoke",
        target_type="UserRole",
        target_id=str(assignment.pk),
        entity_id=assignment.entity_id,
        unit_id=assignment.unit_id,
        before_state={"is_active": True},
        after_state={"is_active": False},
        request_id=request_id,
        ip_address=ip_address,
    )


def role_codes(user: User, entity_id: int) -> set[str]:
    return set(
        UserRole.objects.filter(
            user=user,
            entity_id=entity_id,
            is_active=True,
            role__is_active=True,
        ).values_list("role__code", flat=True)
    )


def grant_default_permissions(role: Role) -> None:
    codes = DEFAULT_ROLE_PERMISSIONS.get(role.code, ())
    for code in codes:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"name": code.replace(".", " ").title()},
        )
        RolePermission.objects.get_or_create(role=role, permission=permission)


DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    Role.RECTOR: (
        "dashboard.read",
        "iam.entity.read",
        "iam.entity.create",
        "iam.entity.update",
        "iam.unit.read",
        "iam.unit.create",
        "iam.unit.update",
        "iam.role.read",
        "iam.role.assign",
        "iam.audit.read",
    ),
    Role.VICE_RECTOR: ("dashboard.read", "iam.entity.read", "iam.unit.read"),
    Role.HEAD_BUREAU: ("dashboard.read", "iam.unit.read", "iam.audit.read"),
    Role.FINANCE_MANAGER: (
        "dashboard.read",
        "iam.unit.read",
        "iam.role.read",
        "iam.role.assign",
        "ledger.journal.read",
        "ledger.journal.create",
        "ledger.period.close",
    ),
    Role.TREASURER: ("dashboard.read", "ledger.journal.read"),
    Role.VERIFICATION_OFFICER: ("dashboard.read",),
    Role.REVENUE_OFFICER: ("dashboard.read",),
}


def seed_roles() -> tuple[int, int]:
    created = 0
    for code, name in (
        (Role.RECTOR, "Rektor"),
        (Role.VICE_RECTOR, "Wakil Rektor"),
        (Role.HEAD_BUREAU, "Kepala Biro Keuangan dan Umum"),
        (Role.FINANCE_MANAGER, "Kepala Bagian Keuangan"),
        (Role.TREASURER, "Bendahara"),
        (Role.VERIFICATION_OFFICER, "Kasubbag Verifikasi"),
        (Role.REVENUE_OFFICER, "Bagian Pendapatan"),
    ):
        role, was_created = Role.objects.get_or_create(code=code, defaults={"name": name})
        created += int(was_created)
        grant_default_permissions(role)
    return created, len(DEFAULT_ROLE_PERMISSIONS)
