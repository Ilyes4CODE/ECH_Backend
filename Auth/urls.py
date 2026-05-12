from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views
urlpatterns = [
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('create_user/', views.Create_User, name='create_user'),
    path('list_users/', views.List_Users, name='list_users'),
    path('list_groups/', views.List_Groups, name='list_groups'),
    path('profile/', views.profile_info, name='profile_info'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('toggle_user_status/<int:user_id>/', views.active_user, name='toggle_user_status'),
    path('delete_user/<int:user_id>/', views.Delete_User, name='delete_user'),
    path('update_user/<int:user_id>/', views.update_user, name='update_user'),
    path('permissions/', views.get_user_permissions, name='user_permissions'),
    path('users/by_group/<str:group_name>/', views.get_users_by_group, name='users_by_group'),
    path('group_statistics/', views.get_group_statistics, name='group_statistics'),
]
