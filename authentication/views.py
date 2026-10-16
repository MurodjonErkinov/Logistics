import os
import re

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .throttles import AuthAddressThrottle, LoginAccountThrottle, RegistrationThrottle, RefreshThrottle, RegistrationCodeAddressThrottle, RegistrationPhoneThrottle

from .serializers import ProfileSerializer, RegistrationSerializer, UserSerializer, SecureTokenRefreshSerializer, PhoneVerificationSerializer
from .verification import new_verification


class LoginView(TokenObtainPairView):
    throttle_classes = [LoginAccountThrottle, AuthAddressThrottle]


class RefreshView(TokenRefreshView):
    serializer_class = SecureTokenRefreshSerializer
    throttle_classes = [RefreshThrottle]


class RegisterView(generics.CreateAPIView):
    throttle_classes = [RegistrationThrottle]
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class RegistrationCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegistrationCodeAddressThrottle, RegistrationPhoneThrottle]

    def post(self, request):
        username = os.getenv("DRIVER_BOT_USERNAME", "").lstrip("@")
        if not os.getenv("DRIVER_BOT_TOKEN") or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            return Response({"detail": "Telegram tasdiqlash boti sozlanmagan. Birozdan keyin qayta urinib ko‘ring."}, status=503)
        serializer = PhoneVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = new_verification(serializer.validated_data["phone_number"])
        return Response({"verification_id": str(row.verification_id), "bot_url": f"https://t.me/{username}?start=reg_{row.verification_id.hex}", "retry_after": 60}, status=201)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"refresh": ["This field is required."]}, status=400)
        try:
            token = RefreshToken(refresh)
            if str(token["user_id"]) != str(request.user.pk):
                return Response({"detail": "Token belongs to another user."}, status=403)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=400)
        return Response(status=204)


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
