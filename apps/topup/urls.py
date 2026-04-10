from django.urls import path
from .views import (
    FavoriteNumberDetailView,
    FavoriteNumberListCreateView,
    ScheduledTopupDetailView,
    ScheduledTopupListCreateView,
    TransactionCreateView,
    TransactionListView,
)

urlpatterns = [
    path("favorites/", FavoriteNumberListCreateView.as_view(), name="favorite-number-list-create"),
    path("favorites/<int:pk>/", FavoriteNumberDetailView.as_view(), name="favorite-number-detail"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path("transactions/create/", TransactionCreateView.as_view(), name="transaction-create"),
    path("scheduled/", ScheduledTopupListCreateView.as_view(), name="scheduled-topup-list-create"),
    path("scheduled/<int:pk>/", ScheduledTopupDetailView.as_view(), name="scheduled-topup-detail"),
]
