"""Login throttling and security headers."""
from django.conf import settings
from django.core.cache import cache

LOGIN_MAX_FAILURES = getattr(settings, 'LOGIN_MAX_FAILURES', 5)
LOGIN_LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 15 * 60)


def client_ip(request):
    return request.META.get('REMOTE_ADDR', 'unknown')


def _key(request, username):
    return f'login-fail:{client_ip(request)}:{(username or "").strip().lower()[:150]}'


def login_locked(request, username):
    return cache.get(_key(request, username), 0) >= LOGIN_MAX_FAILURES


def record_login_failure(request, username):
    key = _key(request, username)
    cache.add(key, 0, LOGIN_LOCKOUT_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_LOCKOUT_SECONDS)


def clear_login_failures(request, username):
    cache.delete(_key(request, username))


class SecurityHeadersMiddleware:
    """Adds a strict Content-Security-Policy and a few hardening headers (not on /admin/)."""
    POLICY = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
              "script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; "
              "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/admin/'):
            response.setdefault('Content-Security-Policy', self.POLICY)
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        return response
