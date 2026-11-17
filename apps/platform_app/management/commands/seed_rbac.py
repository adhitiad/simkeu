from __future__ import annotations

from argparse import ArgumentParser

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from apps.platform_app.models import Entity, Role
from apps.platform_app.services import assign_role, seed_roles


class Command(BaseCommand):
    help = "Seed peran, izin, dan opsional penugasan admin awal."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--user", help="Username pengguna yang akan diberi peran.")
        parser.add_argument("--role", default=Role.RECTOR, help="Kode peran (default: RECTOR).")
        parser.add_argument("--entity-id", type=int, help="ID entitas untuk penugasan.")
        parser.add_argument("--entity-code", help="Kode entitas untuk penugasan.")
        parser.add_argument("--entity-name", help="Nama entitas saat membuat baru.")

    def handle(self, *args: object, **options: object) -> None:
        created_roles, permission_count = seed_roles()
        self.stdout.write(f"Peran baru: {created_roles}; izin yang dikelola: {permission_count}.")

        username = options.get("user")
        if not username:
            return
        role_code = str(options["role"])
        try:
            role = Role.objects.get(code=role_code, is_active=True)
        except Role.DoesNotExist as exc:
            raise CommandError(f"Peran {role_code} tidak ditemukan.") from exc

        entity_id = options.get("entity_id")
        entity_code = options.get("entity_code")
        if not entity_id and not entity_code:
            raise CommandError("Berikan --entity-id atau --entity-code saat memakai --user.")
        if entity_id:
            try:
                entity = Entity.objects.get(pk=int(str(entity_id)))
            except Entity.DoesNotExist as exc:
                raise CommandError(f"Entitas {entity_id} tidak ditemukan.") from exc
        else:
            entity, _ = Entity.objects.get_or_create(
                code=str(entity_code),
                defaults={"name": str(options.get("entity_name") or entity_code)},
            )

        try:
            user = User.objects.get(username=str(username))
        except User.DoesNotExist as exc:
            raise CommandError(f"Pengguna {username} tidak ditemukan.") from exc

        assignment = assign_role(actor=user, user=user, role=role, entity=entity)
        self.stdout.write(
            f"Penugasan {user.username} -> {role.code}@{entity.code} "
            f"({'aktif' if assignment.is_active else 'nonaktif'})."
        )
