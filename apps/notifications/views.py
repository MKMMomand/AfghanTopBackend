from rest_framework import generics

from apps.accounts.permissions import IsApprovedReseller

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    ordering = ["-created_at"]
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")
