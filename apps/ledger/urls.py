from django.urls import path

from .api import JournalCollectionView, TrialBalanceView

app_name = "ledger"

urlpatterns = [
    path("journals", JournalCollectionView.as_view(), name="journals"),
    path("reports/trial-balance", TrialBalanceView.as_view(), name="trial-balance"),
]
