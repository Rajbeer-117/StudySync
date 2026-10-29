"""StudySync views: discovery, booking, messaging, reviews, favorites and tutor tools."""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from itertools import chain

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Avg, Count, F, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import services
from .forms import (AccountNameForm, BookingNotesForm, EmailLoginForm, MessageForm, RegistrationForm,
                    ReviewForm, SearchForm, SlotCreateForm, StudentProfileForm, TutorProfileForm)
from .models import (AvailabilitySlot, Booking, Favorite, Notification, Review, Room, Student, Tutor)
from .security import clear_login_failures, login_locked, record_login_failure
from .services import BookingError

RECENT_KEY = 'recently_viewed'
PENDING_KEY = 'pending_booking'
SEARCH_COOKIE = 'study_filters'
PAGE_SIZE = 12


# --------------------------------------------------------------------------- helpers
def _student_for(user):
    return Student.objects.filter(user=user).first() if user.is_authenticated else None


def _tutor_for(user):
    return Tutor.objects.filter(user=user).first() if user.is_authenticated else None


def _rated(queryset):
    return queryset.annotate(avg_rating=Avg('reviews__rating'), review_count=Count('reviews', distinct=True))


def _favorite_ids(student):
    if not student:
        return set(), set()
    favs = Favorite.objects.filter(student=student)
    return (set(favs.exclude(tutor=None).values_list('tutor_id', flat=True)),
            set(favs.exclude(room=None).values_list('room_id', flat=True)))


def _safe_next(value, default):
    if value and value.startswith('/') and not value.startswith('//'):
        return value
    return default


def _remember_view(request, kind, pk):
    key = f'{kind}:{pk}'
    recent = request.session.get(RECENT_KEY, [])
    request.session[RECENT_KEY] = ([key] + [item for item in recent if item != key])[:5]
    request.session.modified = True


def _recent_items(request):
    entries = []
    for item in request.session.get(RECENT_KEY, []):
        try:
            kind, id_text = item.split(':', 1)
            pk = int(id_text)
        except (ValueError, AttributeError):
            continue
        if kind == 't':
            obj = Tutor.objects.filter(pk=pk, is_active=True).first()
            if obj:
                entries.append({'name': obj.display_name, 'label': 'Tutor', 'url': reverse('tutor_detail', args=[obj.pk])})
        elif kind == 'r':
            obj = Room.objects.filter(pk=pk, is_active=True).first()
            if obj:
                entries.append({'name': obj.name, 'label': 'Room', 'url': reverse('room_detail', args=[obj.pk])})
    return entries


# --------------------------------------------------------------------------- discovery
def home(request):
    open_now = list(services.available_slots()[:6])
    top_tutors = _rated(Tutor.objects.filter(is_active=True)).order_by(F('avg_rating').desc(nulls_last=True), 'display_name')[:3]
    student = _student_for(request.user)
    fav_tutors, fav_rooms = _favorite_ids(student)
    return render(request, 'core/home.html', {
        'tutor_count': Tutor.objects.filter(is_active=True).count(),
        'room_count': Room.objects.filter(is_active=True).count(),
        'review_total': Review.objects.count(),
        'featured_tutors': top_tutors,
        'featured_rooms': Room.objects.filter(is_active=True)[:3],
        'open_now': open_now,
        'search_form': SearchForm(),
        'fav_tutors': fav_tutors, 'fav_rooms': fav_rooms,
    })


