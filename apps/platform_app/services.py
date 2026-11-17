from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AuditEvent,
    Entity,
    Institution,
    OrganizationalUnit,
    Permission,
    Role,
    RolePermission,
    RoleScope,
    UserRole,
)


class IamError(Exception):
    """Base error for identity and access operations."""


class IamPermissionDenied(IamError):
    """The actor does not hold the required permission in the requested scope."""


class IamValidationError(IamError):
    """The requested role assignment is inconsistent."""


@dataclass(frozen=True, slots=True)
class RoleScopeGrant:
    entity_id: int
    institution_id: int | None
    unit_id: int | None
    scope_level: str


def _valid_until_query(effective_date: date, *, prefix: str = "") -> Q:
    field = f"{prefix}valid_until"
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gte": effective_date})


def active_role_scopes(
    user: User,
    entity_id: int,
    permission_code: str,
    *,
    on_date: date | None = None,
) -> tuple[RoleScopeGrant, ...]:
    effective_date = on_date or timezone.localdate()
    rows = (
        UserRole.objects.filter(
            user=user,
            entity_id=entity_id,
            is_active=True,
            revoked_at__isnull=True,
            valid_from__lte=effective_date,
            role__is_active=True,
            role__role_permissions__permission__code=permission_code,
        )
        .filter(_valid_until_query(effective_date))
        .values_list("entity_id", "institution_id", "unit_id", "scope_level")
        .distinct()
    )
    return tuple(
        RoleScopeGrant(
            entity_id=entity,
            institution_id=institution,
            unit_id=unit,
            scope_level=scope,
        )
        for entity, institution, unit, scope in rows
    )


def _unit_ancestors(
    unit_id: int,
    *,
    entity_id: int,
    institution_id: int | None,
) -> set[int]:
    """Return target unit and its ancestors, without crossing entity/institution."""
    result: set[int] = set()
    current: int | None = unit_id
    for _ in range(100):
        if current is None or current in result:
            break
        unit = (
            OrganizationalUnit.objects.filter(
                pk=current,
                entity_id=entity_id,
                institution_id=institution_id,
            )
            .values_list("pk", "parent_id")
            .first()
        )
        if unit is None:
            break
        current_id, parent_id = unit
        result.add(current_id)
        current = parent_id
    return result


def _unit_descendants(
    root_id: int,
    *,
    entity_id: int,
    institution_id: int | None,
) -> set[int]:
    result = {root_id}
    frontier = [root_id]
    for _ in range(100):
        children = list(
            OrganizationalUnit.objects.filter(
                entity_id=entity_id,
                institution_id=institution_id,
                parent_id__in=frontier,
                is_active=True,
            ).values_list("pk", flat=True)
        )
        new = [child for child in children if child not in result]
        if not new:
            break
        result.update(new)
        frontier = new
    return result


def has_permission(
    user: User,
    code: str,
    *,
    entity_id: int,
    institution_id: int | None = None,
    unit_id: int | None = None,
    on_date: date | None = None,
) -> bool:
    """Deny by default and evaluate a permission within its organization scope.

    Entity grants cover the whole legal entity; institution grants cover one
    institution; unit grants cover the unit and its descendants. Superusers
    retain an explicit break-glass bypass for platform recovery.
    """
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return Entity.objects.filter(pk=entity_id, is_active=True).exists()

    if institution_id is not None and not Institution.objects.filter(
        pk=institution_id,
        entity_id=entity_id,
        is_active=True,
    ).exists():
        return False

    target_unit: OrganizationalUnit | None = None
    if unit_id is not None:
        target_unit = (
            OrganizationalUnit.objects.filter(
                pk=unit_id,
                entity_id=entity_id,
                is_active=True,
            )
            .only("pk", "institution_id")
            .first()
        )
        if target_unit is None:
            return False
        if institution_id is not None and target_unit.institution_id != institution_id:
            return False
        institution_id = target_unit.institution_id

    for scope in active_role_scopes(user, entity_id, code, on_date=on_date):
        if scope.scope_level == RoleScope.ENTITY:
            return True
        if (
            scope.scope_level == RoleScope.INSTITUTION
            and institution_id is not None
            and scope.institution_id == institution_id
        ):
            return True
        if (
            scope.scope_level == RoleScope.UNIT
            and target_unit is not None
            and scope.unit_id is not None
            and scope.unit_id
            in _unit_ancestors(
                target_unit.pk,
                entity_id=entity_id,
                institution_id=institution_id,
            )
        ):
            return True
    return False


