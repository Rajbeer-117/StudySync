"""Email verification: signed, expiring links (no extra database table needed)."""
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.urls import reverse

from .models import Student, Tutor

SALT = 'studysync.email-verification'
MAX_AGE_SECONDS = 3 * 24 * 3600
RESEND_COOLDOWN_SECONDS = 60


def _profile(user):
    if not user.is_authenticated:
        return None
    return Student.objects.filter(user=user).first() or Tutor.objects.filter(user=user).first()


def is_verified(user):
    """Accounts without a profile (admins) and legacy accounts count as verified."""
    profile = _profile(user)
    return True if profile is None else profile.email_verified


def make_token(user):
    return signing.dumps({'u': user.pk, 'e': user.email}, salt=SALT)


def read_token(token):
    """Return the payload dict, or None if the token is forged or expired."""
    try:
        return signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:  # includes SignatureExpired
        return None


def send_verification_email(request, user):
    link = request.build_absolute_uri(reverse('verify_email', args=[make_token(user)]))
    body = (f'Hi {user.first_name or "there"},\n\nConfirm your email to start booking on StudySync:\n{link}\n\n'
            'The link works for 3 days. If you did not create this account, ignore this message.\n\n— StudySync')
    send_mail('Confirm your StudySync email', body, None, [user.email], fail_silently=True)


def resend_allowed(user):
    """True at most once per cooldown window per user."""
    return cache.add(f'verify-resend:{user.pk}', 1, RESEND_COOLDOWN_SECONDS)


def mark_verified(user):
    Student.objects.filter(user=user).update(email_verified=True)
    Tutor.objects.filter(user=user).update(email_verified=True)