def catalog(request):
    initial = {}
    if not request.GET:
        try:
            remembered = json.loads(request.COOKIES.get(SEARCH_COOKIE, '{}'))
            if isinstance(remembered, dict):
                initial = {k: str(v) for k, v in remembered.items() if k in SearchForm.base_fields}
        except (ValueError, TypeError):
            pass
    form = SearchForm(request.GET or initial)
    if not form.is_valid() and not request.GET:
        form = SearchForm()  # stale cookie value no longer a valid option: start fresh

    tutors = _rated(Tutor.objects.filter(is_active=True))
    rooms = Room.objects.filter(is_active=True)
    data = form.cleaned_data if form.is_valid() else {}
    kind = data.get('kind') or ''

    if data.get('q'):
        q = data['q']
        tutors = tutors.filter(Q(display_name__icontains=q) | Q(subjects__icontains=q) | Q(bio__icontains=q))
        rooms = rooms.filter(Q(name__icontains=q) | Q(building__icontains=q) | Q(amenities__icontains=q))
    if data.get('subject'):
        tutors = tutors.filter(subjects__icontains=data['subject'])
        rooms = rooms.none()  # subjects apply to tutoring, not spaces
    if data.get('location'):
        tutors = tutors.filter(location__iexact=data['location'])
        rooms = rooms.filter(building__iexact=data['location'])
    if data.get('capacity'):
        rooms = rooms.filter(capacity__gte=int(data['capacity']))
        tutors = tutors.none()

    if data.get('date') or data.get('time') or data.get('when'):
        slots = services.available_slots()
        today = timezone.localdate()
        if data.get('date'):
            slots = slots.filter(date=data['date'])
        elif data.get('when') == 'today':
            slots = slots.filter(date=today)
        elif data.get('when') == 'week':
            slots = slots.filter(date__lte=today + timedelta(days=7))
        if data.get('time'):
            slots = slots.filter(start_time__lte=data['time'], end_time__gt=data['time'])
        tutors = tutors.filter(pk__in=slots.exclude(tutor=None).values('tutor_id'))
        rooms = rooms.filter(pk__in=slots.exclude(room=None).values('room_id'))

    if kind == 'tutor':
        rooms = rooms.none()
    elif kind == 'room':
        tutors = tutors.none()

    sort = data.get('sort', '')
    if sort == 'rating':
        tutors = tutors.order_by(F('avg_rating').desc(nulls_last=True), 'display_name')
    elif sort == 'name':
        tutors, rooms = tutors.order_by('display_name'), rooms.order_by('name')
    else:
        tutors, rooms = tutors.order_by('display_name'), rooms.order_by('name')

    page = Paginator(list(chain(tutors, rooms)), PAGE_SIZE).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    fav_tutors, fav_rooms = _favorite_ids(_student_for(request.user))
    response = render(request, 'core/catalog.html', {
        'form': form, 'page': page, 'result_count': page.paginator.count, 'kind': kind,
        'querystring': params.urlencode(), 'recent_items': _recent_items(request),
        'fav_tutors': fav_tutors, 'fav_rooms': fav_rooms,
    })
    if request.GET and form.is_valid():
        saved = {name: request.GET.get(name, '') for name in SearchForm.base_fields}
        response.set_cookie(SEARCH_COOKIE, json.dumps(saved), max_age=30 * 86400, samesite='Lax', httponly=True,
                            secure=request.is_secure())
    return response


def tutor_detail(request, pk):
    tutor = get_object_or_404(Tutor, pk=pk, is_active=True)
    _remember_view(request, 't', pk)
    slots = list(services.available_slots(AvailabilitySlot.objects.filter(tutor=tutor))[:60])
    student = _student_for(request.user)
    reviews = tutor.reviews.select_related('student__user')
    my_review = reviews.filter(student=student).first() if student else None
    can_review = bool(student) and _has_completed_session(student, tutor)
    fav_tutors, _ = _favorite_ids(student)
    summary = tutor.rating_summary
    counts = Counter(reviews.values_list('rating', flat=True))
    breakdown = [{'stars': s, 'count': counts.get(s, 0),
                  'pct': round(100 * counts.get(s, 0) / summary['count']) if summary['count'] else 0}
                 for s in range(5, 0, -1)]
    return render(request, 'core/detail.html', {
        'resource': tutor, 'resource_kind': 'tutor', 'slots': slots, 'reviews': reviews[:30],
        'my_review': my_review, 'can_review': can_review, 'summary': summary, 'breakdown': breakdown,
        'review_form': ReviewForm(instance=my_review) if can_review else None,
        'is_favorite': tutor.pk in fav_tutors, 'is_student': bool(student),
    })


