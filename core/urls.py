from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('explore/', views.catalog, name='catalog'),
    path('tutors/<int:pk>/', views.tutor_detail, name='tutor_detail'),
    path('rooms/<int:pk>/', views.room_detail, name='room_detail'),
    path('tutors/<int:pk>/review/', views.submit_review, name='submit_review'),
    path('reviews/<int:pk>/delete/', views.delete_review, name='delete_review'),
    path('favorites/', views.favorites, name='favorites'),
    path('favorites/<str:kind>/<int:pk>/toggle/', views.toggle_favorite, name='toggle_favorite'),

    path('accounts/login/', views.StudyLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register, name='register'),
    path('accounts/password-change/', views.StudyPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('accounts/password-reset/sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),

    path('book/<int:slot_id>/', views.start_booking, name='start_booking'),
    path('book/review/', views.booking_review, name='booking_review'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('bookings/<int:pk>/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:pk>/message/', views.booking_message, name='booking_message'),
    path('bookings/<int:pk>/reschedule/', views.reschedule, name='reschedule'),
    path('my-bookings/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('my-bookings/<int:pk>/calendar.ics', views.booking_ics, name='booking_ics'),

    path('tutor/availability/', views.manage_slots, name='manage_slots'),
    path('tutor/availability/<int:pk>/delete/', views.delete_slot, name='delete_slot'),
    path('tutor/bookings/<int:pk>/cancel/', views.tutor_cancel_booking, name='tutor_cancel_booking'),
    path('tutor/bookings/<int:pk>/decide/', views.tutor_decide_booking, name='tutor_decide_booking'),

    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read-all/', views.notifications_read_all, name='notifications_read_all'),
    path('notifications/<int:pk>/go/', views.notification_go, name='notification_go'),

    path('api/search/', views.api_search, name='api_search'),
    path('healthz/', views.healthz, name='healthz'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
]
