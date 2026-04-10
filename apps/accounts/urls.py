from django.urls import path

from .views import (
    ApplicationStatusView,
    ForgotPasswordRequestView,
    MeView,
    RegistrationValidationView,
    ResetPasswordConfirmView,
    ResellerLoginView,
    ResellerRegisterView,
)

urlpatterns = [
    path("register/", ResellerRegisterView.as_view(), name="register"),
    path("register-validation/", RegistrationValidationView.as_view(), name="register-validation"),
    path("login/", ResellerLoginView.as_view(), name="login"),
    path("application-status/", ApplicationStatusView.as_view(), name="application-status"),
    path("forgot-password/", ForgotPasswordRequestView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordConfirmView.as_view(), name="reset-password"),
    path("me/", MeView.as_view(), name="me"),
]
