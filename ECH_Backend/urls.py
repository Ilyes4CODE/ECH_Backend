"""
URL configuration for ECH_Backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.shortcuts import redirect
import os

FRONTEND_DIR = os.path.join(settings.BASE_DIR, 'ECH-Frontend')

def frontend_index(request):
    return redirect('/app/login.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('Auth.urls')),
    path('gestion/', include('Gestion.urls')),
    # Root redirects to login
    path('', frontend_index, name='frontend_index'),
    # Serve all ECH-Frontend files under /app/
    re_path(r'^app/(?P<path>.*)$', serve, {'document_root': FRONTEND_DIR}),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)