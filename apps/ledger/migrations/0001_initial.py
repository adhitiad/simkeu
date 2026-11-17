import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


LEDGER_GUARDS_SQL = """
CREATE OR REPLACE FUNCTION ledger.reject_journal_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'posted ledger records are append-only (operation=%)', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER journal_entries_no_update_delete
BEFORE UPDATE OR DELETE ON ledger.journal_entries
FOR EACH ROW EXECUTE FUNCTION ledger.reject_journal_mutation();

CREATE TRIGGER journal_entries_no_truncate
BEFORE TRUNCATE ON ledger.journal_entries
FOR EACH STATEMENT EXECUTE FUNCTION ledger.reject_journal_mutation();

CREATE TRIGGER journal_lines_no_update_delete
BEFORE UPDATE OR DELETE ON ledger.journal_lines
FOR EACH ROW EXECUTE FUNCTION ledger.reject_journal_mutation();

CREATE TRIGGER journal_lines_no_truncate
BEFORE TRUNCATE ON ledger.journal_lines
FOR EACH STATEMENT EXECUTE FUNCTION ledger.reject_journal_mutation();


CREATE OR REPLACE FUNCTION ledger.guard_journal_entry_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    period_entity bigint;
    period_start date;
    period_end date;
    period_status text;
BEGIN
    SELECT entity_id, starts_on, ends_on, status
      INTO period_entity, period_start, period_end, period_status
      FROM ledger.accounting_periods
     WHERE id = NEW.period_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'accounting period does not exist';
    END IF;
    IF period_entity <> NEW.entity_id THEN
        RAISE EXCEPTION 'journal entity does not match accounting period';
    END IF;
    IF period_status <> 'open' THEN
        RAISE EXCEPTION 'cannot post to a closed accounting period';
    END IF;
    IF NEW.business_date < period_start OR NEW.business_date > period_end THEN
        RAISE EXCEPTION 'journal business date is outside the accounting period';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER journal_entry_period_guard
BEFORE INSERT ON ledger.journal_entries
FOR EACH ROW EXECUTE FUNCTION ledger.guard_journal_entry_insert();


CREATE OR REPLACE FUNCTION ledger.guard_journal_line_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    entry_entity bigint;
    account_entity bigint;
    account_active boolean;
BEGIN
    SELECT entity_id INTO entry_entity
      FROM ledger.journal_entries
     WHERE id = NEW.entry_id
     FOR UPDATE;
    IF NOT FOUND OR entry_entity <> NEW.entity_id THEN
        RAISE EXCEPTION 'journal line entity does not match journal entry';
    END IF;

    SELECT entity_id, is_active INTO account_entity, account_active
      FROM ledger.accounts
     WHERE id = NEW.account_id
     FOR UPDATE;
    IF NOT FOUND OR account_entity <> NEW.entity_id OR account_active IS NOT TRUE THEN
        RAISE EXCEPTION 'journal line account is missing, inactive, or outside entity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER journal_line_scope_guard
BEFORE INSERT ON ledger.journal_lines
FOR EACH ROW EXECUTE FUNCTION ledger.guard_journal_line_insert();


CREATE OR REPLACE FUNCTION ledger.assert_journal_balanced()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id uuid;
    line_count bigint;
    debit_total bigint;
    credit_total bigint;
BEGIN
    IF TG_TABLE_NAME = 'journal_entries' THEN
        target_entry_id := NEW.id;
    ELSE
        target_entry_id := NEW.entry_id;
    END IF;

    SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
      INTO line_count, debit_total, credit_total
      FROM ledger.journal_lines
     WHERE entry_id = target_entry_id;

    IF line_count < 2 OR debit_total <= 0 OR debit_total <> credit_total THEN
        RAISE EXCEPTION 'journal % is not balanced (lines=%, debit=%, credit=%)',
            target_entry_id, line_count, debit_total, credit_total
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER journal_entry_balance_check
AFTER INSERT ON ledger.journal_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ledger.assert_journal_balanced();

CREATE CONSTRAINT TRIGGER journal_line_balance_check
AFTER INSERT ON ledger.journal_lines
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ledger.assert_journal_balanced();
"""

