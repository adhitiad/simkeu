from django.conf import settings
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


def migrate_legacy_role_scopes(apps, schema_editor):
    UserRole = apps.get_model("platform", "UserRole")
    UserRole.objects.filter(unit__isnull=False).update(scope_level="unit")
    UserRole.objects.filter(unit__isnull=True).update(scope_level="entity")


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
    RETURN NEW;
END;
$$;

CREATE TRIGGER platform_org_unit_scope_guard
BEFORE INSERT OR UPDATE OF entity_id, institution_id, parent_id
ON platform_org_units
FOR EACH ROW EXECUTE FUNCTION public.guard_platform_org_unit_scope();


CREATE OR REPLACE FUNCTION public.guard_platform_position_assignment_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    institution_entity bigint;
    unit_entity bigint;
    unit_institution bigint;
BEGIN
    IF NEW.institution_id IS NOT NULL THEN
        SELECT entity_id INTO institution_entity
          FROM platform_institutions WHERE id = NEW.institution_id;
        IF NOT FOUND OR institution_entity <> NEW.entity_id THEN
            RAISE EXCEPTION 'position assignment institution is outside entity';
        END IF;
    END IF;

    IF NEW.unit_id IS NOT NULL THEN
        SELECT entity_id, institution_id
          INTO unit_entity, unit_institution
          FROM platform_org_units WHERE id = NEW.unit_id;
        IF NOT FOUND OR unit_entity <> NEW.entity_id
           OR unit_institution IS DISTINCT FROM NEW.institution_id THEN
            RAISE EXCEPTION 'position assignment unit is outside entity/institution';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER platform_position_assignment_scope_guard
BEFORE INSERT OR UPDATE OF entity_id, institution_id, unit_id
ON platform_position_assignments
FOR EACH ROW EXECUTE FUNCTION public.guard_platform_position_assignment_scope();


CREATE OR REPLACE FUNCTION public.guard_platform_user_role_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    institution_entity bigint;
    unit_entity bigint;
    unit_institution bigint;
BEGIN
    IF NEW.institution_id IS NOT NULL THEN
        SELECT entity_id INTO institution_entity
          FROM platform_institutions WHERE id = NEW.institution_id;
        IF NOT FOUND OR institution_entity <> NEW.entity_id THEN
            RAISE EXCEPTION 'role assignment institution is outside entity';
        END IF;
    END IF;

    IF NEW.scope_level = 'entity' THEN
        IF NEW.institution_id IS NOT NULL OR NEW.unit_id IS NOT NULL THEN
            RAISE EXCEPTION 'entity role scope cannot reference institution or unit';
        END IF;
    ELSIF NEW.scope_level = 'institution' THEN
        IF NEW.institution_id IS NULL OR NEW.unit_id IS NOT NULL THEN
            RAISE EXCEPTION 'institution role scope requires institution only';
        END IF;
    ELSIF NEW.scope_level = 'unit' THEN
        IF NEW.unit_id IS NULL THEN
            RAISE EXCEPTION 'unit role scope requires unit';
        END IF;
        SELECT entity_id, institution_id
          INTO unit_entity, unit_institution
          FROM platform_org_units WHERE id = NEW.unit_id;
        IF NOT FOUND OR unit_entity <> NEW.entity_id
           OR unit_institution IS DISTINCT FROM NEW.institution_id THEN
            RAISE EXCEPTION 'role assignment unit is outside entity/institution';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid role assignment scope';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER platform_user_role_scope_guard
