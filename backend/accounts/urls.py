from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    ChangePasswordView, LogoutView, MeView, RegisterView,
    CorporateInvitationView, CorporateInvitationDetailView, AcceptInvitationView
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="auth_logout"),
    path("me/", MeView.as_view(), name="auth_me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth_change_password"),
    path("portal/invitations/", CorporateInvitationView.as_view(), name="portal_invitations"),
    path("portal/invitations/<uuid:pk>/", CorporateInvitationDetailView.as_view(), name="portal_invitation_detail"),
    path("portal/invitations/<uuid:pk>/accept/", AcceptInvitationView.as_view(), name="portal_accept_invitation"),
]

