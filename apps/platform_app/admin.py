from django.contrib import admin

from .models import OutboxEvent

admin.site.register(OutboxEvent)