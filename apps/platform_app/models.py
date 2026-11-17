from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class LegalForm(models.TextChoices):
    FOUNDATION = "foundation", "Yayasan"
    ASSOCIATION = "association", "Perkumpulan"
    OTHER = "other", "Bentuk badan hukum lain"


class InstitutionType(models.TextChoices):
    UNIVERSITY = "university", "Universitas"
    INSTITUTE = "institute", "Institut"
    COLLEGE = "college", "Sekolah Tinggi"
    POLYTECHNIC = "polytechnic", "Politeknik"
    ACADEMY = "academy", "Akademi"
    OTHER = "other", "Perguruan tinggi lain"


class UnitType(models.TextChoices):
    # Keep legacy values so existing unit records and forms remain readable.
    LEGACY_UNIVERSITY = "university", "Universitas (unit lama)"
    FACULTY = "faculty", "Fakultas"
    LEGACY_DEPARTMENT = "department", "Program studi (unit lama)"
    UNIT = "unit", "Unit kerja"
    CAMPUS = "campus", "Kampus"
    DEPARTMENT = "dept", "Departemen"
    STUDY_PROGRAM = "study_program", "Program studi"
    BUREAU = "bureau", "Biro"
    SECTION = "section", "Bagian"
    SUBSECTION = "subsection", "Subbagian"
    LABORATORY = "laboratory", "Laboratorium"
    BUSINESS = "business", "Unit usaha"
    SUPPORT = "support", "Unit pendukung"


class PositionCategory(models.TextChoices):
    GOVERNING = "governing", "Organ badan penyelenggara"
    STRUCTURAL = "structural", "Jabatan struktural"
    FUNCTIONAL = "functional", "Jabatan fungsional"
    STAFF = "staff", "Pelaksana"
    OTHER = "other", "Lainnya"


class RoleScope(models.TextChoices):
    ENTITY = "entity", "Badan hukum"
    INSTITUTION = "institution", "Institusi"
    UNIT = "unit", "Unit organisasi"


