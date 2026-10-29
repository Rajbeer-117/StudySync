from django.contrib import admin
from django.utils import timezone

from .models import (AvailabilitySlot, Booking, BookingMessage, Favorite, Notification, Review, Room,
                     Student, Tutor)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'subjects', 'location', 'requires_approval', 'is_active')
    list_editable = ('is_active', 'requires_approval')
    list_filter = ('is_active', 'requires_approval', 'location')
    search_fields = ('display_name', 'subjects', 'location')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'capacity', 'is_active')
    list_filter = ('is_active', 'building')
    search_fields = ('name', 'building', 'amenities')


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ('resource', 'date', 'start_time', 'end_time', 'is_active')
    list_filter = ('date', 'is_active')
    search_fields = ('tutor__display_name', 'room__name')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student', 'slot', 'status', 'created_at')
    list_filter = ('status', 'slot__date')
    search_fields = ('student__user__email', 'slot__tutor__display_name', 'slot__room__name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_cancelled', 'mark_confirmed']

    @admin.action(description='Cancel selected bookings')
    def mark_cancelled(self, request, queryset):
        queryset.filter(status__in=Booking.ACTIVE).update(status=Booking.CANCELLED, cancelled_at=timezone.now())

    @admin.action(description='Confirm selected pending bookings')
    def mark_confirmed(self, request, queryset):
        queryset.filter(status=Booking.PENDING).update(status=Booking.CONFIRMED)


@admin.register(BookingMessage)
class BookingMessageAdmin(admin.ModelAdmin):
    list_display = ('booking', 'sender', 'created_at')
    search_fields = ('body', 'sender__email')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('title', 'user__email')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('student', 'tutor', 'rating', 'created_at')
    list_filter = ('rating', 'tutor')
    search_fields = ('comment', 'tutor__display_name')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('student', 'tutor', 'room', 'created_at')
