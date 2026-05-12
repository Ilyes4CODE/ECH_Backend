# serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import UserProfile


def _is_arabic(request):
    """Detect if the request is from an Arabic-language client."""
    if request is None:
        return False
    lang = (request.META.get('HTTP_X_USER_LANG') or
            request.META.get('HTTP_ACCEPT_LANGUAGE', '').split(',')[0].split('-')[0])
    return lang.strip().lower().startswith('ar')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        request = self.context.get('request')
        ar = _is_arabic(request)

        try:
            data = super().validate(attrs)
        except serializers.ValidationError:
            raise serializers.ValidationError(
                'اسم المستخدم أو كلمة المرور غير صحيحة.' if ar
                else "Identifiant ou mot de passe incorrect."
            )

        user = self.user
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError(
                'الملف الشخصي للمستخدم غير موجود.' if ar
                else "Profil utilisateur introuvable."
            )

        user_groups = user.groups.values_list('name', flat=True)

        if 'Admin' not in user_groups and not profile.is_active:
            raise serializers.ValidationError(
                '⚠️ هذا الحساب غير نشط. يرجى التواصل مع المسؤول.' if ar
                else "⚠️ Votre compte n'est pas encore activé. Veuillez contacter l'administrateur."
            )

        data['username'] = user.username
        data['groups'] = list(user_groups)
        return data


