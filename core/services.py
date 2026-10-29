"""Business logic for StudySync: availability, booking, rescheduling, notifications.

Views stay thin; everything that must be atomic or reused lives here.
"""
from datetime import datetime, timedelta

from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from .models import AvailabilitySlot, Booking, BookingMessage, Notification


class BookingError(Exception):
    """A booking rule was violated; the message is safe to show to the user."""


# --------------------------------------------------------------------------- availability
def available_slots(queryset=None):
    """Slots that are in the future, active, and not overlapped by a pending/confirmed booking.

    Evaluated entirely in the database (two EXISTS sub-queries) so it scales with data.
    """
    queryset = AvailabilitySlot.objects.all() if queryset is None else queryset
    now = timezone.localtime()

    def clash(field):
        return Booking.objects.filter(
            status__in=Booking.ACTIVE,
            **{f'slot__{field}': OuterRef(field)},
            slot__date=OuterRef('date'),
            slot__start_time__lt=OuterRef('end_time'),
            slot__end_time__gt=OuterRef('start_time'),
        )

    return (
        queryset.filter(is_active=True)
        .filter(Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time()))
        .filter(Q(tutor__isnull=True) | Q(tutor__is_active=True))
        .filter(Q(room__isnull=True) | Q(room__is_active=True))
        .annotate(_tutor_clash=Exists(clash('tutor_id')), _room_clash=Exists(clash('room_id')))
        .filter(_tutor_clash=False, _room_clash=False)
        .select_related('tutor', 'room')
        .order_by('date', 'start_time')
    )


def slot_available(slot):
    return available_slots(AvailabilitySlot.objects.filter(pk=slot.pk)).exists()


def student_clash(student, slot, exclude=None):
    """True if the student already holds an active booking overlapping this slot."""
    qs = Booking.objects.filter(
        student=student, status__in=Booking.ACTIVE, slot__date=slot.date,
        slot__start_time__lt=slot.end_time, slot__end_time__gt=slot.start_time,
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.exists()


# --------------------------------------------------------------------------- booking
def create_booking(student, slot_id, notes=''):
    """Create a booking atomically. Raises BookingError with a friendly message."""
    with transaction.atomic():
        slot = (AvailabilitySlot.objects.select_for_update().select_related('tutor', 'room')
                .filter(pk=slot_id).first())
        if slot is None:
            raise BookingError('That time no longer exists.')
        if not slot_available(slot):
            raise BookingError('This time was just taken. Please choose another slot.')
        if student_clash(student, slot):
            raise BookingError('You already have a booking that overlaps this time.')
        needs_approval = bool(slot.tutor_id and slot.tutor.requires_approval)
        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    student=student, slot=slot, notes=notes,
                    status=Booking.PENDING if needs_approval else Booking.CONFIRMED)
        except IntegrityError as exc:
            raise BookingError('Another booking just took this slot. Please choose a different time.') from exc
    return booking


def reschedule_booking(booking, new_slot_id):
    """Move a booking to another slot of the same tutor/room, atomically."""
    with transaction.atomic():
        current = (Booking.objects.select_for_update()
                   .select_related('slot__tutor', 'slot__room', 'student__user').get(pk=booking.pk))
        if not current.is_active or current.slot.is_past:
            raise BookingError('This booking can no longer be rescheduled.')
        new = (AvailabilitySlot.objects.select_for_update().select_related('tutor', 'room')
               .filter(pk=new_slot_id).first())
        if (new is None or new.pk == current.slot_id or new.tutor_id != current.slot.tutor_id
                or new.room_id != current.slot.room_id):
            raise BookingError('Choose a different time with the same tutor or room.')
        if not slot_available(new):
            raise BookingError('That time is no longer available.')
        if student_clash(current.student, new, exclude=current):
            raise BookingError('You already have a booking that overlaps that time.')
        old_slot = current.slot
        current.slot = new
        current.save(update_fields=['slot', 'updated_at'])
    return current, old_slot


def set_status(booking, status):
    booking.status = status
    fields = ['status', 'updated_at']
    if status in (Booking.CANCELLED, Booking.DECLINED):
        booking.cancelled_at = timezone.now()
        fields.append('cancelled_at')
    booking.save(update_fields=fields)
    return booking


def slot_start(slot):
    return timezone.make_aware(datetime.combine(slot.date, slot.start_time), timezone.get_current_timezone())


# --------------------------------------------------------------------------- notifications
def when_text(slot):
    start, end = slot.start_time, slot.end_time
    return f"{slot.date:%A, %B} {slot.date.day} · {start:%I:%M %p} – {end:%I:%M %p}".replace(' 0', ' ')


