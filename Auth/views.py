from django.shortcuts import render,get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from utils.decorators import group_required
from rest_framework import status
from .models import UserProfile
from django.contrib.auth.models import User
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

# Create your views here.

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def Create_User(request):
    data = request.data
    if not data.get('username') or not data.get('password'):
        return Response({'detail': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=data['username']).exists():
        return Response({'detail': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    user = User.objects.create_user(username=data['username'], password=data['password'])
    user_profile = UserProfile.objects.create(user=user, username=data['username'])
    user_profile.save()
    return Response({'detail': 'User created successfully.'}, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def active_user(request,pk):
    user = get_object_or_404(UserProfile, pk=pk)
    if user.is_active:
        user.is_active = False
        user.save()
        return Response({'detail': 'User deactivated successfully.'}, status=status.HTTP_200_OK)
    else:
        user.is_active = True
        user.save()
        return Response({'detail': 'User activated successfully.'}, status=status.HTTP_200_OK)