DROP_LEDGER_GUARDS_SQL = """
DROP TRIGGER IF EXISTS journal_line_balance_check ON ledger.journal_lines;
DROP TRIGGER IF EXISTS journal_entry_balance_check ON ledger.journal_entries;
DROP TRIGGER IF EXISTS journal_line_scope_guard ON ledger.journal_lines;
DROP TRIGGER IF EXISTS journal_entry_period_guard ON ledger.journal_entries;
DROP TRIGGER IF EXISTS journal_lines_no_truncate ON ledger.journal_lines;
DROP TRIGGER IF EXISTS journal_lines_no_update_delete ON ledger.journal_lines;
DROP TRIGGER IF EXISTS journal_entries_no_truncate ON ledger.journal_entries;
DROP TRIGGER IF EXISTS journal_entries_no_update_delete ON ledger.journal_entries;
DROP FUNCTION IF EXISTS ledger.assert_journal_balanced();
DROP FUNCTION IF EXISTS ledger.guard_journal_line_insert();
DROP FUNCTION IF EXISTS ledger.guard_journal_entry_insert();
DROP FUNCTION IF EXISTS ledger.reject_journal_mutation();
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE SCHEMA IF NOT EXISTS ledger;",
            reverse_sql="DROP SCHEMA IF EXISTS ledger CASCADE;",
        ),
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("account_type", models.CharField(choices=[("asset", "Aset"), ("liability", "Liabilitas"), ("net_assets", "Aset Neto"), ("revenue", "Pendapatan"), ("expense", "Beban")], max_length=16)),
                ("normal_balance", models.CharField(choices=[("debit", "Debit"), ("credit", "Kredit")], max_length=6)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="ledger.account")),
            ],
            options={
                "db_table": '"ledger"."accounts"',
                "ordering": ["entity_id", "code"],
            },
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=64)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField()),
                ("status", models.CharField(choices=[("open", "Terbuka"), ("closed", "Ditutup")], default="open", max_length=8)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("close_requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": '"ledger"."accounting_periods"',
                "ordering": ["-starts_on"],
            },
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("business_date", models.DateField()),
                ("source_type", models.CharField(max_length=64)),
                ("source_id", models.CharField(max_length=128)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("posted_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_entries", to="ledger.accountingperiod")),
            ],
            options={
                "db_table": '"ledger"."journal_entries"',
                "ordering": ["-business_date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="JournalLineRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False)),
                ("entity_id", models.PositiveBigIntegerField(db_index=True)),
                ("line_number", models.PositiveSmallIntegerField()),
                ("description", models.CharField(blank=True, max_length=255)),
                ("debit", models.PositiveBigIntegerField(default=0)),
                ("credit", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="ledger.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="ledger.journalentry")),
            ],
            options={
                "db_table": '"ledger"."journal_lines"',
                "ordering": ["line_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.UniqueConstraint(fields=("entity_id", "code"), name="ledger_account_entity_code_uniq"),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(condition=Q(account_type__in=["asset", "liability", "net_assets", "revenue", "expense"]), name="ledger_account_type_valid"),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(condition=Q(normal_balance__in=["debit", "credit"]), name="ledger_account_balance_valid"),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.UniqueConstraint(fields=("entity_id", "name"), name="ledger_period_entity_name_uniq"),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.CheckConstraint(condition=Q(ends_on__gte=F("starts_on")), name="ledger_period_dates_valid"),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.CheckConstraint(condition=Q(status__in=["open", "closed"]), name="ledger_period_status_valid"),
        ),
        migrations.AddIndex(
            model_name="accountingperiod",
            index=models.Index(fields=["entity_id", "status", "starts_on"], name="ledger_period_scope_idx"),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(fields=("entity_id", "source_type", "source_id"), name="ledger_journal_source_uniq"),
        ),
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(fields=["entity_id", "business_date", "id"], name="ledger_jrnl_ent_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="journallinerecord",
            constraint=models.UniqueConstraint(fields=("entry", "line_number"), name="ledger_line_number_uniq"),
        ),
        migrations.AddConstraint(
            model_name="journallinerecord",
            constraint=models.CheckConstraint(condition=Q(debit__gt=0, credit=0) | Q(debit=0, credit__gt=0), name="ledger_line_one_sided_amount"),
        ),
        migrations.AddIndex(
            model_name="journallinerecord",
            index=models.Index(fields=["entity_id", "entry"], name="ledger_line_ent_entry_idx"),
        ),
        migrations.RunSQL(sql=LEDGER_GUARDS_SQL, reverse_sql=DROP_LEDGER_GUARDS_SQL),
    ]