def push(user, kind, title, body='', url=''):
    if user is not None:
        Notification.objects.create(user=user, kind=kind, title=title[:140], body=body[:300], url=url[:200])


def _mail(user, subject, body):
    if user is not None and user.email:
        send_mail(subject, body + '\n\n— StudySync', None, [user.email], fail_silently=True)


def notify_booking(booking, event, actor=None):
    """Tell the right people about a booking event (in-app, plus email for key events).

    event: requested | confirmed | approved | declined | cancelled | rescheduled | reminder
    """
    slot = booking.slot
    student_user = booking.student.user
    tutor_user = booking.tutor_user
    url = reverse('booking_detail', args=[booking.pk])
    who = slot.resource
    when = when_text(slot)
    student_name = student_user.get_full_name() or student_user.email or 'A student'
    by_student = actor is not None and actor == student_user

    if event == 'requested':
        push(student_user, 'booking', f'Request sent to {who}', when, url)
        _mail(student_user, f'Booking request sent: {who}', f'Your request with {who} is awaiting approval.\nWhen: {when}')
        push(tutor_user, 'request', f'New booking request from {student_name}', when, url)
        _mail(tutor_user, f'New booking request from {student_name}',
              f'{student_name} requested a session.\nWhen: {when}\nNotes: {booking.notes or "—"}\nReview it in StudySync.')
    elif event == 'confirmed':
        push(student_user, 'booking', f'Booking confirmed: {who}', when, url)
        _mail(student_user, f'Booking confirmed: {who}', f'Your booking with {who} is confirmed.\nWhen: {when}\nBooking #{booking.pk}')
        push(tutor_user, 'booking', f'{student_name} booked a session', when, url)
        _mail(tutor_user, f'New session booked by {student_name}', f'When: {when}\nNotes: {booking.notes or "—"}')
    elif event == 'approved':
        push(student_user, 'booking', f'{who} approved your request', when, url)
        _mail(student_user, f'Booking approved: {who}', f'Good news: {who} approved your session.\nWhen: {when}')
    elif event == 'declined':
        push(student_user, 'booking', f'{who} could not take your request', when, url)
        _mail(student_user, f'Booking declined: {who}', f'Unfortunately {who} could not accept this session.\nWhen: {when}\nPlease pick another time.')
    elif event == 'cancelled':
        _mail(student_user, f'Booking cancelled: {who}', f'The booking with {who} is cancelled.\nWhen: {when}')
        if by_student:
            push(student_user, 'booking', f'Booking cancelled: {who}', when, url)
            push(tutor_user, 'booking', f'{student_name} cancelled a session', when, url)
            _mail(tutor_user, f'Session cancelled by {student_name}', f'When: {when}')
        else:
            push(student_user, 'booking', f'{who} cancelled your session', when, url)
    elif event == 'rescheduled':
        push(student_user, 'booking', f'Rescheduled: {who}', when, url)
        _mail(student_user, f'Booking rescheduled: {who}', f'Your new time with {who}:\n{when}')
        push(tutor_user, 'booking', f'{student_name} rescheduled a session', when, url)
        _mail(tutor_user, f'Session rescheduled by {student_name}', f'New time: {when}')
    elif event == 'reminder':
        push(student_user, 'reminder', f'Coming up: {who}', when, url)
        _mail(student_user, f'Reminder: {who} tomorrow', f'Your session with {who} is coming up.\nWhen: {when}')
        push(tutor_user, 'reminder', f'Coming up: session with {student_name}', when, url)


def add_message(booking, sender, body):
    message = BookingMessage.objects.create(booking=booking, sender=sender, body=body.strip())
    student_user = booking.student.user
    recipient = booking.tutor_user if sender == student_user else student_user
    name = sender.get_full_name() or sender.email
    push(recipient, 'message', f'New message from {name}', body.strip()[:120], reverse('booking_detail', args=[booking.pk]) + '#messages')
    return message


def send_due_reminders(hours=24):
    """Notify about confirmed sessions starting within `hours`. Returns the number sent."""
    now = timezone.localtime()
    horizon = now + timedelta(hours=hours)
    due = (Booking.objects.filter(status=Booking.CONFIRMED, reminder_sent=False,
                                  slot__date__gte=now.date(), slot__date__lte=horizon.date())
           .select_related('slot__tutor__user', 'slot__room', 'student__user'))
    sent = 0
    for booking in due:
        start = slot_start(booking.slot)
        if now < start <= horizon:
            notify_booking(booking, 'reminder')
            booking.reminder_sent = True
            booking.save(update_fields=['reminder_sent'])
            sent += 1
    return sent
