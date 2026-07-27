from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "User registered successfully.",
                    "user": UserSerializer(user).data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from .models import CorporateInvitation, CorporateMembership, CorporateRole, User, UserRole
from .serializers import CorporateInvitationSerializer, AcceptInvitationSerializer
from .permissions import IsCorporateAdmin

class CorporateInvitationView(APIView):
    permission_classes = [IsAuthenticated, IsCorporateAdmin]

    def get(self, request):
        # Admin can view all invitations for companies they manage
        if request.user.is_superuser:
            qs = CorporateInvitation.objects.all()
        else:
            companies = request.user.active_memberships.filter(role=CorporateRole.ADMIN).values_list("company_id", flat=True)
            qs = CorporateInvitation.objects.filter(company_id__in=companies)
        
        serializer = CorporateInvitationSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CorporateInvitationSerializer(data=request.data)
        if serializer.is_valid():
            company = serializer.validated_data["company"]
            # Double check permissions
            if not request.user.is_superuser:
                is_admin = request.user.active_memberships.filter(company=company, role=CorporateRole.ADMIN).exists()
                if not is_admin:
                    return Response({"detail": "You do not have permission to invite users to this company."}, status=status.HTTP_403_FORBIDDEN)
            
            # Default expiry 7 days
            expires_at = timezone.now() + timedelta(days=7)
            invitation = serializer.save(invited_by=request.user, expires_at=expires_at)
            return Response(CorporateInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CorporateInvitationDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        invitation = get_object_or_404(CorporateInvitation, pk=pk)
        if not invitation.is_valid():
            return Response({"detail": "This invitation has expired or has already been used."}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CorporateInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        # Requires authenticated corporate admin
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        invitation = get_object_or_404(CorporateInvitation, pk=pk)
        if not request.user.is_superuser:
            is_admin = request.user.active_memberships.filter(company=invitation.company, role=CorporateRole.ADMIN).exists()
            if not is_admin:
                return Response({"detail": "You do not have permission to revoke this invitation."}, status=status.HTTP_403_FORBIDDEN)
        
        invitation.delete()
        return Response({"message": "Invitation revoked successfully."}, status=status.HTTP_200_OK)


class AcceptInvitationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        invitation = get_object_or_404(CorporateInvitation, pk=pk)
        if not invitation.is_valid():
            return Response({"detail": "This invitation is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = AcceptInvitationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                with transaction.atomic():
                    # Create User
                    user = User.objects.create_user(
                        username=data["username"],
                        email=invitation.email,  # Must match the invited email
                        password=data["password"],
                        first_name=data.get("first_name", ""),
                        last_name=data.get("last_name", ""),
                        role=UserRole.COMMERCIAL  # Use a general commercial/portal user role
                    )
                    # Create Corporate Membership
                    CorporateMembership.objects.create(
                        user=user,
                        company=invitation.company,
                        role=invitation.role,
                        is_active=True
                    )
                    # Mark invitation as used
                    invitation.used_at = timezone.now()
                    invitation.save()
                    
                    return Response({"message": "Invitation accepted and account created successfully."}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

