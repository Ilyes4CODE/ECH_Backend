from django.shortcuts import render,get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from utils.decorators import group_required
from rest_framework import status
from .models import UserProfile
from django.contrib.auth.models import User,Group
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

# Create your views here.

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def Create_User(request):
    data = request.data
    username = data.get('username')
    password = data.get('password')
    group_name = data.get('group')  # Expected values: "Admin", "Secretary", "Viewer"

    if not username or not password or not group_name:
        return Response({'detail': 'username, password and group are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return Response({'detail': 'Invalid group name.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password)
    user.groups.add(group)

    # Create profile
    user_profile = UserProfile.objects.create(user=user, username=username,is_active=True)
    user_profile.save()

    return Response({'detail': f'User created and added to {group_name} group.'}, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def List_Users(request):
    profiles = UserProfile.objects.exclude(user=request.user)  
    response_data = []

    for profile in profiles:
        user = profile.user
        profile_pic_url = request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None
        user_groups = user.groups.values_list('name', flat=True)

        response_data.append({
            'id': profile.id,
            'username': user.username,
            'groups': list(user_groups),
            'profile_picture': profile_pic_url,
            'is_active': profile.is_active
        })

    return Response(response_data, status=status.HTTP_200_OK)

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
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_info(request):
    user = request.user
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Profil utilisateur introuvable.'}, status=404)

    profile_pic_url = request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None
    groups = user.groups.values_list('name', flat=True)
    main_group = groups[0] if groups else None

    return Response({
        'id': user.id,
        'username': user.username,
        'group': main_group,
        'is_active': profile.is_active,
        'profile_picture': profile_pic_url,
    })

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def profile_update(request):
    user = request.user
    data = request.data

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Profil utilisateur introuvable.'}, status=404)

    new_username = data.get('username')
    profile_picture = request.FILES.get('profile_picture')

    if new_username:
        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
            return Response({'detail': 'Ce nom d’utilisateur est déjà utilisé.'}, status=400)
        user.username = new_username
        user.save()
        profile.username = new_username  # sync UserProfile too

    if profile_picture:
        profile.profile_picture = profile_picture

    profile.save()

    return Response({'detail': 'Profil mis à jour avec succès.'})



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def Delete_User(request,pk):
    try:
        profile = UserProfile.objects.get(id=pk)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    user = profile.user

    # Prevent admin from deleting themselves
    if user == request.user:
        return Response({'error': 'You cannot delete your own account.'}, status=status.HTTP_403_FORBIDDEN)

    user.delete()
    return Response({'message': 'User deleted successfully.'}, status=status.HTTP_200_OK)



@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def update_user(request, profile_id):
    try:
        profile = UserProfile.objects.get(id=profile_id)
        user = profile.user
    except UserProfile.DoesNotExist:
        return Response({'message': 'Profil utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    password = data.get('password')
    group_name = data.get('groups')

    if password:
        if len(password) < 6:
            return Response({'message': 'Le mot de passe doit contenir au moins 6 caractères.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)

    if group_name:
        try:
            group = Group.objects.get(name=group_name)
            user.groups.clear()
            user.groups.add(group)
        except Group.DoesNotExist:
            return Response({'message': f"Groupe '{group_name}' introuvable."}, status=status.HTTP_400_BAD_REQUEST)

    user.save()
    return Response({'message': 'Utilisateur mis à jour avec succès.'}, status=status.HTTP_200_OK)