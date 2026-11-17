import json

from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder

from .models import (
    AuditEvent,
    Entity,
    Institution,
    OrganizationalUnit,
    OutboxEvent,
    Permission,
    Position,
    PositionAssignment,
    Role,
    RolePermission,
    UserRole,
)
from .services import record_audit


class AuditedAdminMixin:
    """Audit admin master-data changes and prohibit hard deletion."""

    def _snapshot(self, obj):
        values = {
            field.name: getattr(obj, field.attname)
            for field in obj._meta.concrete_fields
            if field.name not in {"created_at", "updated_at"}
        }
        return json.loads(json.dumps(values, cls=DjangoJSONEncoder))

    def save_model(self, request, obj, form, change):
        before = None
        if change:
            previous = obj.__class__.objects.get(pk=obj.pk)
            before = self._snapshot(previous)
        super().save_model(request, obj, form, change)
        entity_id = obj.pk if isinstance(obj, Entity) else getattr(obj, "entity_id", None)
        unit_id = obj.pk if isinstance(obj, OrganizationalUnit) else getattr(obj, "unit_id", None)
        record_audit(
            actor=request.user,
            action=f"iam.{obj._meta.model_name}.{'update' if change else 'create'}",
            target_type=obj._meta.label,
            target_id=str(obj.pk),
            entity_id=entity_id,
            unit_id=unit_id,
            before_state=before,
            after_state=self._snapshot(obj),
            request_id=request.headers.get("X-Request-ID", ""),
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    def has_delete_permission(self, request, obj=None):
        # Deactivate master records instead; financial and access history must remain.
        return False


@admin.register(Entity)
class EntityAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "legal_form", "fiscal_year_start_month", "is_active")
    list_filter = ("legal_form", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")


@admin.register(Institution)
class InstitutionAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "entity", "institution_type", "is_active")
    list_filter = ("institution_type", "is_active", "entity")
    search_fields = ("code", "name", "entity__name")
    autocomplete_fields = ("entity",)
    readonly_fields = ("id", "created_at")


@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "entity",
        "institution",
        "parent",
        "unit_type",
        "is_cost_center",
        "is_active",
    )
    list_filter = ("entity", "institution", "unit_type", "is_cost_center", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("entity", "institution", "parent")
    readonly_fields = ("id", "created_at")


@admin.register(Position)
class PositionAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")


@admin.register(PositionAssignment)
class PositionAssignmentAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = (
        "user",
        "position",
        "entity",
        "institution",
        "unit",
        "valid_from",
        "valid_until",
    )
    list_filter = ("entity", "institution", "position__category")
    search_fields = ("user__username", "user__email", "position__name", "appointment_reference")
    autocomplete_fields = ("user", "position", "entity", "institution", "unit", "appointed_by")
    readonly_fields = ("created_at",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    readonly_fields = ("id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("id",)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role",)
    search_fields = ("role__code", "permission__code")
    autocomplete_fields = ("role", "permission")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "entity",
        "scope_level",
        "institution",
        "unit",
        "valid_from",
        "valid_until",
        "is_active",
    )
    list_filter = ("entity", "scope_level", "institution", "role", "is_active")
    search_fields = ("user__username", "user__email", "role__code")
    autocomplete_fields = (
        "user",
        "role",
        "entity",
        "institution",
        "unit",
        "granted_by",
        "revoked_by",
    )
    readonly_fields = (
        "user",
        "role",
        "entity",
        "institution",
        "unit",
        "scope_level",
        "valid_from",
        "valid_until",
        "is_active",
        "granted_by",
        "granted_at",
        "revoked_at",
        "revoked_by",
        "revocation_reason",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "entity_id", "target_type", "target_id")
    list_filter = ("action", "entity_id")
    search_fields = ("target_type", "target_id", "request_id")
    readonly_fields = (
        "id",
        "actor",
        "action",
        "entity_id",
        "unit_id",
        "target_type",
        "target_id",
        "before_state",
        "after_state",
        "request_id",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "event_id", "created_at", "published_at")
    readonly_fields = ("event_id", "event_type", "version", "payload", "created_at", "published_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
