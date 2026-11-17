# Generated for the SIMKEU P1 budget bounded context.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE SCHEMA IF NOT EXISTS budget;",
            reverse_sql="SELECT 1;",
        ),
        migrations.CreateModel(
            name="FiscalYear",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("code", models.CharField(max_length=16)),
                ("name", models.CharField(max_length=100)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField()),
                ("status", models.CharField(choices=[("open", "Terbuka"), ("closed", "Ditutup")], default="open", max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": '"budget"."fiscal_years"',
                "ordering": ["-starts_on"],
                "constraints": [
                    models.UniqueConstraint(fields=("entity_id", "code"), name="budget_fy_entity_code_uniq"),
                    models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="budget_fy_dates_valid"),
                    models.CheckConstraint(condition=models.Q(status__in=["open", "closed"]), name="budget_fy_status_valid"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "status", "starts_on"], name="budget_fy_scope_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("unit_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("plan_type", models.CharField(choices=[("RKAT", "Rencana Kerja dan Anggaran Tahunan"), ("RAPBU", "Rencana Anggaran Pendapatan dan Belanja Universitas"), ("APBU", "Anggaran Pendapatan dan Belanja Universitas")], max_length=8)),
                ("version", models.PositiveSmallIntegerField(default=1)),
                ("title", models.CharField(max_length=160)),
                ("status", models.CharField(choices=[("draft", "Draf"), ("submitted", "Diajukan"), ("review", "Dalam review"), ("approved", "Disetujui"), ("active", "Aktif"), ("superseded", "Digantikan"), ("rejected", "Ditolak")], default="draft", max_length=16)),
                ("notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("effective_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="plans", to="budget.fiscalyear")),
                ("previous_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="next_versions", to="budget.budgetplan")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": '"budget"."budget_plans"',
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("entity_id", "fiscal_year", "plan_type", "unit_id", "version"), name="budget_plan_version_uniq", nulls_distinct=False),
                    models.CheckConstraint(condition=models.Q(plan_type__in=["RKAT", "RAPBU", "APBU"]), name="budget_plan_type_valid"),
                    models.CheckConstraint(condition=models.Q(status__in=["draft", "submitted", "review", "approved", "active", "superseded", "rejected"]), name="budget_plan_status_valid"),
                    models.CheckConstraint(condition=(models.Q(plan_type="RKAT", unit_id__isnull=False) | models.Q(plan_type__in=["RAPBU", "APBU"], unit_id__isnull=True)), name="budget_plan_scope_valid"),
                    models.UniqueConstraint(fields=("entity_id", "fiscal_year"), condition=models.Q(plan_type="APBU", status="active"), name="budget_one_active_apbu_uniq"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "fiscal_year", "plan_type", "status"], name="budget_plan_scope_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("line_number", models.PositiveSmallIntegerField()),
                ("unit_id", models.PositiveBigIntegerField(db_index=True)),
                ("account_id", models.UUIDField()),
                ("program_code", models.CharField(blank=True, max_length=40)),
                ("funding_source", models.CharField(max_length=40)),
                ("description", models.CharField(max_length=500)),
                ("objective", models.CharField(blank=True, max_length=500)),
                ("output", models.CharField(blank=True, max_length=500)),
                ("indicator", models.CharField(blank=True, max_length=255)),
                ("schedule_start", models.DateField(blank=True, null=True)),
                ("schedule_end", models.DateField(blank=True, null=True)),
                ("amount", models.PositiveBigIntegerField()),
                ("is_restricted", models.BooleanField(default=False)),
                ("restriction_note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="budget.budgetplan")),
            ],
            options={
                "db_table": '"budget"."budget_lines"',
                "ordering": ["line_number"],
                "constraints": [
                    models.UniqueConstraint(fields=("plan", "line_number"), name="budget_line_number_uniq"),
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="budget_line_amount_positive"),
                    models.CheckConstraint(condition=(models.Q(schedule_start__isnull=True, schedule_end__isnull=True) | models.Q(schedule_start__isnull=False, schedule_end__isnull=False, schedule_end__gte=models.F("schedule_start"))), name="budget_line_schedule_valid"),
                    models.CheckConstraint(condition=(models.Q(is_restricted=False) | ~models.Q(restriction_note="")), name="budget_line_restriction_note_ck"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "unit_id", "plan"], name="budget_line_scope_idx"),
                    models.Index(fields=["account_id"], name="budget_line_account_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("unit_id", models.PositiveBigIntegerField(db_index=True)),
                ("account_id", models.UUIDField()),
                ("funding_source", models.CharField(max_length=40)),
                ("allocated_amount", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("active", "Aktif"), ("superseded", "Digantikan")], default="active", max_length=12)),
                ("effective_from", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("budget_line", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="allocation", to="budget.budgetline")),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="budget.fiscalyear")),
            ],
            options={
                "db_table": '"budget"."pagu_allocations"',
                "ordering": ["unit_id", "account_id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(allocated_amount__gte=0), name="budget_pagu_nonnegative"),
                    models.CheckConstraint(condition=models.Q(status__in=["active", "superseded"]), name="budget_pagu_status_valid"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "fiscal_year", "status"], name="budget_pagu_scope_idx"),
                    models.Index(fields=["unit_id", "status"], name="budget_pagu_unit_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("status", models.CharField(choices=[("draft", "Draf"), ("submitted", "Diajukan"), ("verified", "Terverifikasi"), ("effective", "Berlaku"), ("rejected", "Ditolak")], default="draft", max_length=12)),
                ("reason", models.TextField()),
                ("effective_date", models.DateField()),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revisions", to="budget.fiscalyear")),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": '"budget"."budget_revisions"',
                "ordering": ["-created_at"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(status__in=["draft", "submitted", "verified", "effective", "rejected"]), name="budget_revision_status_valid"),
                    models.CheckConstraint(condition=~models.Q(reason=""), name="budget_revision_reason_ck"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "fiscal_year", "status"], name="budget_revision_scope_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetRevisionItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("previous_amount", models.PositiveBigIntegerField()),
                ("requested_amount", models.PositiveBigIntegerField()),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("allocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revision_items", to="budget.budgetallocation")),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="budget.budgetrevision")),
            ],
            options={
                "db_table": '"budget"."budget_revision_items"',
                "ordering": ["created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("revision", "allocation"), name="budget_revision_alloc_uniq"),
                    models.CheckConstraint(condition=models.Q(requested_amount__gte=0), name="budget_revision_amount_nonnegative"),
                ],
                "indexes": [
                    models.Index(fields=["entity_id", "allocation"], name="budget_revision_item_scope_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetCommitment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("source_type", models.CharField(max_length=64)),
                ("source_id", models.CharField(max_length=128)),
                ("description", models.CharField(max_length=500)),
                ("amount", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("reserved", "Dicadangkan"), ("fulfilled", "Direalisasikan"), ("released", "Dilepaskan")], default="reserved", max_length=12)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("release_reason", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("allocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commitments", to="budget.budgetallocation")),
                ("released_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": '"budget"."budget_commitments"',
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("entity_id", "source_type", "source_id"), name="budget_commitment_source_uniq"),
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="budget_commitment_amount_positive"),
                    models.CheckConstraint(condition=models.Q(status__in=["reserved", "fulfilled", "released"]), name="budget_commitment_status_valid"),
                    models.CheckConstraint(condition=(models.Q(status="released", released_by__isnull=False, released_at__isnull=False) | ~models.Q(status="released")), name="budget_commitment_release_meta_ck"),
                ],
                "indexes": [
                    models.Index(fields=["allocation", "status"], name="budget_commit_alloc_status_idx"),
                    models.Index(fields=["entity_id", "created_at"], name="budget_commit_entity_date_idx"),
                ],
            },
        ),
    ]
