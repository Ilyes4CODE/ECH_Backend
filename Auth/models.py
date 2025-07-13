from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/',default="Default_pfp.jpg", blank=True, null=True)
    username = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.username