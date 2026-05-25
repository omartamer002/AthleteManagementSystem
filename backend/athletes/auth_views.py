from django.contrib.auth import authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
except Exception:
    id_token = None
    google_requests = None


class SignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        confirm_password = request.data.get("confirm_password") or ""

        if not username or not email or not password:
            return Response(
                {"detail": "username, email, and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if password != confirm_password:
            return Response(
                {"detail": "password and confirm_password do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {"detail": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"detail": "Email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User(username=username, email=email)
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            return Response(
                {"detail": "Password validation failed.", "errors": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()

        return Response(
            {
                "message": "Signup successful.",
                "user": {"id": user.id, "username": user.username, "email": user.email},
            },
            status=status.HTTP_201_CREATED,
        )


class SignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = (request.data.get("identifier") or request.data.get("email") or request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not identifier or not password:
            return Response(
                {"detail": "identifier and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=identifier, password=password)
        if user is None and "@" in identifier:
            try:
                mapped_user = User.objects.get(email__iexact=identifier)
                user = authenticate(username=mapped_user.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(
            {
                "message": "Sign in successful.",
                "user": {"id": user.id, "username": user.username, "email": user.email},
            }
        )


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"message": "Logout successful."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        # Do not leak account existence.
        if not user:
            return Response({"message": "If this email exists, reset instructions were generated."})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Dev-friendly response (no OTP flow, no email service configured).
        return Response(
            {
                "message": "If this email exists, reset instructions were generated.",
                "reset": {"uid": uid, "token": token},
            }
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password") or ""
        confirm_password = request.data.get("confirm_password") or ""

        if not uid or not token or not new_password:
            return Response(
                {"detail": "uid, token, and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response(
                {"detail": "new_password and confirm_password do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response({"detail": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return Response(
                {"detail": "Password validation failed.", "errors": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password reset successful."})


def _social_identity(provider: str, token: str):
    provider = (provider or "").lower().strip()
    if provider == "google":
        if not id_token or not google_requests:
            raise ValueError("Google auth libraries are not available.")
        try:
            info = id_token.verify_oauth2_token(token, google_requests.Request())
        except Exception as exc:
            raise ValueError("Invalid Google token.") from exc
        email = (info.get("email") or "").lower().strip()
        if not email:
            raise ValueError("Google account email is missing.")
        return {
            "provider": "google",
            "email": email,
            "username_hint": info.get("name") or email.split("@")[0],
        }

    if provider == "facebook":
        try:
            req = Request(
                f"https://graph.facebook.com/me?fields=id,name,email&access_token={token}",
                headers={"Accept": "application/json"},
            )
            with urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read().decode("utf-8"))
        except URLError as exc:
            raise ValueError("Could not validate Facebook token.") from exc
        except Exception as exc:
            raise ValueError("Invalid Facebook token.") from exc

        email = (info.get("email") or "").lower().strip()
        if not email:
            raise ValueError("Facebook account email is missing.")
        return {
            "provider": "facebook",
            "email": email,
            "username_hint": info.get("name") or email.split("@")[0],
        }

    raise ValueError("Unsupported provider. Use 'google' or 'facebook'.")


def _safe_username(base: str):
    base = (base or "user").strip().replace(" ", "_")
    base = "".join(ch for ch in base if ch.isalnum() or ch in "._-") or "user"
    candidate = base[:150]
    i = 1
    while User.objects.filter(username__iexact=candidate).exists():
        suffix = f"_{i}"
        candidate = f"{base[:150-len(suffix)]}{suffix}"
        i += 1
    return candidate


class SocialSignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get("provider")
        token = request.data.get("token") or request.data.get("id_token") or request.data.get("access_token")
        if not provider or not token:
            return Response(
                {"detail": "provider and token are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            identity = _social_identity(provider, token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=identity["email"]).first()
        created = False
        if not user:
            username = _safe_username(identity["username_hint"])
            user = User(username=username, email=identity["email"])
            user.set_unusable_password()
            user.save()
            created = True

        return Response(
            {
                "message": "Social sign up successful." if created else "User already exists. Signed in with social account.",
                "created": created,
                "user": {"id": user.id, "username": user.username, "email": user.email},
                "provider": identity["provider"],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SocialSignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get("provider")
        token = request.data.get("token") or request.data.get("id_token") or request.data.get("access_token")
        if not provider or not token:
            return Response(
                {"detail": "provider and token are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            identity = _social_identity(provider, token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=identity["email"]).first()
        if not user:
            return Response(
                {"detail": "No account found. Please sign up with your social network first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "message": "Social sign in successful.",
                "user": {"id": user.id, "username": user.username, "email": user.email},
                "provider": identity["provider"],
            }
        )
