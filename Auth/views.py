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
    group_name = data.get('group')  # Expected values: "Admin", "Commercial", "Comptable", "Secrétaire"

    # Valid groups list
    valid_groups = ['Admin', 'Commercial', 'Comptable', 'Secrétaire']

    if not username or not password or not group_name:
        return Response({'detail': 'username, password and group are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if group_name not in valid_groups:
        return Response({'detail': f'Invalid group name. Valid groups are: {", ".join(valid_groups)}'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return Response({'detail': f'Group "{group_name}" does not exist. Please create it first.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password)
    user.groups.add(group)

    # Create profile
    user_profile = UserProfile.objects.create(user=user, username=username, is_active=True)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def List_Groups(request):
    """Get all available groups - useful for frontend dropdowns"""
    groups = Group.objects.all().values('id', 'name')
    return Response(list(groups), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def active_user(request, pk):
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
            return Response({'detail': 'Ce nom d\'utilisateur est déjà utilisé.'}, status=400)
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
def Delete_User(request, pk):
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

    # Valid groups list
    valid_groups = ['Admin', 'Commercial', 'Comptable', 'Secrétaire']

    if password:
        if len(password) < 6:
            return Response({'message': 'Le mot de passe doit contenir au moins 6 caractères.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)

    if group_name:
        if group_name not in valid_groups:
            return Response({'message': f'Groupe invalide. Groupes valides: {", ".join(valid_groups)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            group = Group.objects.get(name=group_name)
            user.groups.clear()
            user.groups.add(group)
        except Group.DoesNotExist:
            return Response({'message': f"Groupe '{group_name}' introuvable."}, status=status.HTTP_400_BAD_REQUEST)

    user.save()
    return Response({'message': 'Utilisateur mis à jour avec succès.'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_permissions(request):
    """Get current user's permissions based on their group"""
    user = request.user
    user_groups = user.groups.values_list('name', flat=True)
    main_group = user_groups[0] if user_groups else None
    
    permissions = {
        'can_create_users': main_group == 'Admin',
        'can_delete_users': main_group == 'Admin',
        'can_view_users': main_group == 'Admin',
        'can_update_users': main_group == 'Admin',
        'can_manage_commercial': main_group in ['Admin', 'Commercial'],
        'can_manage_comptable': main_group in ['Admin', 'Comptable'],
        'can_view_reports': main_group in ['Admin', 'Commercial', 'Comptable'],
        'is_secretaire': main_group == 'Secrétaire',
        'group': main_group
    }
    
    return Response(permissions, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def get_users_by_group(request, group_name):
    """Get users filtered by specific group"""
    valid_groups = ['Admin', 'Commercial', 'Comptable', 'Secrétaire']
    
    if group_name not in valid_groups:
        return Response({'error': f'Invalid group name. Valid groups are: {", ".join(valid_groups)}'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    try:
        group = Group.objects.get(name=group_name)
        users = User.objects.filter(groups=group)
        profiles = UserProfile.objects.filter(user__in=users)
        
        response_data = []
        for profile in profiles:
            user = profile.user
            profile_pic_url = request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None
            
            response_data.append({
                'id': profile.id,
                'username': user.username,
                'group': group_name,
                'profile_picture': profile_pic_url,
                'is_active': profile.is_active
            })
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Group.DoesNotExist:
        return Response({'error': f'Group "{group_name}" does not exist.'}, 
                       status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def get_group_statistics(request):
    """Get statistics about users in each group"""
    statistics = {}
    
    for group_name in ['Admin', 'Commercial', 'Comptable', 'Secrétaire']:
        try:
            group = Group.objects.get(name=group_name)
            active_users = UserProfile.objects.filter(user__groups=group, is_active=True).count()
            inactive_users = UserProfile.objects.filter(user__groups=group, is_active=False).count()
            
            statistics[group_name] = {
                'active_users': active_users,
                'inactive_users': inactive_users,
                'total_users': active_users + inactive_users
            }
        except Group.DoesNotExist:
            statistics[group_name] = {
                'active_users': 0,
                'inactive_users': 0,
                'total_users': 0
            }
    
    return Response(statistics, status=status.HTTP_200_OK)