from django.urls import path
from .views import ShopkeeperProfileView, ShopDocumentListCreateView, DashboardSummaryView

urlpatterns = [
    path("profile/", ShopkeeperProfileView.as_view(), name="shopkeeper-profile"),
    path("documents/", ShopDocumentListCreateView.as_view(), name="shop-document-list-create"),
    path("dashboard-summary/", DashboardSummaryView.as_view(), name="shop-dashboard-summary"),
]
