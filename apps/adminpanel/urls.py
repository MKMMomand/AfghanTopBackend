from django.urls import path

from .views import (
    AdminCreditAdjustmentView,
    AdminDashboardView,
    AdminLoginView,
    AdminMeView,
    AdminSendNotificationView,
    AdminSettlementListView,
    AdminShopkeeperDecisionView,
    AdminShopkeeperDetailView,
    AdminShopkeeperListView,
    AdminTopupListView,
)

urlpatterns = [
    path("auth/login/", AdminLoginView.as_view(), name="admin-login"),
    path("auth/me/", AdminMeView.as_view(), name="admin-me"),
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("users/", AdminShopkeeperListView.as_view(), name="admin-users"),
    path("users/<int:user_id>/", AdminShopkeeperDetailView.as_view(), name="admin-user-detail"),
    path("users/<int:user_id>/decision/", AdminShopkeeperDecisionView.as_view(), name="admin-user-decision"),
    path("users/<int:user_id>/credit-adjustment/", AdminCreditAdjustmentView.as_view(), name="admin-user-credit-adjustment"),
    path("topups/", AdminTopupListView.as_view(), name="admin-topups"),
    path("settlements/", AdminSettlementListView.as_view(), name="admin-settlements"),
    path("notifications/send/", AdminSendNotificationView.as_view(), name="admin-send-notification"),
]