def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk, is_active=True)
    _remember_view(request, 'r', pk)
    slots = list(services.available_slots(AvailabilitySlot.objects.filter(room=room))[:60])
    _, fav_rooms = _favorite_ids(_student_for(request.user))
    return render(request, 'core/detail.html', {
        'resource': room, 'resource_kind': 'room', 'slots': slots,
        'is_favorite': room.pk in fav_rooms, 'is_student': request.user.is_authenticated and bool(_student_for(request.user)),
    })


# --------------------------------------------------------------------------- favorites & reviews
@login_required
@require_POST
def toggle_favorite(request, kind, pk):
    student = _student_for(request.user)
    if student is None:
        messages.info(request, 'Saving favorites is available to student accounts.')
        return redirect(_safe_next(request.POST.get('next'), 'catalog'))
    if kind == 'tutor':
        lookup = {'tutor': get_object_or_404(Tutor, pk=pk, is_active=True)}
    elif kind == 'room':
        lookup = {'room': get_object_or_404(Room, pk=pk, is_active=True)}
    else:
        raise Http404
    existing = Favorite.objects.filter(student=student, **lookup)
    if existing.exists():
        existing.delete()
        messages.success(request, 'Removed from your saved list.')
    else:
        Favorite.objects.create(student=student, **lookup)
        messages.success(request, 'Saved to your favorites.')
    return redirect(_safe_next(request.POST.get('next'), reverse('favorites')))


@login_required
def favorites(request):
    student = _student_for(request.user)
    if not student:
        messages.info(request, 'Favorites are available to student accounts.')
        return redirect('dashboard')
    fav_tutors, fav_rooms = _favorite_ids(student)
    tutors = _rated(Tutor.objects.filter(pk__in=fav_tutors, is_active=True))
    rooms = Room.objects.filter(pk__in=fav_rooms, is_active=True)
    return render(request, 'core/favorites.html', {
        'tutors': tutors, 'rooms': rooms, 'fav_tutors': fav_tutors, 'fav_rooms': fav_rooms,
        'has_any': tutors.exists() or rooms.exists()})


def _has_completed_session(student, tutor):
    now = timezone.localtime()
    return Booking.objects.filter(student=student, status=Booking.CONFIRMED, slot__tutor=tutor).filter(
        Q(slot__date__lt=now.date()) | Q(slot__date=now.date(), slot__end_time__lte=now.time())).exists()


@login_required
@require_POST
def submit_review(request, pk):
    student = _student_for(request.user)
    tutor = get_object_or_404(Tutor, pk=pk, is_active=True)
    if not student or not _has_completed_session(student, tutor):
        messages.error(request, 'You can review a tutor after a completed session with them.')
        return redirect('tutor_detail', pk=pk)
    form = ReviewForm(request.POST, instance=Review.objects.filter(student=student, tutor=tutor).first())
    if form.is_valid():
        review = form.save(commit=False)
        review.student, review.tutor = student, tutor
        review.save()
        services.push(tutor.user, 'review', f'New {review.rating}★ review from {request.user.first_name or "a student"}',
                      review.comment[:120], reverse('tutor_detail', args=[tutor.pk]) + '#reviews')
        messages.success(request, 'Thanks! Your review is published.')
    else:
        messages.error(request, 'Please choose a rating from 1 to 5.')
    return redirect(reverse('tutor_detail', args=[pk]) + '#reviews')


@login_required
@require_POST
def delete_review(request, pk):
    student = _student_for(request.user)
    review = get_object_or_404(Review, pk=pk, student=student) if student else None
    if review is None:
        raise Http404
    tutor_id = review.tutor_id
    review.delete()
    messages.success(request, 'Your review was removed.')
    return redirect('tutor_detail', pk=tutor_id)


# --------------------------------------------------------------------------- accounts
class StudyLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '')
        if login_locked(request, username):
            form = self.get_form()
            form.add_error(None, 'Too many failed attempts. Please wait 15 minutes or reset your password.')
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        clear_login_failures(self.request, self.request.POST.get('username', ''))
        response = super().form_valid(form)
        self.request.session.set_expiry(14 * 86400 if form.cleaned_data.get('remember_me') else 0)
        return response

    def form_invalid(self, form):
        record_login_failure(self.request, self.request.POST.get('username', ''))
        return super().form_invalid(form)


class StudyPasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, 'Password updated.')
        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        messages.success(request, 'Welcome to StudySync! Your account is ready.')
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile(request):
    student = _student_for(request.user)
    tutor = _tutor_for(request.user)
    name_form = AccountNameForm(request.POST or None, instance=request.user, prefix='name')
    extra_form = None
    if student:
        extra_form = StudentProfileForm(request.POST or None, request.FILES or None, instance=student, prefix='extra')
    elif tutor:
        extra_form = TutorProfileForm(request.POST or None, request.FILES or None, instance=tutor, prefix='extra')
    if request.method == 'POST' and name_form.is_valid() and (extra_form is None or extra_form.is_valid()):
        with transaction.atomic():
            name_form.save()
            if extra_form:
                extra_form.save()
        messages.success(request, 'Your profile has been saved.')
        return redirect('profile')
    return render(request, 'core/profile.html', {
        'name_form': name_form, 'extra_form': extra_form, 'student': student, 'tutor': tutor})


# --------------------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    student = _student_for(request.user)
    tutor = _tutor_for(request.user)
    ctx = {'student': student, 'tutor': tutor}
    today = timezone.localdate()
    now = timezone.localtime()
    if student:
        mine = Booking.objects.filter(student=student).select_related('slot__tutor', 'slot__room')
        active = mine.filter(status__in=Booking.ACTIVE)
        upcoming = (active.filter(Q(slot__date__gt=today) | Q(slot__date=today, slot__end_time__gt=now.time()))
                    .order_by('slot__date', 'slot__start_time'))
        confirmed_next = upcoming.filter(status=Booking.CONFIRMED).first()
        reviewed = set(Review.objects.filter(student=student).values_list('tutor_id', flat=True))
        to_review, seen = [], set()
        past = (mine.filter(status=Booking.CONFIRMED, slot__tutor__isnull=False)
                .filter(Q(slot__date__lt=today) | Q(slot__date=today, slot__end_time__lte=now.time()))
                .order_by('-slot__date'))
        for b in past:
            if b.slot.tutor_id not in reviewed and b.slot.tutor_id not in seen:
                seen.add(b.slot.tutor_id)
                to_review.append(b.slot.tutor)
        minutes = sum((datetime.combine(b.slot.date, b.slot.end_time) - datetime.combine(b.slot.date, b.slot.start_time)).seconds // 60
                      for b in past)
        fav_qs = Favorite.objects.filter(student=student).select_related('tutor', 'room')
        ctx.update({
            'upcoming': list(upcoming[:4]), 'next_booking': confirmed_next or upcoming.first(),
            'booking_count': mine.filter(status=Booking.CONFIRMED).count(),
            'pending_count': mine.filter(status=Booking.PENDING).count(),
            'hours_studied': round(minutes / 60, 1),
            'favorite_count': fav_qs.count(), 'favorites_preview': fav_qs[:3],
            'to_review': to_review[:3],
        })
    elif tutor:
        base = Booking.objects.filter(slot__tutor=tutor).select_related('slot', 'student__user')
        pending = base.filter(status=Booking.PENDING).order_by('slot__date', 'slot__start_time')
        confirmed = base.filter(status=Booking.CONFIRMED).filter(
            Q(slot__date__gt=today) | Q(slot__date=today, slot__end_time__gt=now.time()))
        open_slots = services.available_slots(AvailabilitySlot.objects.filter(tutor=tutor)).count()
        # sessions per week: last 5 weeks and the next 2
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=5)
        end = monday + timedelta(weeks=3)
        week_counts = Counter(
            (b.slot.date - timedelta(days=b.slot.date.weekday())) for b in
            base.filter(status=Booking.CONFIRMED, slot__date__gte=start, slot__date__lt=end))
        weeks = [start + timedelta(weeks=i) for i in range(8)]
        peak = max([week_counts.get(w, 0) for w in weeks] + [1])
        chart = [{'label': w.strftime('%b %d'), 'count': week_counts.get(w, 0),
                  'pct': round(100 * week_counts.get(w, 0) / peak), 'current': w == monday} for w in weeks]
        ctx.update({
            'open_slot_count': open_slots, 'upcoming_session_count': confirmed.count(),
            'rating': tutor.rating_summary, 'pending_requests': list(pending[:5]), 'pending_total': pending.count(),
            'tutor_upcoming': list(confirmed.order_by('slot__date', 'slot__start_time')[:4]),
            'chart': chart, 'completed_total': base.filter(status=Booking.CONFIRMED).filter(
                Q(slot__date__lt=today) | Q(slot__date=today, slot__end_time__lte=now.time())).count(),
        })
    return render(request, 'core/dashboard.html', ctx)


