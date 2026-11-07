"""Web-app plumbing: manifest, service worker and offline page (installable on Windows, macOS, Android, iOS, Linux)."""
import hashlib
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe

ICONS = (
    ('core/img/icon-192.png', '192x192', 'any'),
    ('core/img/icon-512.png', '512x512', 'any'),
    ('core/img/icon-maskable-512.png', '512x512', 'maskable'),
)
PRECACHE = ('core/css/style.css', 'core/js/main.js', 'core/js/theme-init.js', 'core/img/icon-192.png', 'core/img/favicon.svg')


@require_safe
@cache_control(max_age=3600)
def manifest(request):
    data = {
        'id': '/', 'name': 'StudySync', 'short_name': 'StudySync',
        'description': 'Find campus tutors and study rooms, and book open sessions in a few taps.',
        'start_url': '/?source=pwa', 'scope': '/', 'display': 'standalone',
        'display_override': ['window-controls-overlay', 'standalone', 'minimal-ui'],
        'orientation': 'any', 'lang': 'en', 'dir': 'ltr', 'categories': ['education', 'productivity'],
        'background_color': '#030407', 'theme_color': '#030407',
        'icons': [{'src': static(path), 'sizes': size, 'type': 'image/png', 'purpose': purpose} for path, size, purpose in ICONS]
                 + [{'src': static('core/img/favicon.svg'), 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any'}],
        'shortcuts': [
            {'name': 'Explore', 'url': reverse('catalog'), 'icons': [{'src': static('core/img/icon-192.png'), 'sizes': '192x192'}]},
            {'name': 'My bookings', 'url': reverse('my_bookings'), 'icons': [{'src': static('core/img/icon-192.png'), 'sizes': '192x192'}]},
        ],
    }
    return HttpResponse(json.dumps(data), content_type='application/manifest+json')


@require_safe
@cache_control(no_cache=True)
def service_worker(request):
    urls = [static(path) for path in PRECACHE] + [reverse('offline')]
    version = hashlib.sha1('|'.join(urls).encode()).hexdigest()[:10]
    response = render(request, 'core/sw.js', {'urls_json': json.dumps(urls), 'version': version, 'offline_url': reverse('offline')},
                      content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    return response


@require_safe
def offline(request):
    return render(request, 'core/offline.html')
