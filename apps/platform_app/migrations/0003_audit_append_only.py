from django.db import migrations

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION public.reject_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only (operation=%)', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER audit_events_no_update_delete
BEFORE UPDATE OR DELETE ON platform_audit_events
FOR EACH ROW EXECUTE FUNCTION public.reject_audit_mutation();

CREATE TRIGGER audit_events_no_truncate
BEFORE TRUNCATE ON platform_audit_events
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_audit_mutation();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS audit_events_no_truncate ON platform_audit_events;
DROP TRIGGER IF EXISTS audit_events_no_update_delete ON platform_audit_events;
DROP FUNCTION IF EXISTS public.reject_audit_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("platform", "0002_entity_permission_role_organizationalunit_and_more")]

    operations = [migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL)]
