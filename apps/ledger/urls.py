from django.urls import path

from .api import JournalCollectionView

app_name = "ledger"

urlpatterns = [
    path("journals", JournalCollectionView.as_view(), name="journals"),
]
