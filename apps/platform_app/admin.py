from django.contrib import admin

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


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "legal_form", "fiscal_year_start_month", "is_active")
    list_filter = ("legal_form", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity", "institution_type", "is_active")
    list_filter = ("institution_type", "is_active", "entity")
    search_fields = ("code", "name", "entity__name")
    autocomplete_fields = ("entity",)
    readonly_fields = ("id", "created_at")


@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity", "institution", "parent", "unit_type", "is_cost_center", "is_active")
    list_filter = ("entity", "institution", "unit_type", "is_cost_center", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("entity", "institution", "parent")
    readonly_fields = ("id", "created_at")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")


@admin.register(PositionAssignment)
class PositionAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "position", "entity", "institution", "unit", "valid_from", "valid_until")
    list_filter = ("entity", "institution", "position__category")
    search_fields = ("user__username", "user__email", "position__name", "appointment_reference")
    autocomplete_fields = ("user", "position", "entity", "institution", "unit", "appointed_by")
    readonly_fields = ("created_at",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    readonly_fields = ("id",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
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


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "entity", "scope_level", "institution", "unit", "valid_from", "valid_until", "is_active")
    list_filter = ("entity", "scope_level", "institution", "role", "is_active")
    search_fields = ("user__username", "user__email", "role__code")
    autocomplete_fields = ("user", "role", "entity", "institution", "unit", "granted_by", "revoked_by")
    readonly_fields = ("granted_at", "revoked_at")


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


admin.site.register(OutboxEvent)
