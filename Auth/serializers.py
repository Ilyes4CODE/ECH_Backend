# serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import UserProfile

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("Profil utilisateur introuvable.")

        user_groups = user.groups.values_list('name', flat=True)

        # Check if user is in Viewer or Secretary and not active
        if 'Admin' not in user_groups and not profile.is_active:
            raise serializers.ValidationError("⚠️ Votre compte n'est pas encore activé. Veuillez contacter l'administrateur.")

        # Include additional data in the response if needed
        data['username'] = user.username
        data['groups'] = list(user_groups)
        return data