# --------------------------------------------------------------------------- booking flow
@login_required
def start_booking(request, slot_id):
    student = _student_for(request.user)
    if student is None:
        messages.error(request, 'Only student accounts can book. You can still browse tutors and rooms.')
        return redirect('catalog')
    slot = get_object_or_404(AvailabilitySlot.objects.select_related('tutor', 'room'), pk=slot_id)
    if not services.slot_available(slot):
        messages.warning(request, 'That time is no longer available. Please choose another slot.')
        return redirect('tutor_detail', pk=slot.tutor_id) if slot.tutor_id else redirect('room_detail', pk=slot.room_id)
    if services.student_clash(student, slot):
        messages.warning(request, 'You already have a booking that overlaps this time.')
        return redirect('my_bookings')
    form = BookingNotesForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session[PENDING_KEY] = {'slot_id': slot.pk, 'notes': form.cleaned_data['notes'],
                                        'created_at': timezone.now().isoformat()}
        return redirect('booking_review')
    return render(request, 'core/start_booking.html', {'slot': slot, 'form': form})


@login_required
def booking_review(request):
    student = _student_for(request.user)
    if not student:
        messages.error(request, 'Only students can confirm bookings.')
        return redirect('catalog')
    pending = request.session.get(PENDING_KEY)
    if not pending:
        messages.info(request, 'Choose a tutor or room time slot to start a booking.')
        return redirect('catalog')
    try:
        created = datetime.fromisoformat(pending['created_at'])
        if timezone.is_naive(created):
            raise ValueError('Invalid booking session')
        if timezone.now() - created > timedelta(minutes=15):
            raise ValueError('Booking hold expired')
        slot_id = int(pending['slot_id'])
    except (ValueError, TypeError, KeyError):
        request.session.pop(PENDING_KEY, None)
        messages.warning(request, 'Your 15-minute booking preview expired. Please select a slot again.')
        return redirect('catalog')
    slot = get_object_or_404(AvailabilitySlot.objects.select_related('tutor', 'room'), pk=slot_id)
    if request.method == 'POST':
        try:
            booking = services.create_booking(student, slot_id, pending.get('notes', ''))
        except BookingError as exc:
            request.session.pop(PENDING_KEY, None)
            messages.error(request, str(exc))
            return redirect('my_bookings' if 'overlaps' in str(exc) else 'catalog')
        request.session.pop(PENDING_KEY, None)
        booking = Booking.objects.select_related('slot__tutor__user', 'slot__room', 'student__user').get(pk=booking.pk)
        if booking.status == Booking.PENDING:
            services.notify_booking(booking, 'requested', request.user)
            messages.success(request, 'Request sent! You will be notified when the tutor responds.')
        else:
            services.notify_booking(booking, 'confirmed', request.user)
            messages.success(request, f'Booking #{booking.pk} confirmed!')
        return redirect('booking_detail', pk=booking.pk)
    if not services.slot_available(slot):
        request.session.pop(PENDING_KEY, None)
        messages.warning(request, 'This slot is no longer available.')
        return redirect('catalog')
    return render(request, 'core/booking_review.html', {
        'slot': slot, 'notes': pending.get('notes', ''), 'needs_approval': bool(slot.tutor_id and slot.tutor.requires_approval)})


