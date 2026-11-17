from django.urls import path

from . import views

app_name = "budget"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("fiscal-years/new/", views.fiscal_year_create, name="fiscal_year_create"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<uuid:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<uuid:plan_id>/lines/new/", views.plan_line_create, name="plan_line_create"),
    path("plans/<uuid:plan_id>/action/", views.plan_action, name="plan_action"),
    path("rapbu/consolidate/", views.rapbu_consolidate, name="rapbu_consolidate"),
    path("plans/<uuid:rapbu_id>/create-apbu/", views.apbu_from_rapbu, name="apbu_from_rapbu"),
    path("allocations/", views.allocation_list, name="allocation_list"),
    path("revisions/new/", views.revision_create, name="revision_create"),
    path("revisions/<uuid:revision_id>/", views.revision_detail, name="revision_detail"),
    path("revisions/<uuid:revision_id>/action/", views.revision_action, name="revision_action"),
    path("commitments/", views.commitment_list, name="commitment_list"),
    path("commitments/new/", views.commitment_create, name="commitment_create"),
    path(
        "commitments/<uuid:commitment_id>/action/",
        views.commitment_action,
        name="commitment_action",
    ),
]
