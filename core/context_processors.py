from .models import Notification


def notifications(request):
    """Unread notification count for the navigation bell."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return {'unread_count': Notification.objects.filter(user=user, is_read=False).count()}
    return {'unread_count': 0}
