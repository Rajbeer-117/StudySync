from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = 'StudySync administration'
admin.site.site_title = 'StudySync admin'
admin.site.index_title = 'Manage tutors, rooms, bookings and reviews'

handler403 = 'core.views_errors.forbidden'
handler404 = 'core.views_errors.not_found'
handler500 = 'core.views_errors.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
if settings.SERVE_MEDIA:
    urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT})]