class Entity(models.Model):
    """Legal entity / badan hukum penyelenggara and financial reporting boundary."""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    legal_form = models.CharField(
        max_length=20,
        choices=LegalForm.choices,
        default=LegalForm.OTHER,
    )
    address = models.TextField(blank=True)
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_entities"
        ordering: ClassVar[list[str]] = ["code"]
        verbose_name = "Badan hukum penyelenggara"
        verbose_name_plural = "Badan hukum penyelenggara"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(fiscal_year_start_month__gte=1, fiscal_year_start_month__lte=12),
                name="platform_entity_fy_month_ck",
            ),
            models.CheckConstraint(
                condition=Q(legal_form__in=[choice.value for choice in LegalForm]),
                name="platform_entity_legal_form_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Institution(models.Model):
    """A PTS (university/institute/etc.) operated by one legal entity."""

    id = models.BigAutoField(primary_key=True)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="institutions")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    institution_type = models.CharField(
        max_length=20,
        choices=InstitutionType.choices,
        default=InstitutionType.UNIVERSITY,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_institutions"
        ordering: ClassVar[list[str]] = ["entity_id", "code"]
        verbose_name = "Institusi perguruan tinggi"
        verbose_name_plural = "Institusi perguruan tinggi"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity", "code"],
                name="platform_institution_entity_code_uniq",
            ),
            models.CheckConstraint(
                condition=Q(institution_type__in=[choice.value for choice in InstitutionType]),
                name="platform_institution_type_ck",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["entity", "is_active"],
                name="platform_inst_entity_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class OrganizationalUnit(models.Model):
    id = models.BigAutoField(primary_key=True)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="units")
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="units",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    unit_type = models.CharField(max_length=20, choices=UnitType.choices)
    is_cost_center = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_org_units"
        ordering: ClassVar[list[str]] = ["entity_id", "code"]
        verbose_name = "Unit organisasi"
        verbose_name_plural = "Unit organisasi"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="platform_unit_entity_code_uniq"
            ),
            models.CheckConstraint(
                condition=Q(unit_type__in=[choice.value for choice in UnitType]),
                name="platform_unit_type_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["entity", "institution", "parent"],
                name="platform_unit_tree_scope_idx",
            ),
            models.Index(
                fields=["entity", "is_cost_center", "is_active"],
                name="platform_unit_cost_center_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.institution_id and self.institution.entity_id != self.entity_id:
            raise ValidationError({"institution": "Institusi harus berada pada badan hukum yang sama."})
        if self.parent_id and self.parent:
            if (
                self.parent.entity_id != self.entity_id
                or self.parent.institution_id != self.institution_id
            ):
                raise ValidationError({"parent": "Unit induk harus berada pada badan hukum dan institusi yang sama."})
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({"parent": "Unit tidak boleh menjadi induk dirinya sendiri."})


class Position(models.Model):
    """A structural/functional office; deliberately separate from application Role."""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=PositionCategory.choices)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_positions"
        ordering: ClassVar[list[str]] = ["code"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(category__in=[choice.value for choice in PositionCategory]),
                name="platform_position_category_ck",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PositionAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="simkeu_position_assignments",
    )
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="assignments")
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="position_assignments")
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="position_assignments",
    )
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="position_assignments",
    )
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    appointment_reference = models.CharField(max_length=100, blank=True)
    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_position_assignments"
        ordering: ClassVar[list[str]] = ["-valid_from"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="platform_position_dates_ck",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["user", "valid_from", "valid_until"], name="platform_pos_user_dates_idx"),
            models.Index(fields=["entity", "unit"], name="platform_pos_entity_unit_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.position}"

    def clean(self) -> None:
        super().clean()
        if self.institution_id and self.institution.entity_id != self.entity_id:
            raise ValidationError({"institution": "Institusi tidak sesuai dengan badan hukum."})
        if self.unit_id:
            unit = self.unit
            if unit.entity_id != self.entity_id or unit.institution_id != self.institution_id:
                raise ValidationError({"unit": "Unit tidak sesuai dengan badan hukum/institusi."})


class Role(models.Model):
    RECTOR = "RECTOR"
    VICE_RECTOR = "VICE_RECTOR"
    HEAD_BUREAU = "HEAD_BUREAU"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    TREASURER = "TREASURER"
    VERIFICATION_OFFICER = "VERIFICATION_OFFICER"
    REVENUE_OFFICER = "REVENUE_OFFICER"

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "platform_roles"
        ordering: ClassVar[list[str]] = ["code"]

    def __str__(self) -> str:
        return self.name


class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "platform_permissions"
        ordering: ClassVar[list[str]] = ["code"]

    def __str__(self) -> str:
        return self.code


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )

    class Meta:
        db_table = "platform_role_permissions"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="platform_role_permission_uniq"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role.code}:{self.permission.code}"


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="simkeu_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="user_roles")
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    scope_level = models.CharField(
        max_length=16,
        choices=RoleScope.choices,
        default=RoleScope.ENTITY,
    )
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    revocation_reason = models.TextField(blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_user_roles"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="platform_user_role_dates_ck",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scope_level=RoleScope.ENTITY, institution__isnull=True, unit__isnull=True)
                    | Q(scope_level=RoleScope.INSTITUTION, institution__isnull=False, unit__isnull=True)
                    | Q(scope_level=RoleScope.UNIT, unit__isnull=False)
                ),
                name="platform_user_role_scope_shape_ck",
            ),
            models.CheckConstraint(
                condition=Q(scope_level__in=[choice.value for choice in RoleScope]),
                name="platform_user_role_scope_value_ck",
            ),
            models.UniqueConstraint(
                fields=["user", "role", "entity", "scope_level", "institution", "unit"],
                name="platform_user_role_scope_uniq",
                condition=Q(is_active=True),
                nulls_distinct=False,
            ),
        ]

    def __str__(self) -> str:
        scope = self.unit.code if self.unit else self.institution.code if self.institution else "*"
        return f"{self.user_id}:{self.role.code}@{self.entity_id}:{scope}"

    def clean(self) -> None:
        super().clean()
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Tanggal akhir tidak boleh sebelum tanggal mulai."})
        if self.institution_id and self.institution.entity_id != self.entity_id:
            raise ValidationError({"institution": "Institusi harus berada pada entitas yang sama."})
        if self.unit_id:
            unit = self.unit
            if unit.entity_id != self.entity_id or unit.institution_id != self.institution_id:
                raise ValidationError({"unit": "Unit harus berada pada entitas dan institusi yang sama."})
        if self.scope_level == RoleScope.ENTITY and (self.institution_id or self.unit_id):
            raise ValidationError("Scope badan hukum tidak boleh menunjuk institusi atau unit.")
        if self.scope_level == RoleScope.INSTITUTION and (not self.institution_id or self.unit_id):
            raise ValidationError("Scope institusi wajib menunjuk institusi dan tanpa unit.")
        if self.scope_level == RoleScope.UNIT and not self.unit_id:
            raise ValidationError("Scope unit wajib menunjuk unit.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=120)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    unit_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    request_id = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_audit_events"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["entity_id", "action"], name="platform_audit_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.target_type}:{self.target_id}"


class OutboxEvent(models.Model):
    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_outbox"
        ordering: ClassVar[list[str]] = ["created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id}"
