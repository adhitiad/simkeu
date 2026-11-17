from __future__ import annotations

from typing import ClassVar

from django.contrib import admin
from django.contrib.auth.models import User
from django.forms import ModelForm
from django.http import HttpRequest

from .models import Account, AccountingPeriod, JournalEntry, JournalLineRecord


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "code", "name", "entity_id", "account_type", "normal_balance", "is_active"
    ]
    list_filter: ClassVar[list[str]] = [
        "entity_id", "account_type", "normal_balance", "is_active"
    ]
    search_fields: ClassVar[list[str]] = ["code", "name"]
    readonly_fields: ClassVar[list[str]] = ["created_at", "created_by"]
    ordering: ClassVar[list[str]] = ["entity_id", "code"]

    def save_model(
        self,
        request: HttpRequest,
        obj: Account,
        form: ModelForm[Account],
        change: bool,
    ) -> None:
        if not change:
            obj.created_by = User.objects.get(pk=request.user.pk)
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request: HttpRequest, obj: Account | None = None) -> bool:
        return False


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "name", "entity_id", "starts_on", "ends_on", "status", "closed_at"
    ]
    list_filter: ClassVar[list[str]] = ["entity_id", "status"]
    search_fields: ClassVar[list[str]] = ["name"]
    readonly_fields: ClassVar[list[str]] = [
        "status",
        "close_requested_by",
        "closed_by",
        "closed_at",
        "created_at",
        "created_by",
    ]

    def save_model(
        self,
        request: HttpRequest,
        obj: AccountingPeriod,
        form: ModelForm[AccountingPeriod],
        change: bool,
    ) -> None:
        if not change:
            obj.created_by = User.objects.get(pk=request.user.pk)
        super().save_model(request, obj, form, change)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: AccountingPeriod | None = None,
    ) -> bool:
        return False


class JournalLineInline(admin.TabularInline):
    model = JournalLineRecord
    extra = 0
    can_delete = False
    readonly_fields: ClassVar[list[str]] = [
        "entity_id",
        "account",
        "line_number",
        "description",
        "debit",
        "credit",
        "created_at",
        "created_by",
    ]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "business_date", "entity_id", "source_type", "source_id", "period", "posted_at"
    ]
    list_filter: ClassVar[list[str]] = ["entity_id", "period"]
    search_fields: ClassVar[list[str]] = [
        "source_type", "source_id", "description"
    ]
    readonly_fields: ClassVar[list[str]] = [
        "entity_id",
        "period",
        "business_date",
        "source_type",
        "source_id",
        "description",
        "posted_at",
        "created_at",
        "created_by",
    ]
    inlines: ClassVar[list[type[admin.TabularInline]]] = [JournalLineInline]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_view_permission(
        self,
        request: HttpRequest,
        obj: JournalEntry | None = None,
    ) -> bool:
        return request.user.is_staff

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: JournalEntry | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: JournalEntry | None = None,
    ) -> bool:
        return False
