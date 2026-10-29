"""StudySync data model: students, tutors, rooms, slots, bookings, reviews, favorites."""
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q
from django.utils import timezone
from .validators import validate_image, validate_pdf


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='students/photos/', blank=True, validators=[validate_image])
    study_notes = models.FileField(upload_to='students/notes/', blank=True, validators=[validate_pdf])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Tutor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='tutor_profile')
    display_name = models.CharField(max_length=120)
    subjects = models.CharField(max_length=200, help_text='Comma-separated subjects')
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=120, default='Leddy Library')
    photo = models.ImageField(upload_to='tutors/photos/', blank=True, validators=[validate_image])
    requires_approval = models.BooleanField(
        default=False, help_text='New booking requests stay pending until you approve them.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    kind = 'tutor'

    def __str__(self):
        return self.display_name

    @property
    def subject_list(self):
        return [item.strip() for item in self.subjects.split(',') if item.strip()]

    @property
    def rating_summary(self):
        data = self.reviews.aggregate(avg=Avg('rating'))
        count = self.reviews.count()
        return {'avg': round(data['avg'], 1) if data['avg'] else None, 'count': count}


class Room(models.Model):
    name = models.CharField(max_length=110)
    building = models.CharField(max_length=120)
    capacity = models.PositiveSmallIntegerField(default=4)
    amenities = models.CharField(max_length=230, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='rooms/', blank=True, validators=[validate_image])
    is_active = models.BooleanField(default=True)

    kind = 'room'

    @property
    def amenity_list(self):
        return [item.strip() for item in self.amenities.split(',') if item.strip()]

    def __str__(self):
        return f'{self.name} · {self.building}'


class AvailabilitySlot(models.Model):
    """Precisely one bookable resource: a tutor OR a room."""
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, null=True, blank=True, related_name='slots')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['date', 'start_time']
        indexes = [models.Index(fields=['date', 'start_time']),
                   models.Index(fields=['tutor', 'date']),
                   models.Index(fields=['room', 'date'])]
        constraints = [models.CheckConstraint(
            condition=(Q(tutor__isnull=False, room__isnull=True) | Q(tutor__isnull=True, room__isnull=False)),
            name='slot_exactly_one_resource',
        )]

    def clean(self):
        if bool(self.tutor_id) == bool(self.room_id):
            raise ValidationError('A slot must belong to a tutor or a room, not both.')
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError('End time must be later than start time.')

    @property
    def resource(self):
        return self.tutor if self.tutor_id else self.room

    @property
    def kind(self):
        return 'tutor' if self.tutor_id else 'room'

    @property
    def is_past(self):
        now = timezone.localtime()
        return timezone.make_aware(datetime.combine(self.date, self.start_time), timezone.get_current_timezone()) <= now

    def __str__(self):
        return f'{self.resource}: {self.date} {self.start_time:%H:%M}–{self.end_time:%H:%M}'


class Booking(models.Model):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    DECLINED = 'declined'
    STATUS_CHOICES = [(PENDING, 'Awaiting approval'), (CONFIRMED, 'Confirmed'),
                      (CANCELLED, 'Cancelled'), (DECLINED, 'Declined')]
    ACTIVE = (PENDING, CONFIRMED)  # statuses that occupy a slot

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='bookings')
    slot = models.ForeignKey(AvailabilitySlot, on_delete=models.PROTECT, related_name='bookings')
    notes = models.TextField(blank=True, max_length=750)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=CONFIRMED)
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-slot__date', '-slot__start_time']
        indexes = [models.Index(fields=['student', 'status']), models.Index(fields=['status', 'reminder_sent'])]
        constraints = [models.UniqueConstraint(
            fields=['slot'], condition=Q(status__in=['pending', 'confirmed']), name='one_active_booking_per_slot',
        )]

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def is_completed(self):
        return self.status == self.CONFIRMED and self.slot.is_past

    @property
    def tutor_user(self):
        return self.slot.tutor.user if self.slot.tutor_id else None

    @property
    def display_status(self):
        return 'Completed' if self.is_completed else self.get_status_display()

    @property
    def tone(self):
        if self.is_completed:
            return 'past'
        return {self.PENDING: 'wait', self.CONFIRMED: 'ok'}.get(self.status, 'off')

    def __str__(self):
        return f'{self.student} → {self.slot} ({self.status})'


class BookingMessage(models.Model):
    """A short note between the student and the tutor about one booking."""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender} on booking {self.booking_id}'


class Notification(models.Model):
    """In-app notification shown under the bell icon."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=30, default='info')
    title = models.CharField(max_length=140)
    body = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read', '-created_at'])]

    def __str__(self):
        return f'{self.user}: {self.title}'


class Review(models.Model):
    """A student's rating of a tutor (one per student/tutor, editable)."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reviews')
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['student', 'tutor'], name='one_review_per_student_tutor')]

    def __str__(self):
        return f'{self.student} rated {self.tutor}: {self.rating}/5'


class Favorite(models.Model):
    """A student's saved tutor or room (exactly one of the two)."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='favorites')
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, null=True, blank=True, related_name='favorited_by')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(tutor__isnull=False, room__isnull=True) | Q(tutor__isnull=True, room__isnull=False)),
                name='favorite_exactly_one_resource'),
            models.UniqueConstraint(fields=['student', 'tutor'], condition=Q(tutor__isnull=False), name='unique_favorite_tutor'),
            models.UniqueConstraint(fields=['student', 'room'], condition=Q(room__isnull=False), name='unique_favorite_room'),
        ]

    @property
    def resource(self):
        return self.tutor if self.tutor_id else self.room

    def __str__(self):
        return f'{self.student} ♥ {self.resource}'