def require_permission(
    user: User,
    code: str,
    *,
    entity_id: int,
    institution_id: int | None = None,
    unit_id: int | None = None,
    on_date: date | None = None,
) -> None:
    if not has_permission(
        user,
        code,
        entity_id=entity_id,
        institution_id=institution_id,
        unit_id=unit_id,
        on_date=on_date,
    ):
        raise IamPermissionDenied(
            f"Pengguna tidak memiliki izin {code} pada scope entitas/institusi/unit yang diminta."
        )


def has_permission_any_entity(user: User, code: str) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return Entity.objects.filter(is_active=True).exists()
    today = timezone.localdate()
    return (
        UserRole.objects.filter(
            user=user,
            is_active=True,
            revoked_at__isnull=True,
            valid_from__lte=today,
            role__is_active=True,
            role__role_permissions__permission__code=code,
            entity__is_active=True,
        )
        .filter(_valid_until_query(today))
        .exists()
    )


def entities_for_user(user: User) -> list[Entity]:
    if not user.is_authenticated or not user.is_active:
        return []
    if user.is_superuser:
        return list(Entity.objects.filter(is_active=True))
    today = timezone.localdate()
    return list(
        Entity.objects.filter(
            is_active=True,
            user_roles__user=user,
            user_roles__is_active=True,
            user_roles__revoked_at__isnull=True,
            user_roles__valid_from__lte=today,
            user_roles__role__is_active=True,
        )
        .filter(_valid_until_query(today, prefix="user_roles__"))
        .distinct()
    )


