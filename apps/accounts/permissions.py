from rest_framework.permissions import BasePermission


class IsApprovedReseller(BasePermission):
    message = "Your reseller account is not approved for access yet."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and getattr(user, "approval_status", "pending") == "approved"
        )
