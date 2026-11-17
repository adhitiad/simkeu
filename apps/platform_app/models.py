from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Entity(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_entities"
        ordering: ClassVar[list[str]] = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class UnitType(models.TextChoices):
    UNIVERSITY = "university", "Universitas"
    FACULTY = "faculty", "Fakultas"
    DEPARTMENT = "department", "Program Studi"
    UNIT = "unit", "Unit Kerja"


class OrganizationalUnit(models.Model):
    id = models.BigAutoField(primary_key=True)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="units")
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    unit_type = models.CharField(max_length=16, choices=UnitType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_org_units"
        ordering: ClassVar[list[str]] = ["entity_id", "code"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entity", "code"], name="platform_unit_entity_code_uniq"
            ),
            models.CheckConstraint(
                condition=Q(unit_type__in=[choice.value for choice in UnitType]),
                name="platform_unit_type_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        super().clean()
        parent = self.parent
        if self.parent_id is not None and parent is not None:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "Unit tidak boleh menjadi induk dirinya sendiri."})
            if parent.entity_id != self.entity_id:
                raise ValidationError({"parent": "Induk unit harus berada pada entitas yang sama."})


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
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    is_active = models.BooleanField(default=True)
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
            models.UniqueConstraint(
                fields=["user", "role", "entity", "unit"],
                name="platform_user_role_uniq",
            ),
        ]

    def __str__(self) -> str:
        scope = self.unit.code if self.unit else "*"
        return f"{self.user_id}:{self.role.code}@{self.entity_id}:{scope}"

    def clean(self) -> None:
        super().clean()
        unit = self.unit
        if self.unit_id is not None and unit is not None and unit.entity_id != self.entity_id:
            raise ValidationError({"unit": "Unit harus berada pada entitas yang sama."})


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
