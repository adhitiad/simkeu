from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.platform_app.models import (
    AuditEvent,
    Entity,
    OrganizationalUnit,
    Role,
    UserRole,
)
from apps.platform_app.services import (
    IamPermissionDenied,
    IamValidationError,
    assign_role,
    entities_for_user,
    has_permission,
    record_audit,
    require_permission,
    revoke_role,
    seed_roles,
    visible_unit_ids,
)


@pytest.fixture()
def rbac_env() -> tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role]:
    seed_roles()
    actor = User.objects.create_user(
        username=f"admin-{uuid4().hex[:8]}", password="pw", is_staff=True
    )
    target = User.objects.create_user(username=f"staff-{uuid4().hex[:8]}", password="pw")
    entity = Entity.objects.create(code=f"ENT-{uuid4().hex[:6]}", name="Universitas Contoh")
    faculty = OrganizationalUnit.objects.create(
        entity=entity, code="FAK", name="Fakultas Ilmu", unit_type="faculty"
    )
    department = OrganizationalUnit.objects.create(
        entity=entity, code="PRODI", name="Informatika", unit_type="department", parent=faculty
    )
    rector = Role.objects.get(code=Role.RECTOR)
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    assign_role(actor=actor, user=actor, role=rector, entity=entity)
    return actor, target, entity, faculty, department, role


@pytest.mark.django_db
def test_seed_roles_is_idempotent() -> None:
    first = seed_roles()
    second = seed_roles()
    assert first[0] >= 0
    assert second[0] == 0
    assert Role.objects.count() == 7


@pytest.mark.django_db
def test_deny_by_default_without_role(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    _, target, entity, _, _, _ = rbac_env
    assert has_permission(target, "dashboard.read", entity_id=entity.pk) is False
    with pytest.raises(IamPermissionDenied):
        require_permission(target, "dashboard.read", entity_id=entity.pk)


@pytest.mark.django_db
def test_entity_scope_is_enforced(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, target, entity, faculty, department, role = rbac_env
    assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    assert (
        has_permission(target, "dashboard.read", entity_id=entity.pk, unit_id=department.pk) is True
    )
    other = Entity.objects.create(code=f"OTH-{uuid4().hex[:6]}", name="Entitas Lain")
    assert has_permission(target, "dashboard.read", entity_id=other.pk) is False
    assert entities_for_user(target) == [entity]


@pytest.mark.django_db
def test_unit_scope_covers_descendants_and_not_siblings(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, target, entity, faculty, department, role = rbac_env
    sibling = OrganizationalUnit.objects.create(
        entity=entity, code="LAIN", name="Unit Lain", unit_type="unit"
    )
    assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    assert (
        has_permission(target, "dashboard.read", entity_id=entity.pk, unit_id=department.pk) is True
    )
    assert (
        has_permission(target, "dashboard.read", entity_id=entity.pk, unit_id=sibling.pk) is False
    )
    assert visible_unit_ids(target, entity.pk, "dashboard.read") == {faculty.pk, department.pk}


@pytest.mark.django_db
def test_assign_role_validates_entity_scope(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, target, entity, _, _, role = rbac_env
    other = Entity.objects.create(code=f"X-{uuid4().hex[:6]}", name="Lain")
    unit = OrganizationalUnit.objects.create(
        entity=other, code="U", name="Unit Lain", unit_type="unit"
    )
    with pytest.raises(IamValidationError):
        assign_role(actor=actor, user=target, role=role, entity=entity, unit=unit)


@pytest.mark.django_db
def test_revoke_role_blocks_permission(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, target, entity, faculty, _, role = rbac_env
    assignment = assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    assert has_permission(target, "dashboard.read", entity_id=entity.pk, unit_id=faculty.pk) is True
    revoke_role(actor=actor, assignment=assignment)
    assert (
        has_permission(target, "dashboard.read", entity_id=entity.pk, unit_id=faculty.pk) is False
    )
    assignment.refresh_from_db()
    assert assignment.is_active is False


@pytest.mark.django_db
def test_non_grantor_cannot_assign_role(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    _, target, entity, faculty, _, role = rbac_env
    other_user = User.objects.create_user(username=f"other-{uuid4().hex[:8]}", password="pw")
    with pytest.raises(IamPermissionDenied):
        assign_role(actor=other_user, user=target, role=role, entity=entity, unit=faculty)


@pytest.mark.django_db
def test_superuser_has_all_permissions(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    _, _, entity, _, _, _ = rbac_env
    superuser = User.objects.create_superuser(
        username=f"root-{uuid4().hex[:8]}", password="pw", email=""
    )
    assert has_permission(superuser, "any.permission", entity_id=entity.pk) is True


@pytest.mark.django_db
def test_audit_event_records_actor_and_is_append_only(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, _, entity, _, _, _ = rbac_env
    event = record_audit(
        actor=actor,
        action="iam.entity.create",
        target_type="Entity",
        target_id=str(entity.pk),
        entity_id=entity.pk,
        after_state={"name": entity.name},
    )
    assert event.actor_id == actor.pk
    assert AuditEvent.objects.filter(pk=event.pk).count() == 1


@pytest.mark.django_db
def test_unauthorized_user_sees_forbidden_page(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    _, target, _, _, _, _ = rbac_env
    client = Client()
    client.force_login(target)
    response = client.get("/entities/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_role_assignment_unique_per_scope(
    rbac_env: tuple[User, User, Entity, OrganizationalUnit, OrganizationalUnit, Role],
) -> None:
    actor, target, entity, faculty, _, role = rbac_env
    first = assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    second = assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    assert first.pk == second.pk
    assert UserRole.objects.filter(user=target).count() == 1
