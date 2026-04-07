from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ApplicationStatusSerializer,
    RegistrationValidationSerializer,
    ResellerLoginSerializer,
    ResellerRegistrationSerializer,
    UserSerializer,
)


class ResellerRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResellerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Application submitted successfully. Your reseller account is pending admin approval.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RegistrationValidationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class ResellerLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResellerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return Response(
            {
                "message": "Login successful.",
                "access": payload["access"],
                "refresh": payload["refresh"],
                "user": UserSerializer(payload["user"]).data,
            },
            status=status.HTTP_200_OK,
        )


class ApplicationStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
