from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from .models import (
    BudgetAllocation,
    BudgetCommitment,
    BudgetLine,
    BudgetPlan,
    BudgetRevision,
    BudgetRevisionItem,
    FiscalYear,
)


class ReadOnlyBudgetAdmin(admin.ModelAdmin):
    """Financial documents are changed through domain services, never generic admin CRUD."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False


@admin.register(FiscalYear)
class FiscalYearAdmin(ReadOnlyBudgetAdmin):
    list_display = ("code", "name", "entity_id", "starts_on", "ends_on", "status")
    list_filter = ("entity_id", "status")
    search_fields = ("code", "name")
    readonly_fields = tuple(field.name for field in FiscalYear._meta.fields)


@admin.register(BudgetPlan)
class BudgetPlanAdmin(ReadOnlyBudgetAdmin):
    list_display = ("plan_type", "title", "entity_id", "version", "status", "created_at")
    list_filter = ("plan_type", "status", "entity_id")
    search_fields = ("title",)
    readonly_fields = tuple(field.name for field in BudgetPlan._meta.fields)


@admin.register(BudgetLine)
class BudgetLineAdmin(ReadOnlyBudgetAdmin):
    list_display = ("plan", "line_number", "unit_id", "account_id", "amount")
    list_filter = ("entity_id",)
    search_fields = ("description", "funding_source")
    readonly_fields = tuple(field.name for field in BudgetLine._meta.fields)


@admin.register(BudgetAllocation)
class BudgetAllocationAdmin(ReadOnlyBudgetAdmin):
    list_display = ("unit_id", "account_id", "funding_source", "allocated_amount", "status")
    list_filter = ("entity_id", "status")
    readonly_fields = tuple(field.name for field in BudgetAllocation._meta.fields)


@admin.register(BudgetRevision)
class BudgetRevisionAdmin(ReadOnlyBudgetAdmin):
    list_display = ("id", "entity_id", "status", "effective_date", "created_at")
    list_filter = ("entity_id", "status")
    readonly_fields = tuple(field.name for field in BudgetRevision._meta.fields)


@admin.register(BudgetRevisionItem)
class BudgetRevisionItemAdmin(ReadOnlyBudgetAdmin):
    list_display = ("revision", "allocation", "previous_amount", "requested_amount")
    readonly_fields = tuple(field.name for field in BudgetRevisionItem._meta.fields)


@admin.register(BudgetCommitment)
class BudgetCommitmentAdmin(ReadOnlyBudgetAdmin):
    list_display = ("source_type", "source_id", "amount", "status", "created_at")
    list_filter = ("entity_id", "status")
    search_fields = ("source_type", "source_id", "description")
    readonly_fields = tuple(field.name for field in BudgetCommitment._meta.fields)
