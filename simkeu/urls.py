from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import healthz, home, readyz
from apps.platform_app.views import (
    dashboard,
    entity_create,
    entity_list,
    login_view,
    role_assign,
    role_assignment_list,
    role_revoke,
    unit_create,
    unit_list,
)

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("login/", login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("entities/", entity_list, name="entity_list"),
    path("entities/new/", entity_create, name="entity_create"),
    path("units/", unit_list, name="unit_list"),
    path("units/new/", unit_create, name="unit_create"),
    path("roles/", role_assignment_list, name="role_assignment_list"),
    path("roles/assign/", role_assign, name="role_assign"),
    path("roles/<int:assignment_id>/revoke/", role_revoke, name="role_revoke"),
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("", include("django_prometheus.urls")),
    path("api/ledger/", include("apps.ledger.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
