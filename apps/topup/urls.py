from django.urls import path
from .views import FavoriteNumberListCreateView, TransactionCreateView, TransactionListView

urlpatterns = [
    path("favorites/", FavoriteNumberListCreateView.as_view(), name="favorite-number-list-create"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path("transactions/create/", TransactionCreateView.as_view(), name="transaction-create"),
]
