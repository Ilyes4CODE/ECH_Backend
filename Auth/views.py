from django.shortcuts import render,get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from utils.decorators import group_required
from utils.i18n import msg
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
    username   = data.get('username')
    password   = data.get('password')
    first_name = data.get('first_name', '') or ''
    last_name  = data.get('last_name', '') or ''

    # Accept both 'group' (string) and 'groups' (array of strings)
    group_name = data.get('group')
    if not group_name:
        groups_arr = data.get('groups')
        if isinstance(groups_arr, list) and groups_arr:
            group_name = groups_arr[0]
        elif isinstance(groups_arr, str):
            group_name = groups_arr

    valid_groups = ['Admin', 'Commercial', 'Comptable', 'Secrétaire']

    if not username or not password or not group_name:
        return Response({'detail': msg(request, 'username_password_group_required')},
                        status=status.HTTP_400_BAD_REQUEST)

    if group_name not in valid_groups:
        return Response({'detail': msg(request, 'invalid_group') + f' ({", ".join(valid_groups)})'},
                        status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'detail': msg(request, 'username_exists')},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return Response({'detail': msg(request, 'group_not_found')},
                        status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.groups.add(group)

    UserProfile.objects.create(user=user, username=username, is_active=True)

    return Response({
        'detail': msg(request, 'user_created'),
        'id': user.id,
        'username': user.username,
    }, status=status.HTTP_201_CREATED)


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
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
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
def active_user(request, user_id):
    user = get_object_or_404(UserProfile, pk=user_id)
    if user.is_active:
        user.is_active = False
        user.save()
        return Response({'detail': msg(request, 'user_deactivated')}, status=status.HTTP_200_OK)
    else:
        user.is_active = True
        user.save()
        return Response({'detail': msg(request, 'user_activated')}, status=status.HTTP_200_OK)
    

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

    return Response({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_active': user.is_active,
        'groups': list(groups),
        'profile_picture': profile_pic_url,
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_update(request):
    user = request.user
    # request.data works for both JSON and multipart/form-data
    data = request.data

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Profil utilisateur introuvable.'}, status=404)

    new_username = data.get('username')
    new_first_name = data.get('first_name')
    new_last_name = data.get('last_name')
    new_email = data.get('email')
    new_password = data.get('password')
    profile_picture = request.FILES.get('profile_picture')

    if new_username:
        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
            return Response({'detail': 'Ce nom d\'utilisateur est déjà utilisé.'}, status=400)
        user.username = new_username
        profile.username = new_username  # sync UserProfile too

    if new_first_name is not None:
        user.first_name = new_first_name

    if new_last_name is not None:
        user.last_name = new_last_name

    if new_email is not None:
        user.email = new_email

    if new_password:
        if len(new_password) < 6:
            return Response({'detail': msg(request, 'password_too_short')}, status=400)
        user.set_password(new_password)

    user.save()

    if profile_picture:
        profile.profile_picture = profile_picture

    profile.save()

    return Response({'detail': msg(request, 'profile_updated')})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def Delete_User(request, user_id):
    try:
        profile = UserProfile.objects.get(id=user_id)
    except UserProfile.DoesNotExist:
        return Response({'detail': msg(request, 'profile_not_found')}, status=status.HTTP_404_NOT_FOUND)

    user = profile.user

    if user == request.user:
        return Response({'detail': msg(request, 'cannot_delete_self')}, status=status.HTTP_403_FORBIDDEN)

    user.delete()
    return Response({'detail': msg(request, 'user_deleted')}, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@group_required('Admin')
def update_user(request, user_id):
    try:
        profile = UserProfile.objects.get(id=user_id)
        user = profile.user
    except UserProfile.DoesNotExist:
        return Response({'detail': msg(request, 'profile_not_found')}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    password = data.get('password')

    group_name = data.get('group')
    if not group_name:
        groups_arr = data.get('groups')
        if isinstance(groups_arr, list) and groups_arr:
            group_name = groups_arr[0]
        elif isinstance(groups_arr, str):
            group_name = groups_arr

    valid_groups = ['Admin', 'Commercial', 'Comptable', 'Secrétaire']

    if password:
        if len(password) < 6:
            return Response({'detail': msg(request, 'password_too_short')}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)

    if 'first_name' in data:
        user.first_name = data.get('first_name') or ''
    if 'last_name' in data:
        user.last_name = data.get('last_name') or ''
    if 'email' in data:
        user.email = data.get('email') or ''

    if group_name:
        if group_name not in valid_groups:
            return Response({'detail': msg(request, 'invalid_group')}, status=status.HTTP_400_BAD_REQUEST)
        try:
            group = Group.objects.get(name=group_name)
            user.groups.clear()
            user.groups.add(group)
        except Group.DoesNotExist:
            return Response({'detail': msg(request, 'group_not_found')}, status=status.HTTP_400_BAD_REQUEST)

    user.save()
    return Response({'detail': msg(request, 'user_updated')}, status=status.HTTP_200_OK)


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