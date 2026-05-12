from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def group_required(*group_names):
    """
    Decorator for DRF API views that checks whether the authenticated user
    belongs to one of the specified groups.  Works with JWT authentication
    (no HTML login-page redirect like @login_required).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # At this point the JWT middleware has already run, so
            # request.user is populated (or AnonymousUser).
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'detail': 'Authentication credentials were not provided.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if request.user.is_superuser or request.user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            return Response(
                {'detail': 'You do not have the required group permission.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _wrapped_view
    return decorator
