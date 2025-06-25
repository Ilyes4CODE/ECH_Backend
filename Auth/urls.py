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
    path('profile/', views.profile_info, name='profile_info'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('toggle_user_status/<int:pk>/',views.active_user),
    path('delete_user/<int:pk>/', views.Delete_User, name='delete_user'),
    path('update_user/<int:profile_id>/', views.update_user, name='update_user'),
]