def visible_unit_ids(
    user: User,
    entity_id: int,
    permission_code: str,
    *,
    institution_id: int | None = None,
) -> set[int] | None:
    """Return visible unit IDs; None represents entity-wide visibility."""
    if user.is_superuser:
        return None
    scopes = active_role_scopes(user, entity_id, permission_code)
    if any(scope.scope_level == RoleScope.ENTITY for scope in scopes):
        return None

    visible: set[int] = set()
    for scope in scopes:
        if scope.scope_level == RoleScope.INSTITUTION and scope.institution_id is not None:
            if institution_id is not None and scope.institution_id != institution_id:
                continue
            visible.update(
                OrganizationalUnit.objects.filter(
                    entity_id=entity_id,
                    institution_id=scope.institution_id,
                    is_active=True,
                ).values_list("pk", flat=True)
            )
        elif scope.scope_level == RoleScope.UNIT and scope.unit_id is not None:
            root = OrganizationalUnit.objects.filter(
                pk=scope.unit_id,
                entity_id=entity_id,
                is_active=True,
            ).only("institution_id").first()
            if root is None or (institution_id is not None and root.institution_id != institution_id):
                continue
            visible.update(
                _unit_descendants(
                    scope.unit_id,
                    entity_id=entity_id,
                    institution_id=root.institution_id,
                )
            )
    return visible


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
    institution: Institution | None = None,
    scope_level: str | None = None,
    request_id: str = "",
    ip_address: str | None = None,
) -> UserRole:
    has_grant = has_permission(
        actor,
        "iam.role.assign",
        entity_id=entity.pk,
        institution_id=institution.pk if institution else None,
        unit_id=unit.pk if unit else None,
    )
    first_assignment = actor.is_staff and not UserRole.objects.filter(
        entity=entity,
        is_active=True,
    ).exists()
    if not has_grant and not first_assignment:
        raise IamPermissionDenied(
            f"Pengguna tidak memiliki izin iam.role.assign pada entitas {entity.pk}."
        )
    if not role.is_active or not entity.is_active:
        raise IamValidationError("Role dan badan hukum harus aktif.")

    if unit is not None:
        if unit.entity_id != entity.pk or not unit.is_active:
            raise IamValidationError("Unit harus aktif dan berada pada badan hukum yang sama.")
        if institution is None:
            institution = unit.institution
        if unit.institution_id != (institution.pk if institution else None):
            raise IamValidationError("Unit harus berada pada institusi yang dipilih.")
        inferred_scope = RoleScope.UNIT
    elif institution is not None:
        if institution.entity_id != entity.pk or not institution.is_active:
            raise IamValidationError("Institusi harus aktif dan berada pada badan hukum yang sama.")
        inferred_scope = RoleScope.INSTITUTION
    else:
        inferred_scope = RoleScope.ENTITY

    selected_scope = scope_level or inferred_scope
    if selected_scope != inferred_scope:
        raise IamValidationError("Level scope tidak sesuai dengan badan hukum/institusi/unit.")

    today = timezone.localdate()
    lookup = {
        "user": user,
        "role": role,
        "entity": entity,
        "scope_level": selected_scope,
        "institution": institution,
        "unit": unit,
    }
    expired_assignments = UserRole.objects.filter(
        **lookup,
        is_active=True,
        valid_until__lt=today,
    )
    for expired in expired_assignments:
        expired.is_active = False
        expired.save(update_fields=["is_active"])
        record_audit(
            actor=actor,
            action="iam.role.expire",
            target_type="UserRole",
            target_id=str(expired.pk),
            entity_id=entity.pk,
            unit_id=unit.pk if unit else None,
            before_state={"is_active": True, "valid_until": expired.valid_until.isoformat()},
            after_state={"is_active": False, "reason": "validity_period_ended"},
            request_id=request_id,
            ip_address=ip_address,
        )

    assignment, created = UserRole.objects.get_or_create(
        **lookup,
        is_active=True,
        defaults={"granted_by": actor, "valid_from": today},
    )
    before_state = {
        "is_active": assignment.is_active if not created else False,
        "valid_from": assignment.valid_from.isoformat() if not created else None,
        "valid_until": assignment.valid_until.isoformat() if assignment.valid_until else None,
    }
    record_audit(
        actor=actor,
        action="iam.role.assign",
        target_type="UserRole",
        target_id=str(assignment.pk),
        entity_id=entity.pk,
        unit_id=unit.pk if unit else None,
        before_state=before_state,
        after_state={
            "is_active": True,
            "role": role.code,
            "scope_level": selected_scope,
            "institution_id": institution.pk if institution else None,
            "unit_id": unit.pk if unit else None,
            "valid_from": assignment.valid_from.isoformat(),
            "valid_until": None,
        },
        request_id=request_id,
        ip_address=ip_address,
    )
    return assignment


@transaction.atomic
def revoke_role(
    *,
    actor: User,
    assignment: UserRole,
    reason: str = "",
    request_id: str = "",
    ip_address: str | None = None,
) -> None:
    require_permission(
        actor,
        "iam.role.assign",
        entity_id=assignment.entity_id,
        institution_id=assignment.institution_id,
        unit_id=assignment.unit_id,
    )
    if not assignment.is_active or assignment.revoked_at is not None:
        return
    assignment.is_active = False
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = actor
    assignment.revocation_reason = reason
    assignment.save(
        update_fields=["is_active", "revoked_at", "revoked_by", "revocation_reason"]
    )
    record_audit(
        actor=actor,
        action="iam.role.revoke",
        target_type="UserRole",
        target_id=str(assignment.pk),
        entity_id=assignment.entity_id,
        unit_id=assignment.unit_id,
        before_state={"is_active": True},
        after_state={
            "is_active": False,
            "revoked_at": assignment.revoked_at.isoformat(),
            "reason": reason,
        },
        request_id=request_id,
        ip_address=ip_address,
    )


def role_codes(user: User, entity_id: int) -> set[str]:
    today = timezone.localdate()
    return set(
        UserRole.objects.filter(
            user=user,
            entity_id=entity_id,
            is_active=True,
            revoked_at__isnull=True,
            valid_from__lte=today,
            role__is_active=True,
        )
        .filter(_valid_until_query(today))
        .values_list("role__code", flat=True)
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
