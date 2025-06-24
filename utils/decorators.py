from functools import wraps
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required

def group_required(*group_names):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.groups.filter(name__in=group_names).exists() or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            return Response({'detail': 'You do not have the required group permission.'}, status=403)
        return _wrapped_view
    return decorator
