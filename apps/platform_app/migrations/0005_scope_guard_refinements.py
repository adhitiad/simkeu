from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION public.guard_platform_org_unit_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    institution_entity bigint;
    parent_entity bigint;
    parent_institution bigint;
BEGIN
    IF NEW.institution_id IS NOT NULL THEN
        SELECT entity_id INTO institution_entity
          FROM platform_institutions
         WHERE id = NEW.institution_id;
        IF NOT FOUND OR institution_entity <> NEW.entity_id THEN
            RAISE EXCEPTION 'organization unit institution is outside entity';
        END IF;
    END IF;

    IF NEW.parent_id IS NOT NULL THEN
        SELECT entity_id, institution_id
          INTO parent_entity, parent_institution
          FROM platform_org_units
         WHERE id = NEW.parent_id;
        IF NOT FOUND
           OR parent_entity <> NEW.entity_id
           OR parent_institution IS DISTINCT FROM NEW.institution_id THEN
            RAISE EXCEPTION 'organization unit parent is outside entity/institution';
        END IF;
        IF NEW.parent_id = NEW.id THEN
            RAISE EXCEPTION 'organization unit cannot be its own parent';
        END IF;
        IF EXISTS (
            WITH RECURSIVE ancestors(id, parent_id) AS (
                SELECT id, parent_id
                  FROM platform_org_units
                 WHERE id = NEW.parent_id
                UNION
                SELECT parent.id, parent.parent_id
                  FROM platform_org_units parent
                  JOIN ancestors child ON parent.id = child.parent_id
            )
            SELECT 1 FROM ancestors WHERE id = NEW.id
        ) THEN
            RAISE EXCEPTION 'organization unit hierarchy cannot contain a cycle';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM platform_org_units child
         WHERE child.parent_id = NEW.id
           AND (
                child.entity_id <> NEW.entity_id
                OR child.institution_id IS DISTINCT FROM NEW.institution_id
           )
    ) THEN
        RAISE EXCEPTION 'organization unit change would invalidate child scopes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM platform_user_roles role_assignment
         WHERE role_assignment.unit_id = NEW.id
           AND (
                role_assignment.entity_id <> NEW.entity_id
                OR role_assignment.institution_id IS DISTINCT FROM NEW.institution_id
           )
    ) OR EXISTS (
        SELECT 1
          FROM platform_position_assignments position_assignment
         WHERE position_assignment.unit_id = NEW.id
           AND (
                position_assignment.entity_id <> NEW.entity_id
                OR position_assignment.institution_id IS DISTINCT FROM NEW.institution_id
           )
    ) THEN
        RAISE EXCEPTION 'organization unit change would invalidate existing assignments';
    END IF;
    RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION public.guard_platform_institution_entity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.entity_id <> OLD.entity_id AND (
        EXISTS (SELECT 1 FROM platform_org_units WHERE institution_id = NEW.id)
        OR EXISTS (SELECT 1 FROM platform_user_roles WHERE institution_id = NEW.id)
        OR EXISTS (SELECT 1 FROM platform_position_assignments WHERE institution_id = NEW.id)
    ) THEN
        RAISE EXCEPTION 'institution cannot move to another legal entity while referenced';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER platform_institution_entity_guard
BEFORE UPDATE OF entity_id ON platform_institutions
FOR EACH ROW EXECUTE FUNCTION public.guard_platform_institution_entity();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS platform_institution_entity_guard ON platform_institutions;
DROP FUNCTION IF EXISTS public.guard_platform_institution_entity();
"""


class Migration(migrations.Migration):
    dependencies = [("platform", "0004_institution_position_and_scoped_roles")]

    operations = [
        migrations.AlterModelOptions(
            name="entity",
            options={
                "ordering": ["code"],
                "verbose_name": "Badan hukum penyelenggara",
                "verbose_name_plural": "Badan hukum penyelenggara",
            },
        ),
        migrations.AlterModelOptions(
            name="organizationalunit",
            options={
                "ordering": ["entity_id", "code"],
                "verbose_name": "Unit organisasi",
                "verbose_name_plural": "Unit organisasi",
            },
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