def _booking_for(request, pk):
    """Return (booking, role) for the student who owns it or the tutor whose slot it is."""
    booking = get_object_or_404(
        Booking.objects.select_related('slot__tutor__user', 'slot__room', 'student__user'), pk=pk)
    if booking.student.user_id == request.user.id:
        return booking, 'student'
    if booking.tutor_user is not None and booking.tutor_user.id == request.user.id:
        return booking, 'tutor'
    raise Http404


@login_required
def my_bookings(request):
    student = _student_for(request.user)
    if not student:
        messages.info(request, 'Booking management is available to student accounts.')
        return redirect('dashboard')
    bookings = list(Booking.objects.filter(student=student).select_related('slot__tutor', 'slot__room'))
    upcoming = sorted((b for b in bookings if b.is_active and not b.slot.is_past),
                      key=lambda b: (b.slot.date, b.slot.start_time))
    history = [b for b in bookings if b not in upcoming]
    return render(request, 'core/my_bookings.html', {'upcoming': upcoming, 'history': history})


@login_required
def booking_detail(request, pk):
    booking, role = _booking_for(request, pk)
    Notification.objects.filter(user=request.user, is_read=False, url__startswith=request.path).update(is_read=True)
    can_reschedule = role == 'student' and booking.is_active and not booking.slot.is_past
    closed = booking.status in (Booking.CANCELLED, Booking.DECLINED)
    timeline = [{'label': 'Booked', 'state': 'done', 'note': booking.created_at}]
    if closed:
        timeline.append({'label': booking.get_status_display(), 'state': 'stop', 'note': booking.cancelled_at})
    else:
        timeline.append({'label': 'Confirmed' if booking.status == Booking.CONFIRMED else 'Awaiting approval',
                         'state': 'done' if booking.status == Booking.CONFIRMED else 'current', 'note': None})
        timeline.append({'label': 'Session', 'state': 'done' if booking.is_completed else 'todo', 'note': None})
    return render(request, 'core/booking_detail.html', {
        'booking': booking, 'role': role, 'slot': booking.slot, 'timeline': timeline,
        'messages_list': booking.messages.select_related('sender'),
        'message_form': MessageForm(), 'can_reschedule': can_reschedule,
        'can_cancel': booking.is_active and not booking.slot.is_past,
        'can_message': booking.tutor_user is not None and booking.status in Booking.ACTIVE,
        'can_review': role == 'student' and booking.is_completed and bool(booking.slot.tutor_id),
        'other_party': (booking.tutor_user or booking.slot.resource) if role == 'student' else booking.student.user,
    })


@login_required
@require_POST
def booking_message(request, pk):
    booking, _ = _booking_for(request, pk)
    form = MessageForm(request.POST)
    if booking.status in (Booking.CANCELLED, Booking.DECLINED):
        messages.warning(request, 'This booking is closed, so messaging is off.')
    elif form.is_valid():
        if booking.tutor_user is None and request.user == booking.student.user:
            messages.info(request, 'Room bookings have no tutor to message.')
        else:
            services.add_message(booking, request.user, form.cleaned_data['body'])
    else:
        messages.error(request, 'Write a message (up to 1000 characters).')
    return redirect(reverse('booking_detail', args=[pk]) + '#messages')


@login_required
def reschedule(request, pk):
    booking, role = _booking_for(request, pk)
    if role != 'student':
        raise Http404
    if not booking.is_active or booking.slot.is_past:
        messages.warning(request, 'This booking can no longer be rescheduled.')
        return redirect('booking_detail', pk=pk)
    if request.method == 'POST':
        try:
            booking, old_slot = services.reschedule_booking(booking, request.POST.get('slot_id'))
        except (BookingError, ValueError, TypeError) as exc:
            messages.error(request, str(exc) if isinstance(exc, BookingError) else 'Choose a time from the list.')
            return redirect('reschedule', pk=pk)
        booking.refresh_from_db()
        services.notify_booking(booking, 'rescheduled', request.user)
        messages.success(request, 'Booking moved to your new time.')
        return redirect('booking_detail', pk=pk)
    candidates = services.available_slots(AvailabilitySlot.objects.filter(
        tutor=booking.slot.tutor, room=booking.slot.room).exclude(pk=booking.slot_id))[:60]
    return render(request, 'core/reschedule.html', {'booking': booking, 'slots': list(candidates)})


