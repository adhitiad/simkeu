from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.platform_app.models import (
    Entity,
    Institution,
    OrganizationalUnit,
    Position,
    PositionAssignment,
    Role,
    RoleScope,
    UserRole,
)
from apps.platform_app.services import assign_role, has_permission, seed_roles


@pytest.fixture()
def p0_graph() -> tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit]:
    seed_roles()
    actor = User.objects.create_user(
        username=f"p0-admin-{uuid4().hex[:8]}",
        password="test-password-only",
        is_staff=True,
    )
    target = User.objects.create_user(
        username=f"p0-user-{uuid4().hex[:8]}",
        password="test-password-only",
    )
    entity = Entity.objects.create(
        code=f"YYS-{uuid4().hex[:8]}",
        name="Yayasan Pendidikan Contoh",
        legal_form="foundation",
    )
    institution = Institution.objects.create(
        entity=entity,
        code="PTS-A",
        name="Universitas Contoh",
        institution_type="university",
    )
    faculty = OrganizationalUnit.objects.create(
        entity=entity,
        institution=institution,
        code="FEB",
        name="Fakultas Ekonomi",
        unit_type="faculty",
    )
    study_program = OrganizationalUnit.objects.create(
        entity=entity,
        institution=institution,
        parent=faculty,
        code="AKT",
        name="Program Studi Akuntansi",
        unit_type="study_program",
        is_cost_center=True,
    )
    rector = Role.objects.get(code=Role.RECTOR)
    assign_role(actor=actor, user=actor, role=rector, entity=entity)
    return actor, target, entity, institution, faculty, study_program


@pytest.mark.django_db
def test_entity_is_legal_body_and_can_operate_multiple_institutions(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, _, entity, institution, _, _ = p0_graph
    other = Institution.objects.create(
        entity=entity,
        code="PTS-B",
        name="Institut Contoh",
        institution_type="institute",
    )
    assert institution.entity_id == entity.pk
    assert other.entity_id == entity.pk
    assert entity.legal_form == "foundation"


@pytest.mark.django_db
def test_unit_scope_is_bound_to_same_entity_and_institution(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, _, entity, institution, faculty, _ = p0_graph
    other_entity = Entity.objects.create(
        code=f"YYS-{uuid4().hex[:8]}",
        name="Yayasan Lain",
        legal_form="foundation",
    )
    other_institution = Institution.objects.create(
        entity=other_entity,
        code="PTS-X",
        name="PTS Lain",
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        OrganizationalUnit.objects.create(
            entity=other_entity,
            institution=other_institution,
            parent=faculty,
            code="BAD",
            name="Unit lintas badan hukum",
            unit_type="unit",
        )
    assert faculty.entity_id == entity.pk
    assert faculty.institution_id == institution.pk


@pytest.mark.django_db
def test_database_rejects_unit_hierarchy_cycle(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, _, _, _, faculty, study_program = p0_graph
    with pytest.raises(DatabaseError), transaction.atomic():
        OrganizationalUnit.objects.filter(pk=faculty.pk).update(parent=study_program)


@pytest.mark.django_db
def test_institution_role_scope_does_not_cross_institutions(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    actor, target, entity, institution, _, study_program = p0_graph
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    assign_role(
        actor=actor,
        user=target,
        role=role,
        entity=entity,
        institution=institution,
    )
    other = Institution.objects.create(
        entity=entity,
        code="PTS-B",
        name="Institut Contoh",
        institution_type="institute",
    )
    assert has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        institution_id=institution.pk,
    )
    assert has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        unit_id=study_program.pk,
    )
    assert not has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        institution_id=other.pk,
    )


@pytest.mark.django_db
def test_unit_role_scope_inherits_only_to_descendants(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    actor, target, entity, institution, faculty, study_program = p0_graph
    sibling = OrganizationalUnit.objects.create(
        entity=entity,
        institution=institution,
        code="FT",
        name="Fakultas Teknik",
        unit_type="faculty",
    )
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    assert has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        institution_id=institution.pk,
        unit_id=study_program.pk,
    )
    assert not has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        institution_id=institution.pk,
        unit_id=sibling.pk,
    )


@pytest.mark.django_db
def test_role_assignment_respects_validity_dates(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, target, entity, _, _, _ = p0_graph
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    tomorrow = timezone.localdate() + timedelta(days=1)
    assignment = UserRole.objects.create(
        user=target,
        role=role,
        entity=entity,
        scope_level=RoleScope.ENTITY,
        valid_from=tomorrow,
    )
    assert not has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        on_date=timezone.localdate(),
    )
    assert has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        on_date=tomorrow,
    )
    assert not has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        on_date=tomorrow + timedelta(days=1),
    )
    assignment.valid_until = tomorrow
    assignment.save(update_fields=["valid_until"])
    assert not has_permission(
        target,
        "dashboard.read",
        entity_id=entity.pk,
        on_date=tomorrow + timedelta(days=1),
    )


@pytest.mark.django_db
def test_position_is_separate_from_role_and_tracks_appointment(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, target, entity, institution, faculty, _ = p0_graph
    position = Position.objects.create(
        code="KABAG-KEU",
        name="Kepala Bagian Keuangan",
        category="structural",
    )
    assignment = PositionAssignment.objects.create(
        user=target,
        position=position,
        entity=entity,
        institution=institution,
        unit=faculty,
        valid_from=date(2026, 1, 1),
        appointment_reference="SK/001/2026",
    )
    assert assignment.position.name == "Kepala Bagian Keuangan"
    assert assignment.unit_id == faculty.pk
    assert not UserRole.objects.filter(user=target, entity=entity).exists()


@pytest.mark.django_db
def test_database_rejects_role_assignment_to_other_entity(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    _, target, entity, _, _, _ = p0_graph
    other_entity = Entity.objects.create(
        code=f"YYS-{uuid4().hex[:8]}",
        name="Yayasan Lain",
        legal_form="foundation",
    )
    other_institution = Institution.objects.create(
        entity=other_entity,
        code="PTS-X",
        name="PTS Lain",
    )
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    with pytest.raises(DatabaseError), transaction.atomic():
        UserRole.objects.create(
            user=target,
            role=role,
            entity=entity,
            institution=other_institution,
            scope_level=RoleScope.INSTITUTION,
        )


@pytest.mark.django_db
def test_entity_scope_assignment_is_unchanged_for_legacy_user_roles(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    actor, target, entity, _, _, _ = p0_graph
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    assignment = assign_role(actor=actor, user=target, role=role, entity=entity)
    assert assignment.scope_level == RoleScope.ENTITY
    assert assignment.institution_id is None
    assert assignment.unit_id is None


@pytest.mark.django_db
def test_revocation_preserves_assignment_history_and_regrant_creates_new_row(
    p0_graph: tuple[User, User, Entity, Institution, OrganizationalUnit, OrganizationalUnit],
) -> None:
    actor, target, entity, _, faculty, _ = p0_graph
    role = Role.objects.get(code=Role.REVENUE_OFFICER)
    first = assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)
    from apps.platform_app.services import revoke_role

    revoke_role(actor=actor, assignment=first, reason="Perubahan penugasan")
    second = assign_role(actor=actor, user=target, role=role, entity=entity, unit=faculty)

    first.refresh_from_db()
    assert first.pk != second.pk
    assert first.is_active is False
    assert first.revoked_at is not None
    assert first.revocation_reason == "Perubahan penugasan"
    assert second.is_active is True
