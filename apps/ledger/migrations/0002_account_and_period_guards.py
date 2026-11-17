from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION ledger.guard_account_history()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_entity bigint;
    has_history boolean;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'ledger account identity is immutable';
        END IF;

        SELECT EXISTS (
            SELECT 1
              FROM ledger.journal_lines
             WHERE account_id = OLD.id
        ) INTO has_history;

        IF has_history AND (
            NEW.entity_id IS DISTINCT FROM OLD.entity_id
            OR NEW.code IS DISTINCT FROM OLD.code
            OR NEW.name IS DISTINCT FROM OLD.name
            OR NEW.account_type IS DISTINCT FROM OLD.account_type
            OR NEW.normal_balance IS DISTINCT FROM OLD.normal_balance
            OR NEW.parent_id IS DISTINCT FROM OLD.parent_id
        ) THEN
            RAISE EXCEPTION 'account classification cannot change after ledger usage';
        END IF;
    END IF;

    IF NEW.parent_id IS NOT NULL THEN
        IF NEW.parent_id = NEW.id THEN
            RAISE EXCEPTION 'an account cannot be its own parent';
        END IF;

        SELECT entity_id
          INTO parent_entity
          FROM ledger.accounts
         WHERE id = NEW.parent_id;

        IF NOT FOUND OR parent_entity IS DISTINCT FROM NEW.entity_id THEN
            RAISE EXCEPTION 'account parent must belong to the same entity';
        END IF;

        IF EXISTS (
            WITH RECURSIVE ancestors(id, parent_id) AS (
                SELECT id, parent_id
                  FROM ledger.accounts
                 WHERE id = NEW.parent_id
                UNION
                SELECT account.id, account.parent_id
                  FROM ledger.accounts account
                  JOIN ancestors ON account.id = ancestors.parent_id
            )
            SELECT 1
              FROM ancestors
             WHERE id = NEW.id
        ) THEN
            RAISE EXCEPTION 'account parent relation cannot create a cycle';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER accounts_history_guard
BEFORE INSERT OR UPDATE ON ledger.accounts
FOR EACH ROW EXECUTE FUNCTION ledger.guard_account_history();


CREATE OR REPLACE FUNCTION ledger.guard_accounting_period_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    has_entries boolean;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'closed' THEN
        RAISE EXCEPTION 'closed accounting periods are immutable';
    END IF;

    IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status <> 'open' OR NEW.status <> 'closed' THEN
            RAISE EXCEPTION 'invalid accounting period state transition';
        END IF;

        IF NEW.close_requested_by_id IS NULL
           OR NEW.closed_by_id IS NULL
           OR NEW.close_requested_by_id = NEW.closed_by_id
           OR NEW.closed_at IS NULL THEN
            RAISE EXCEPTION 'closing a period requires distinct maker and checker';
        END IF;

        IF NEW.id IS DISTINCT FROM OLD.id
           OR NEW.entity_id IS DISTINCT FROM OLD.entity_id
           OR NEW.name IS DISTINCT FROM OLD.name
           OR NEW.starts_on IS DISTINCT FROM OLD.starts_on
           OR NEW.ends_on IS DISTINCT FROM OLD.ends_on
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id THEN
            RAISE EXCEPTION 'period business attributes cannot change during closure';
        END IF;
    ELSIF TG_OP = 'UPDATE' THEN
        SELECT EXISTS (
            SELECT 1
              FROM ledger.journal_entries
             WHERE period_id = OLD.id
        ) INTO has_entries;

        IF has_entries THEN
            RAISE EXCEPTION 'accounting period cannot change after journal posting';
        END IF;
    ELSIF TG_OP = 'INSERT' AND NEW.status <> 'open' THEN
        RAISE EXCEPTION 'new accounting periods must start open';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.entity_id <> NEW.entity_id THEN
        PERFORM pg_advisory_xact_lock(LEAST(OLD.entity_id, NEW.entity_id));
        PERFORM pg_advisory_xact_lock(GREATEST(OLD.entity_id, NEW.entity_id));
    ELSE
        PERFORM pg_advisory_xact_lock(NEW.entity_id);
    END IF;

    IF EXISTS (
        SELECT 1
          FROM ledger.accounting_periods period
         WHERE period.entity_id = NEW.entity_id
           AND period.id IS DISTINCT FROM NEW.id
           AND period.starts_on <= NEW.ends_on
           AND period.ends_on >= NEW.starts_on
    ) THEN
        RAISE EXCEPTION 'accounting periods for the same entity cannot overlap';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER accounting_period_write_guard
BEFORE INSERT OR UPDATE ON ledger.accounting_periods
FOR EACH ROW EXECUTE FUNCTION ledger.guard_accounting_period_write();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS accounting_period_write_guard ON ledger.accounting_periods;
DROP TRIGGER IF EXISTS accounts_history_guard ON ledger.accounts;
DROP FUNCTION IF EXISTS ledger.guard_accounting_period_write();
DROP FUNCTION IF EXISTS ledger.guard_account_history();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
