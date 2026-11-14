from .models import Notification
from .verification import is_verified


def notifications(request):
    """Unread notification count for the navigation bell, plus the email-verification banner flag."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return {'unread_count': Notification.objects.filter(user=user, is_read=False).count(),
                'email_unverified': not is_verified(user)}
    return {'unread_count': 0, 'email_unverified': False}