@login_required
@require_POST
def cancel_booking(request, pk):
    student = _student_for(request.user)
    if student is None:
        return HttpResponseForbidden('Student account required.')
    booking = get_object_or_404(Booking.objects.select_related('slot__tutor__user', 'slot__room', 'student__user'),
                                pk=pk, student=student)
    if booking.is_active and not booking.slot.is_past:
        services.set_status(booking, Booking.CANCELLED)
        services.notify_booking(booking, 'cancelled', request.user)
        messages.success(request, 'Your booking has been cancelled and the slot is open again.')
    else:
        messages.warning(request, 'This booking cannot be cancelled.')
    return redirect(_safe_next(request.POST.get('next'), reverse('my_bookings')))


@login_required
def booking_ics(request, pk):
    """Download a confirmed booking as an .ics calendar file."""
    student = _student_for(request.user)
    booking = get_object_or_404(Booking, pk=pk, student=student, status=Booking.CONFIRMED) if student else None
    if booking is None:
        raise Http404
    slot = booking.slot
    fmt = '%Y%m%dT%H%M%SZ'
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(slot.date, slot.start_time), tz).astimezone(dt_timezone.utc)
    end = timezone.make_aware(datetime.combine(slot.date, slot.end_time), tz).astimezone(dt_timezone.utc)
    place = slot.tutor.location if slot.tutor_id else slot.room.building
    esc = lambda text: str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//StudySync//EN', 'BEGIN:VEVENT',
             f'UID:booking-{booking.pk}@studysync', f'DTSTAMP:{timezone.now().astimezone(dt_timezone.utc).strftime(fmt)}',
             f'DTSTART:{start.strftime(fmt)}', f'DTEND:{end.strftime(fmt)}',
             f'SUMMARY:{esc("StudySync: " + str(slot.resource))}', f'LOCATION:{esc(place)}',
             'BEGIN:VALARM', 'TRIGGER:-PT30M', 'ACTION:DISPLAY', 'DESCRIPTION:StudySync session soon', 'END:VALARM',
             'END:VEVENT', 'END:VCALENDAR']
    response = HttpResponse('\r\n'.join(lines) + '\r\n', content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="studysync-booking-{booking.pk}.ics"'
    return response


# --------------------------------------------------------------------------- tutor tools
@login_required
def manage_slots(request):
    """Tutor-only: publish availability and manage the sessions booked on it."""
    tutor = _tutor_for(request.user)
    if tutor is None:
        messages.info(request, 'Availability management is for tutor accounts.')
        return redirect('dashboard')
    form = SlotCreateForm(request.POST or None, tutor=tutor)
    if request.method == 'POST' and form.is_valid():
        created = form.save()
        messages.success(request, f'Added {len(created)} availability slot{"s" if len(created) != 1 else ""}.')
        return redirect('manage_slots')
    today = timezone.localdate()
    slots = list(AvailabilitySlot.objects.filter(tutor=tutor, is_active=True, date__gte=today).order_by('date', 'start_time'))
    held = {b.slot_id: b for b in Booking.objects.filter(
        slot__in=slots, status__in=Booking.ACTIVE).select_related('student__user')}
    for slot in slots:
        slot.booking = held.get(slot.pk)
    return render(request, 'core/manage_slots.html', {'form': form, 'slots': slots, 'tutor': tutor})


@login_required
@require_POST
def delete_slot(request, pk):
    tutor = _tutor_for(request.user)
    slot = get_object_or_404(AvailabilitySlot, pk=pk, tutor=tutor) if tutor else None
    if slot is None:
        raise Http404
    if slot.bookings.filter(status__in=Booking.ACTIVE).exists():
        messages.warning(request, 'That slot is booked. Cancel or decline the session first if you need to remove it.')
    elif slot.bookings.exists():
        slot.is_active = False  # keep history for past bookings
        slot.save(update_fields=['is_active'])
        messages.success(request, 'Slot removed.')
    else:
        slot.delete()
        messages.success(request, 'Slot removed.')
    return redirect('manage_slots')


@login_required
@require_POST
def tutor_cancel_booking(request, pk):
    tutor = _tutor_for(request.user)
    booking = get_object_or_404(Booking.objects.select_related('slot__tutor__user', 'slot__room', 'student__user'),
                                pk=pk, slot__tutor=tutor) if tutor else None
    if booking is None:
        raise Http404
    if booking.is_active and not booking.slot.is_past:
        services.set_status(booking, Booking.CANCELLED)
        services.notify_booking(booking, 'cancelled', request.user)
        messages.success(request, 'Session cancelled and the student was notified.')
    return redirect(_safe_next(request.POST.get('next'), reverse('manage_slots')))


@login_required
@require_POST
def tutor_decide_booking(request, pk):
    """Approve or decline a pending booking request."""
    tutor = _tutor_for(request.user)
    booking = get_object_or_404(Booking.objects.select_related('slot__tutor__user', 'slot__room', 'student__user'),
                                pk=pk, slot__tutor=tutor) if tutor else None
    if booking is None:
        raise Http404
    decision = request.POST.get('decision')
    if booking.status != Booking.PENDING or booking.slot.is_past:
        messages.warning(request, 'That request is no longer pending.')
    elif decision == 'approve':
        services.set_status(booking, Booking.CONFIRMED)
        services.notify_booking(booking, 'approved', request.user)
        messages.success(request, 'Request approved. The student has been notified.')
    elif decision == 'decline':
        services.set_status(booking, Booking.DECLINED)
        services.notify_booking(booking, 'declined', request.user)
        messages.success(request, 'Request declined.')
    return redirect(_safe_next(request.POST.get('next'), reverse('dashboard')))


# --------------------------------------------------------------------------- notifications
@login_required
def notifications(request):
    page = Paginator(Notification.objects.filter(user=request.user), 25).get_page(request.GET.get('page'))
    return render(request, 'core/notifications.html', {'page': page})


@login_required
def notification_go(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=['is_read'])
    return redirect(_safe_next(note.url, reverse('notifications')))


@login_required
@require_POST
def notifications_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')


# --------------------------------------------------------------------------- JSON & ops endpoints
@require_GET
def api_search(request):
    """Instant search for the command palette (Ctrl/⌘ + K)."""
    q = request.GET.get('q', '').strip()[:60]
    if len(q) < 2:
        return JsonResponse({'results': []})
    results = []
    for t in _rated(Tutor.objects.filter(is_active=True)).filter(
            Q(display_name__icontains=q) | Q(subjects__icontains=q))[:5]:
        results.append({'type': 'Tutor', 'title': t.display_name, 'subtitle': t.subjects,
                        'rating': round(t.avg_rating, 1) if t.avg_rating else None,
                        'url': reverse('tutor_detail', args=[t.pk])})
    for r in Room.objects.filter(is_active=True).filter(Q(name__icontains=q) | Q(building__icontains=q))[:4]:
        results.append({'type': 'Room', 'title': r.name, 'subtitle': f'{r.building} · up to {r.capacity}',
                        'rating': None, 'url': reverse('room_detail', args=[r.pk])})
    return JsonResponse({'results': results})


@require_GET
def healthz(request):
    """Liveness/readiness probe for load balancers and orchestrators."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except Exception:  # noqa: BLE001 - report any database failure as unhealthy
        return JsonResponse({'status': 'unavailable'}, status=503)


@require_GET
def robots_txt(request):
    body = 'User-agent: *\nDisallow: /admin/\nDisallow: /accounts/\nDisallow: /dashboard/\nDisallow: /my-bookings/\nDisallow: /api/\n'
    return HttpResponse(body, content_type='text/plain')
