from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("platform", "0005_scope_guard_refinements")]

    operations = [
        migrations.RemoveConstraint(
            model_name="userrole",
            name="platform_user_role_scope_uniq",
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.UniqueConstraint(
                fields=("user", "role", "entity", "scope_level", "institution", "unit"),
                name="platform_user_role_scope_uniq",
                condition=Q(is_active=True),
                nulls_distinct=False,
            ),
        ),
    ]
