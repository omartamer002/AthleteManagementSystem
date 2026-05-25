from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AthleteInfoViewSet, OwnerViewSet, FitnessViewSet,
    SwimmingViewSet, BasketballViewSet, FootballViewSet, CrossFitViewSet,
    AttendanceRecordViewSet, InjuryRecordViewSet
)
from .auth_views import (
    SignUpView, SignInView, ForgotPasswordView, ResetPasswordView,
    SocialSignUpView, SocialSignInView, LogoutView
)

router = DefaultRouter()
router.register(r'athletes', AthleteInfoViewSet)
router.register(r'owners', OwnerViewSet)
router.register(r'fitness', FitnessViewSet)
router.register(r'swimming', SwimmingViewSet)
router.register(r'basketball', BasketballViewSet)
router.register(r'football', FootballViewSet)
router.register(r'crossfit', CrossFitViewSet)
router.register(r'attendance', AttendanceRecordViewSet)
router.register(r'injuries', InjuryRecordViewSet)

urlpatterns = [
    path('auth/signup/', SignUpView.as_view(), name='auth-signup'),
    path('auth/signin/', SignInView.as_view(), name='auth-signin'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='auth-reset-password'),
    path('auth/social/signup/', SocialSignUpView.as_view(), name='auth-social-signup'),
    path('auth/social/signin/', SocialSignInView.as_view(), name='auth-social-signin'),
    path('', include(router.urls)),
]