BEFORE INSERT OR UPDATE OF entity_id, institution_id, unit_id, scope_level
ON platform_user_roles
FOR EACH ROW EXECUTE FUNCTION public.guard_platform_user_role_scope();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS platform_user_role_scope_guard ON platform_user_roles;
DROP TRIGGER IF EXISTS platform_position_assignment_scope_guard ON platform_position_assignments;
DROP TRIGGER IF EXISTS platform_org_unit_scope_guard ON platform_org_units;
DROP FUNCTION IF EXISTS public.guard_platform_user_role_scope();
DROP FUNCTION IF EXISTS public.guard_platform_position_assignment_scope();
DROP FUNCTION IF EXISTS public.guard_platform_org_unit_scope();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0003_audit_append_only"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Institution",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("institution_type", models.CharField(choices=[("university", "Universitas"), ("institute", "Institut"), ("college", "Sekolah Tinggi"), ("polytechnic", "Politeknik"), ("academy", "Akademi"), ("other", "Perguruan tinggi lain")], default="university", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="institutions", to="platform.entity")),
            ],
            options={
                "db_table": "platform_institutions",
                "ordering": ["entity_id", "code"],
                "verbose_name": "Institusi perguruan tinggi",
                "verbose_name_plural": "Institusi perguruan tinggi",
            },
        ),
        migrations.CreateModel(
            name="Position",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("category", models.CharField(choices=[("governing", "Organ badan penyelenggara"), ("structural", "Jabatan struktural"), ("functional", "Jabatan fungsional"), ("staff", "Pelaksana"), ("other", "Lainnya")], max_length=20)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "platform_positions", "ordering": ["code"]},
        ),
        migrations.AddField(
            model_name="entity",
            name="legal_form",
            field=models.CharField(choices=[("foundation", "Yayasan"), ("association", "Perkumpulan"), ("other", "Bentuk badan hukum lain")], default="other", max_length=20),
        ),
        migrations.AddField(
            model_name="entity",
            name="address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="entity",
            name="fiscal_year_start_month",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="organizationalunit",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="units", to="platform.institution"),
        ),
        migrations.AddField(
            model_name="organizationalunit",
            name="is_cost_center",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="organizationalunit",
            name="unit_type",
            field=models.CharField(choices=[("university", "Universitas (unit lama)"), ("faculty", "Fakultas"), ("department", "Program studi (unit lama)"), ("unit", "Unit kerja"), ("campus", "Kampus"), ("dept", "Departemen"), ("study_program", "Program studi"), ("bureau", "Biro"), ("section", "Bagian"), ("subsection", "Subbagian"), ("laboratory", "Laboratorium"), ("business", "Unit usaha"), ("support", "Unit pendukung")], max_length=20),
        ),
        migrations.CreateModel(
            name="PositionAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valid_from", models.DateField(default=django.utils.timezone.localdate)),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("appointment_reference", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("appointed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="position_assignments", to="platform.entity")),
                ("institution", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="position_assignments", to="platform.institution")),
                ("position", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assignments", to="platform.position")),
                ("unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="position_assignments", to="platform.organizationalunit")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="simkeu_position_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "platform_position_assignments", "ordering": ["-valid_from"]},
        ),
        migrations.AddField(
            model_name="userrole",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="user_roles", to="platform.institution"),
        ),
        migrations.AddField(
            model_name="userrole",
            name="scope_level",
            field=models.CharField(choices=[("entity", "Badan hukum"), ("institution", "Institusi"), ("unit", "Unit organisasi")], default="entity", max_length=16),
        ),
        migrations.AddField(
            model_name="userrole",
            name="valid_from",
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name="userrole",
            name="valid_until",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userrole",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userrole",
            name="revocation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="userrole",
            name="revoked_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(migrate_legacy_role_scopes, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="organizationalunit",
            name="platform_unit_type_valid",
        ),
        migrations.AddConstraint(
            model_name="entity",
            constraint=models.CheckConstraint(condition=Q(fiscal_year_start_month__gte=1, fiscal_year_start_month__lte=12), name="platform_entity_fy_month_ck"),
        ),
        migrations.AddConstraint(
            model_name="entity",
            constraint=models.CheckConstraint(condition=Q(legal_form__in=["foundation", "association", "other"]), name="platform_entity_legal_form_ck"),
        ),
        migrations.AddConstraint(
            model_name="institution",
            constraint=models.UniqueConstraint(fields=("entity", "code"), name="platform_institution_entity_code_uniq"),
        ),
        migrations.AddConstraint(
            model_name="institution",
            constraint=models.CheckConstraint(condition=Q(institution_type__in=["university", "institute", "college", "polytechnic", "academy", "other"]), name="platform_institution_type_ck"),
        ),
        migrations.AddIndex(
            model_name="institution",
            index=models.Index(fields=["entity", "is_active"], name="platform_inst_entity_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="organizationalunit",
            constraint=models.CheckConstraint(condition=Q(unit_type__in=["university", "faculty", "department", "unit", "campus", "dept", "study_program", "bureau", "section", "subsection", "laboratory", "business", "support"]), name="platform_unit_type_valid"),
        ),
        migrations.AddIndex(
            model_name="organizationalunit",
            index=models.Index(fields=["entity", "institution", "parent"], name="platform_unit_tree_scope_idx"),
        ),
        migrations.AddIndex(
            model_name="organizationalunit",
            index=models.Index(fields=["entity", "is_cost_center", "is_active"], name="platform_unit_cost_center_idx"),
        ),
        migrations.AddConstraint(
            model_name="position",
            constraint=models.CheckConstraint(condition=Q(category__in=["governing", "structural", "functional", "staff", "other"]), name="platform_position_category_ck"),
        ),
        migrations.AddConstraint(
            model_name="positionassignment",
            constraint=models.CheckConstraint(condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")), name="platform_position_dates_ck"),
        ),
        migrations.AddIndex(
            model_name="positionassignment",
            index=models.Index(fields=["user", "valid_from", "valid_until"], name="platform_pos_user_dates_idx"),
        ),
        migrations.AddIndex(
            model_name="positionassignment",
            index=models.Index(fields=["entity", "unit"], name="platform_pos_entity_unit_idx"),
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.CheckConstraint(condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")), name="platform_user_role_dates_ck"),
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.CheckConstraint(condition=Q(scope_level="entity", institution__isnull=True, unit__isnull=True) | Q(scope_level="institution", institution__isnull=False, unit__isnull=True) | Q(scope_level="unit", unit__isnull=False), name="platform_user_role_scope_shape_ck"),
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.CheckConstraint(condition=Q(scope_level__in=["entity", "institution", "unit"]), name="platform_user_role_scope_value_ck"),
        ),
        migrations.RemoveConstraint(
            model_name="userrole",
            name="platform_user_role_uniq",
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.UniqueConstraint(fields=("user", "role", "entity", "scope_level", "institution", "unit"), name="platform_user_role_scope_uniq", nulls_distinct=False),
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
