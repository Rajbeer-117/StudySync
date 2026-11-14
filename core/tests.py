from datetime import time, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from . import services
from django.core.cache import cache
from .models import AvailabilitySlot, Booking, Favorite, Notification, Review, Room, Student, Tutor, WaitlistEntry

User = get_user_model()


class StudySyncFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='learner@example.test', email='learner@example.test', password='GoodPassword123!')
        cls.student = Student.objects.create(user=cls.user)
        cls.other_user = User.objects.create_user(username='other@example.test', email='other@example.test', password='GoodPassword123!')
        cls.other_student = Student.objects.create(user=cls.other_user)
        cls.tutor = Tutor.objects.create(display_name='Test Tutor', subjects='Mathematics', location='Leddy Library')
        cls.room = Room.objects.create(name='Room Test', building='Leddy Library')
        cls.slot = AvailabilitySlot.objects.create(room=cls.room, date=timezone.localdate() + timedelta(days=2), start_time=time(14), end_time=time(15))
        cls.other_slot = AvailabilitySlot.objects.create(room=cls.room, date=timezone.localdate() + timedelta(days=2), start_time=time(14, 30), end_time=time(15, 30))

    def test_guest_browsing_is_open_but_booking_requires_login(self):
        self.assertEqual(self.client.get(reverse('catalog')).status_code, 200)
        self.assertEqual(self.client.get(reverse('room_detail', args=[self.room.pk])).status_code, 200)
        resp = self.client.get(reverse('start_booking', args=[self.slot.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_student_can_book_and_see_confirmation(self):
        self.client.force_login(self.user)
        begin = self.client.post(reverse('start_booking', args=[self.slot.pk]), {'notes': 'Practice derivatives'})
        self.assertRedirects(begin, reverse('booking_review'))
        self.assertEqual(self.client.get(reverse('booking_review')).status_code, 200)
        confirm = self.client.post(reverse('booking_review'))
        booking = Booking.objects.get(student=self.student)
        self.assertRedirects(confirm, reverse('booking_detail', args=[booking.pk]))
        self.assertEqual(booking.notes, 'Practice derivatives')
        self.assertEqual(booking.status, Booking.CONFIRMED)

    def test_overlapping_room_slot_cannot_be_double_booked(self):
        Booking.objects.create(student=self.other_student, slot=self.slot)
        self.client.force_login(self.user)
        response = self.client.get(reverse('start_booking', args=[self.other_slot.pk]))
        self.assertRedirects(response, reverse('room_detail', args=[self.room.pk]))
        self.assertEqual(Booking.objects.count(), 1)

    def test_can_cancel_and_free_slot(self):
        booking = Booking.objects.create(student=self.student, slot=self.slot)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(reverse('cancel_booking', args=[booking.pk])), reverse('my_bookings'))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.CANCELLED)
        self.assertTrue(self.client.get(reverse('start_booking', args=[self.slot.pk])).status_code == 200)

    def test_other_student_cannot_cancel_booking(self):
        booking = Booking.objects.create(student=self.other_student, slot=self.slot)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('cancel_booking', args=[booking.pk])).status_code, 404)

    def test_search_filters_saved_cookie(self):
        AvailabilitySlot.objects.create(tutor=self.tutor, date=timezone.localdate() + timedelta(days=2), start_time=time(9), end_time=time(10))
        response = self.client.get(reverse('catalog'), {'kind': 'tutor', 'subject': 'Mathematics'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Tutor')

    def test_tutor_registration(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'Test Mentor', 'email': 'mentor@example.test', 'role': 'tutor',
            'password1': 'DifferentPassword123!', 'password2': 'DifferentPassword123!',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(Tutor.objects.filter(user__email='mentor@example.test').exists())
        self.assertFalse(Student.objects.filter(user__email='mentor@example.test').exists())

    def test_login_using_email(self):
        response = self.client.post(reverse('login'), {'username': 'learner@example.test', 'password': 'GoodPassword123!'})
        self.assertRedirects(response, reverse('dashboard'))

    def test_filter_dropdown_choices_come_from_available_data(self):
        """Subject/date/time/location are real select lists, not text-only mockups."""
        from .forms import SearchForm
        form = SearchForm()
        for name in ('kind', 'subject', 'date', 'time', 'location'):
            self.assertEqual(form.fields[name].widget.__class__.__name__, 'Select')
        day = self.slot.date.isoformat()
        self.assertIn(day, [value for value, label in form.fields['date'].choices])
        self.assertIn('14:00', [value for value, label in form.fields['time'].choices])
        self.assertIn('Leddy Library', [value for value, label in form.fields['location'].choices])

    def test_search_dropdowns_filter_real_availability(self):
        day = self.slot.date.isoformat()
        response = self.client.get(reverse('catalog'), {
            'kind': 'room', 'date': day, 'time': '14:00', 'location': 'Leddy Library'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Room Test')
        self.assertNotContains(response, 'Test Tutor')
        self.assertContains(response, '<select', html=False)


class Phase2FeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='s@example.test', email='s@example.test', password='GoodPassword123!', first_name='Sam')
        cls.student = Student.objects.create(user=cls.user)
        cls.tutor_user = User.objects.create_user(username='t@example.test', email='t@example.test', password='GoodPassword123!', first_name='Tia')
        cls.tutor = Tutor.objects.create(user=cls.tutor_user, display_name='Tia Tutor', subjects='Math, Physics', location='Erie Hall')
        cls.other_tutor = Tutor.objects.create(display_name='Other Tutor', subjects='Writing', location='Leddy Library')
        today = timezone.localdate()
        cls.future = AvailabilitySlot.objects.create(tutor=cls.tutor, date=today + timedelta(days=3), start_time=time(10), end_time=time(11))
        cls.past = AvailabilitySlot.objects.create(tutor=cls.tutor, date=today - timedelta(days=2), start_time=time(10), end_time=time(11))

    # ---- password reset ----
    def test_password_reset_sends_email_and_works(self):
        from django.core import mail
        resp = self.client.post(reverse('password_reset'), {'email': 's@example.test'})
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)
        link = [w for w in mail.outbox[0].body.split() if '/accounts/reset/' in w][0]
        path = link[link.index('/accounts/reset/'):]
        follow = self.client.get(path, follow=True)
        final = follow.redirect_chain[-1][0]
        done = self.client.post(final, {'new_password1': 'BrandNewPass987!', 'new_password2': 'BrandNewPass987!'})
        self.assertRedirects(done, reverse('password_reset_complete'))
        self.assertTrue(self.client.login(username='s@example.test', password='BrandNewPass987!'))

    def test_password_reset_unknown_email_does_not_leak(self):
        from django.core import mail
        resp = self.client.post(reverse('password_reset'), {'email': 'nobody@example.test'})
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    # ---- reviews ----
    def test_cannot_review_without_completed_session(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('submit_review', args=[self.tutor.pk]), {'rating': 5, 'comment': 'Great'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Review.objects.count(), 0)
        Booking.objects.create(student=self.student, slot=self.future)  # upcoming, not completed
        self.client.post(reverse('submit_review', args=[self.tutor.pk]), {'rating': 5})
        self.assertEqual(Review.objects.count(), 0)

    def test_review_after_completed_session_and_update_and_average(self):
        Booking.objects.create(student=self.student, slot=self.past)
        self.client.force_login(self.user)
        self.client.post(reverse('submit_review', args=[self.tutor.pk]), {'rating': 4, 'comment': 'Helpful'})
        self.assertEqual(Review.objects.get().rating, 4)
        self.client.post(reverse('submit_review', args=[self.tutor.pk]), {'rating': 5, 'comment': 'Even better'})
        self.assertEqual(Review.objects.count(), 1)  # edited, not duplicated
        self.assertEqual(self.tutor.rating_summary, {'avg': 5.0, 'count': 1})
        page = self.client.get(reverse('tutor_detail', args=[self.tutor.pk]))
        self.assertContains(page, 'Even better')
        self.client.post(reverse('delete_review', args=[Review.objects.get().pk]))
        self.assertEqual(Review.objects.count(), 0)

    def test_invalid_rating_rejected(self):
        Booking.objects.create(student=self.student, slot=self.past)
        self.client.force_login(self.user)
        self.client.post(reverse('submit_review', args=[self.tutor.pk]), {'rating': 9})
        self.assertEqual(Review.objects.count(), 0)

    def test_catalog_sort_by_rating(self):
        other_student = Student.objects.create(user=User.objects.create_user(username='x@example.test', email='x@example.test', password='GoodPassword123!'))
        Review.objects.create(student=self.student, tutor=self.other_tutor, rating=5)
        Review.objects.create(student=other_student, tutor=self.tutor, rating=2)
        html = self.client.get(reverse('catalog'), {'sort': 'rating'}).content.decode()
        self.assertLess(html.index('Other Tutor'), html.index('Tia Tutor'))

    # ---- favorites ----
    def test_favorite_toggle(self):
        self.client.force_login(self.user)
        url = reverse('toggle_favorite', args=['tutor', self.tutor.pk])
        self.client.post(url, {'next': '/explore/'})
        self.assertEqual(Favorite.objects.filter(student=self.student, tutor=self.tutor).count(), 1)
        self.assertContains(self.client.get(reverse('favorites')), 'Tia Tutor')
        self.client.post(url)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_favorite_open_redirect_blocked(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('toggle_favorite', args=['tutor', self.tutor.pk]), {'next': '//evil.example'})
        self.assertRedirects(resp, reverse('favorites'))

    def test_guest_cannot_favorite(self):
        resp = self.client.post(reverse('toggle_favorite', args=['tutor', self.tutor.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    # ---- emails & booking rules ----
    def test_booking_confirmation_and_cancellation_emails(self):
        from django.core import mail
        self.client.force_login(self.user)
        self.client.post(reverse('start_booking', args=[self.future.pk]), {'notes': 'Limits'})
        self.client.post(reverse('booking_review'))
        recipients = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(recipients, ['s@example.test', 't@example.test'])
        booking = Booking.objects.get()
        self.client.post(reverse('cancel_booking', args=[booking.pk]))
        self.assertEqual(len(mail.outbox), 4)
        self.assertIn('cancelled', mail.outbox[2].subject)

    def test_student_cannot_double_book_overlapping_times(self):
        Booking.objects.create(student=self.student, slot=self.future)
        clash = AvailabilitySlot.objects.create(tutor=self.other_tutor, date=self.future.date, start_time=time(10, 30), end_time=time(11, 30))
        self.client.force_login(self.user)
        resp = self.client.get(reverse('start_booking', args=[clash.pk]))
        self.assertRedirects(resp, reverse('my_bookings'))

    def test_calendar_download(self):
        booking = Booking.objects.create(student=self.student, slot=self.future)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('booking_ics', args=[booking.pk]))
        self.assertTrue(resp['Content-Type'].startswith('text/calendar'))
        body = resp.content.decode()
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn('SUMMARY:StudySync: Tia Tutor', body)
        other = User.objects.create_user(username='o@example.test', email='o@example.test', password='GoodPassword123!')
        Student.objects.create(user=other)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('booking_ics', args=[booking.pk])).status_code, 404)

    # ---- tutor tools ----
    def test_tutor_can_add_repeating_slots(self):
        self.client.force_login(self.tutor_user)
        day = timezone.localdate() + timedelta(days=10)
        resp = self.client.post(reverse('manage_slots'), {'date': day.isoformat(), 'start_time': '13:00', 'end_time': '14:00', 'repeat_weeks': 3})
        self.assertRedirects(resp, reverse('manage_slots'))
        self.assertEqual(AvailabilitySlot.objects.filter(tutor=self.tutor, start_time=time(13)).count(), 3)

    def test_tutor_slot_overlap_and_bad_times_rejected(self):
        self.client.force_login(self.tutor_user)
        day = self.future.date.isoformat()
        overlap = self.client.post(reverse('manage_slots'), {'date': day, 'start_time': '10:30', 'end_time': '11:30', 'repeat_weeks': 1})
        self.assertEqual(overlap.status_code, 200)
        self.assertContains(overlap, 'overlapping')
        backwards = self.client.post(reverse('manage_slots'), {'date': day, 'start_time': '15:00', 'end_time': '14:00', 'repeat_weeks': 1})
        self.assertContains(backwards, 'later than the start')
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        past = self.client.post(reverse('manage_slots'), {'date': yesterday, 'start_time': '10:00', 'end_time': '11:00', 'repeat_weeks': 1})
        self.assertContains(past, 'future date')

    def test_tutor_cannot_delete_booked_slot_but_can_cancel_session(self):
        from django.core import mail
        booking = Booking.objects.create(student=self.student, slot=self.future)
        self.client.force_login(self.tutor_user)
        self.client.post(reverse('delete_slot', args=[self.future.pk]))
        self.assertTrue(AvailabilitySlot.objects.filter(pk=self.future.pk, is_active=True).exists())
        self.client.post(reverse('tutor_cancel_booking', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.CANCELLED)
        self.assertEqual(mail.outbox[-1].to, ['s@example.test'])
        self.client.post(reverse('delete_slot', args=[self.future.pk]))
        self.future.refresh_from_db()
        self.assertFalse(self.future.is_active)  # kept for history, hidden from students

    def test_tutor_tools_are_role_protected(self):
        self.client.force_login(self.user)  # a student
        self.assertRedirects(self.client.get(reverse('manage_slots')), reverse('dashboard'))
        self.assertEqual(self.client.post(reverse('delete_slot', args=[self.future.pk])).status_code, 404)
        self.client.logout()
        self.assertIn('/accounts/login/', self.client.get(reverse('manage_slots')).url)

    def test_other_tutor_cannot_touch_my_slot(self):
        other_user = User.objects.create_user(username='ot@example.test', email='ot@example.test', password='GoodPassword123!')
        Tutor.objects.create(user=other_user, display_name='Intruder', subjects='X')
        self.client.force_login(other_user)
        self.assertEqual(self.client.post(reverse('delete_slot', args=[self.future.pk])).status_code, 404)

    def test_dashboards_render_for_each_role(self):
        Booking.objects.create(student=self.student, slot=self.future)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('dashboard')), 'Up next')
        self.assertEqual(self.client.get(reverse('my_bookings')).status_code, 200)
        self.client.force_login(self.tutor_user)
        self.assertContains(self.client.get(reverse('dashboard')), 'Open slots')
        self.assertEqual(self.client.get(reverse('manage_slots')).status_code, 200)


class V2FeatureTests(TestCase):
    def setUp(self):
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        mk = lambda e, f='Test': User.objects.create_user(username=e, email=e, password='GoodPassword123!', first_name=f)
        cls.su, cls.tu = mk('s@example.test', 'Stu'), mk('t@example.test', 'Tut')
        cls.student = Student.objects.create(user=cls.su)
        cls.tutor = Tutor.objects.create(user=cls.tu, display_name='Approver', subjects='Physics', location='Hall', requires_approval=True)
        day = timezone.localdate() + timedelta(days=3)
        cls.slot = AvailabilitySlot.objects.create(tutor=cls.tutor, date=day, start_time=time(10), end_time=time(11))
        cls.slot2 = AvailabilitySlot.objects.create(tutor=cls.tutor, date=day, start_time=time(12), end_time=time(13))

    def _request(self):
        self.client.force_login(self.su)
        self.client.post(reverse('start_booking', args=[self.slot.pk]), {'notes': 'hi'})
        self.client.post(reverse('booking_review'))
        return Booking.objects.get(student=self.student)

    def test_approval_flow(self):
        b = self._request()
        self.assertEqual(b.status, Booking.PENDING)
        self.assertTrue(Notification.objects.filter(user=self.tu, kind='request').exists())
        self.client.force_login(self.tu)
        self.assertContains(self.client.get(reverse('dashboard')), 'Booking requests')
        self.client.post(reverse('tutor_decide_booking', args=[b.pk]), {'decision': 'approve'})
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.CONFIRMED)
        self.assertTrue(Notification.objects.filter(user=self.su, title__icontains='approved').exists())

    def test_decline_frees_slot(self):
        b = self._request()
        self.client.force_login(self.tu)
        self.client.post(reverse('tutor_decide_booking', args=[b.pk]), {'decision': 'decline'})
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.DECLINED)
        self.assertTrue(services.slot_available(self.slot))

    def test_pending_blocks_slot(self):
        self._request()
        self.assertFalse(services.slot_available(self.slot))

    def test_reschedule(self):
        b = self._request()
        self.client.force_login(self.su)
        self.assertEqual(self.client.get(reverse('reschedule', args=[b.pk])).status_code, 200)
        self.client.post(reverse('reschedule', args=[b.pk]), {'slot_id': self.slot2.pk})
        b.refresh_from_db()
        self.assertEqual(b.slot_id, self.slot2.pk)
        self.assertTrue(services.slot_available(self.slot))

    def test_messages_only_between_parties(self):
        b = self._request()
        url = reverse('booking_message', args=[b.pk])
        self.client.force_login(self.su)
        self.client.post(url, {'body': 'Hello tutor'})
        self.assertEqual(b.messages.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.tu, kind='message').exists())
        stranger = User.objects.create_user(username='x@example.test', email='x@example.test', password='GoodPassword123!')
        Student.objects.create(user=stranger)
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url, {'body': 'spam'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('booking_detail', args=[b.pk])).status_code, 404)

    def test_notifications_page_and_mark_read(self):
        self._request()
        self.client.force_login(self.su)
        self.assertEqual(self.client.get(reverse('notifications')).status_code, 200)
        self.client.post(reverse('notifications_read_all'))
        self.assertFalse(Notification.objects.filter(user=self.su, is_read=False).exists())

    def test_reminders_sent_once(self):
        self.tutor.requires_approval = False
        self.tutor.save()
        soon = timezone.localtime() + timedelta(hours=3)
        slot = AvailabilitySlot.objects.create(tutor=self.tutor, date=soon.date(), start_time=soon.time().replace(microsecond=0),
                                               end_time=(soon + timedelta(minutes=30)).time().replace(microsecond=0))
        if soon.date() != (soon + timedelta(minutes=30)).date():
            self.skipTest('crosses midnight')
        Booking.objects.create(student=self.student, slot=slot)
        self.assertEqual(services.send_due_reminders(), 1)
        self.assertEqual(services.send_due_reminders(), 0)

    def test_api_search_healthz_robots(self):
        self.assertEqual(self.client.get(reverse('api_search'), {'q': 'Appr'}).json()['results'][0]['title'], 'Approver')
        self.assertEqual(self.client.get(reverse('api_search'), {'q': 'a'}).json()['results'], [])
        self.assertEqual(self.client.get(reverse('healthz')).status_code, 200)
        self.assertEqual(self.client.get(reverse('robots_txt')).status_code, 200)

    def test_security_headers_and_no_footer(self):
        resp = self.client.get(reverse('home'))
        self.assertIn('Content-Security-Policy', resp)
        self.assertNotContains(resp, 'Group 1')
        self.assertNotContains(resp, '<footer')

    def test_login_throttle(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'username': 's@example.test', 'password': 'wrong'})
        resp = self.client.post(reverse('login'), {'username': 's@example.test', 'password': 'GoodPassword123!'})
        self.assertEqual(resp.status_code, 429)

    def test_custom_404(self):
        self.assertContains(self.client.get('/nope-nothing/'), 'Page not found', status_code=404)


class CrossPlatformTests(TestCase):
    def test_manifest_is_installable(self):
        resp = self.client.get(reverse('manifest'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/manifest+json')
        data = resp.json()
        self.assertEqual((data['scope'], data['display']), ('/', 'standalone'))
        purposes = {(i['sizes'], i['purpose']) for i in data['icons'] if i['type'] == 'image/png'}
        self.assertIn(('192x192', 'any'), purposes)
        self.assertIn(('512x512', 'maskable'), purposes)

    def test_service_worker_scope_and_offline_page(self):
        resp = self.client.get(reverse('service_worker'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('javascript', resp['Content-Type'])
        self.assertEqual(resp['Service-Worker-Allowed'], '/')
        self.assertContains(self.client.get(reverse('offline')), "You're offline")

    def test_head_has_mobile_and_desktop_meta(self):
        html = self.client.get(reverse('home')).content.decode()
        for needle in ('viewport-fit=cover', 'apple-touch-icon', 'rel="manifest"', 'apple-mobile-web-app-capable', 'theme-color'):
            self.assertIn(needle, html)


class V3Base(TestCase):
    """Shared fixtures for the v3 feature tests."""

    @classmethod
    def setUpTestData(cls):
        cls.tutor_user = User.objects.create_user('tutor3@example.test', 'tutor3@example.test', 'GoodPassword123!')
        cls.tutor = Tutor.objects.create(user=cls.tutor_user, display_name='T3', subjects='Math',
                                         meeting_url='https://meet.example.test/abc')
        cls.user = User.objects.create_user('s3@example.test', 's3@example.test', 'GoodPassword123!', first_name='Sam')
        cls.student = Student.objects.create(user=cls.user)
        cls.user2 = User.objects.create_user('s4@example.test', 's4@example.test', 'GoodPassword123!')
        cls.student2 = Student.objects.create(user=cls.user2)
        cls.day = timezone.localdate() + timedelta(days=3)

    def slot(self, offset=0, hour=10):
        return AvailabilitySlot.objects.create(tutor=self.tutor, date=self.day + timedelta(days=offset),
                                               start_time=time(hour), end_time=time(hour + 1))

    def past_confirmed(self):
        slot = AvailabilitySlot.objects.create(tutor=self.tutor, date=timezone.localdate() - timedelta(days=1),
                                               start_time=time(9), end_time=time(10))
        return Booking.objects.create(student=self.student, slot=slot, status=Booking.CONFIRMED)


class V3ModelTests(V3Base):
    """Rajbeer: schema additions behave as designed."""

    def test_new_fields_default_safely(self):
        self.assertTrue(self.student.email_verified)      # legacy and seeded accounts stay verified
        self.assertEqual(self.past_confirmed().tutor_notes, '')

    def test_waitlist_entry_is_unique_per_student_and_slot(self):
        from django.db import IntegrityError, transaction
        slot = self.slot()
        WaitlistEntry.objects.create(student=self.student, slot=slot)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WaitlistEntry.objects.create(student=self.student, slot=slot)

    def test_no_show_is_not_an_active_status(self):
        self.assertNotIn(Booking.NO_SHOW, Booking.ACTIVE)

    def test_waitlist_registered_in_admin(self):
        from django.contrib import admin
        self.assertIn(WaitlistEntry, admin.site._registry)


class EmailVerificationTests(V3Base):
    """Krish: sign-up email, signed link, resend limit, gating."""

    def register(self, role='student', email='new@example.test'):
        from django.core import mail
        mail.outbox.clear()
        return self.client.post(reverse('register'), {
            'full_name': 'New Person', 'email': email, 'role': role,
            'password1': 'GoodPassword123!', 'password2': 'GoodPassword123!'})

    def test_registration_sends_link_and_blocks_booking_until_verified(self):
        from django.core import mail
        self.register()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/verify/', mail.outbox[0].body)
        new = Student.objects.get(user__email='new@example.test')
        self.assertFalse(new.email_verified)
        slot = self.slot()
        resp = self.client.get(reverse('start_booking', args=[slot.pk]))
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)
        link = mail.outbox[0].body.split('\n')[3].strip()
        self.client.get(link)
        new.refresh_from_db()
        self.assertTrue(new.email_verified)
        self.assertEqual(self.client.get(reverse('start_booking', args=[slot.pk])).status_code, 200)

    def test_bad_or_mismatched_token_is_rejected(self):
        from django.core import signing
        self.register(email='x@example.test')
        resp = self.client.get(reverse('verify_email', args=['not-a-real-token']))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Student.objects.get(user__email='x@example.test').email_verified)
        token = signing.dumps({'u': self.user.pk, 'e': 'someone-else@example.test'}, salt='studysync.email-verification')
        self.client.get(reverse('verify_email', args=[token]))  # email no longer matches the account
        self.assertFalse(Student.objects.get(user__email='x@example.test').email_verified)

    def test_expired_token_is_rejected(self):
        from unittest import mock
        from . import verification
        self.register(email='old@example.test')
        user = User.objects.get(email='old@example.test')
        token = verification.make_token(user)
        with mock.patch.object(verification, 'MAX_AGE_SECONDS', -1):
            self.client.get(reverse('verify_email', args=[token]))
        self.assertFalse(Student.objects.get(user=user).email_verified)

    def test_resend_is_rate_limited(self):
        from django.core import mail
        cache.clear()
        self.register(email='y@example.test')
        mail.outbox.clear()
        self.client.post(reverse('resend_verification'))
        self.client.post(reverse('resend_verification'))
        self.assertEqual(len(mail.outbox), 1)

    def test_unverified_tutor_cannot_publish_slots(self):
        self.register(role='tutor', email='tt@example.test')
        self.client.post(reverse('manage_slots'), {'date': str(self.day), 'start_time': '09:00', 'end_time': '10:00', 'repeat_weeks': 1})
        self.assertEqual(AvailabilitySlot.objects.filter(tutor__user__email='tt@example.test').count(), 0)


class SessionNotesTests(V3Base):
    """Krish: tutor follow-up notes after a session."""

    def test_tutor_notes_saved_and_student_notified(self):
        booking = self.past_confirmed()
        self.client.force_login(self.tutor_user)
        self.client.post(reverse('tutor_session_notes', args=[booking.pk]), {'tutor_notes': 'Practise problem set 3'})
        booking.refresh_from_db()
        self.assertEqual(booking.tutor_notes, 'Practise problem set 3')
        self.assertTrue(Notification.objects.filter(user=self.user, title__contains='shared notes').exists())

    def test_notes_rejected_for_future_session_and_for_students(self):
        future = services.create_booking(self.student, self.slot().pk)
        self.client.force_login(self.tutor_user)
        self.client.post(reverse('tutor_session_notes', args=[future.pk]), {'tutor_notes': 'too early'})
        future.refresh_from_db()
        self.assertEqual(future.tutor_notes, '')
        past = self.past_confirmed()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('tutor_session_notes', args=[past.pk]), {'tutor_notes': 'x'}).status_code, 404)


class WaitlistTests(V3Base):
    """Vraj: waitlist for booked slots."""

    def test_waitlist_notifies_when_slot_is_cancelled(self):
        slot = self.slot()
        booking = services.create_booking(self.student, slot.pk)
        self.client.force_login(self.user2)
        self.client.post(reverse('waitlist_join', args=[slot.pk]))
        self.assertTrue(WaitlistEntry.objects.filter(student=self.student2, slot=slot).exists())
        self.client.post(reverse('waitlist_join', args=[slot.pk]))  # idempotent
        self.assertEqual(WaitlistEntry.objects.count(), 1)
        services.set_status(booking, Booking.CANCELLED)
        self.assertTrue(Notification.objects.filter(user=self.user2, kind='waitlist').exists())
        self.assertFalse(WaitlistEntry.objects.exists())

    def test_cannot_join_waitlist_for_open_slot(self):
        slot = self.slot()
        self.client.force_login(self.user2)
        self.client.post(reverse('waitlist_join', args=[slot.pk]))
        self.assertFalse(WaitlistEntry.objects.exists())

    def test_waitlist_notified_on_reschedule(self):
        a, b = self.slot(0, 10), self.slot(1, 10)
        booking = services.create_booking(self.student, a.pk)
        services.join_waitlist(self.student2, a)
        services.reschedule_booking(booking, b.pk)
        self.assertTrue(Notification.objects.filter(user=self.user2, kind='waitlist').exists())

    def test_leave_waitlist(self):
        slot = self.slot()
        services.create_booking(self.student, slot.pk)
        services.join_waitlist(self.student2, slot)
        self.client.force_login(self.user2)
        self.client.post(reverse('waitlist_leave', args=[slot.pk]))
        self.assertFalse(WaitlistEntry.objects.exists())


class RecurringBookingTests(V3Base):
    """Vraj: weekly repeat bookings."""

    def test_recurring_books_matching_weeks_and_skips_gaps(self):
        base = self.slot(0)
        self.slot(7)           # week 2 exists; week 3 does not
        bookings, skipped = services.create_recurring(self.student, base.pk, 'weekly', weeks=3)
        self.assertEqual(len(bookings), 2)
        self.assertEqual(skipped, [self.day + timedelta(days=14)])

    def test_recurring_skips_taken_week(self):
        base, week2 = self.slot(0), self.slot(7)
        services.create_booking(self.student2, week2.pk)
        bookings, skipped = services.create_recurring(self.student, base.pk, weeks=2)
        self.assertEqual(len(bookings), 1)
        self.assertEqual(len(skipped), 1)

    def test_recurring_via_views(self):
        base = self.slot(0)
        self.slot(7)
        self.client.force_login(self.user)
        self.client.post(reverse('start_booking', args=[base.pk]), {'notes': '', 'repeat_weeks': 2})
        self.client.post(reverse('booking_review'))
        self.assertEqual(Booking.objects.filter(student=self.student).count(), 2)


class NoShowTests(V3Base):
    """Vraj: marking and limiting no-shows."""

    def test_tutor_marks_no_show_and_only_for_past_sessions(self):
        past = self.past_confirmed()
        future = services.create_booking(self.student, self.slot().pk)
        self.client.force_login(self.tutor_user)
        self.client.post(reverse('tutor_mark_no_show', args=[past.pk]))
        self.client.post(reverse('tutor_mark_no_show', args=[future.pk]))
        past.refresh_from_db(); future.refresh_from_db()
        self.assertEqual(past.status, Booking.NO_SHOW)
        self.assertEqual(future.status, Booking.CONFIRMED)

    def test_other_tutor_cannot_mark_no_show(self):
        past = self.past_confirmed()
        other = User.objects.create_user('o@example.test', 'o@example.test', 'GoodPassword123!')
        Tutor.objects.create(user=other, display_name='Other', subjects='x')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('tutor_mark_no_show', args=[past.pk])).status_code, 404)

    def test_three_no_shows_pause_booking(self):
        for i in range(services.NO_SHOW_LIMIT):
            slot = AvailabilitySlot.objects.create(tutor=self.tutor, date=timezone.localdate() - timedelta(days=i + 1),
                                                   start_time=time(9), end_time=time(10))
            Booking.objects.create(student=self.student, slot=slot, status=Booking.NO_SHOW)
        with self.assertRaises(services.BookingError):
            services.create_booking(self.student, self.slot().pk)


class AnalyticsTests(V3Base):
    """Harsh: analytics page and CSV export."""

    def test_analytics_access_and_numbers(self):
        self.past_confirmed()
        services.create_booking(self.student, self.slot().pk)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 302)  # students are redirected
        self.client.force_login(self.tutor_user)
        resp = self.client.get(reverse('analytics'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['stats']['total'], 2)
        self.assertEqual(resp.context['stats']['held'], 1)
        self.assertContains(resp, 'Did everyone show up?')

    def test_analytics_scoped_to_own_tutor(self):
        services.create_booking(self.student, self.slot().pk)
        other = User.objects.create_user('o2@example.test', 'o2@example.test', 'GoodPassword123!')
        Tutor.objects.create(user=other, display_name='Other2', subjects='x')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('analytics')).context['stats']['total'], 0)

    def test_empty_analytics_page_renders(self):
        self.client.force_login(self.tutor_user)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 200)

    def test_csv_export_scoped_and_protected(self):
        self.past_confirmed()
        self.assertEqual(self.client.get(reverse('analytics_csv')).status_code, 302)  # login required
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('analytics_csv')).status_code, 404)  # students have no analytics
        self.client.force_login(self.tutor_user)
        resp = self.client.get(reverse('analytics_csv'))
        self.assertEqual(resp['Content-Type'], 'text/csv')
        body = resp.content.decode()
        self.assertIn('s3@example.test', body)
        self.assertEqual(len(body.strip().splitlines()), 2)

    def test_csv_neutralises_formula_cells(self):
        evil = User.objects.create_user('=cmd@example.test', '=cmd@example.test', 'GoodPassword123!')
        other = Student.objects.create(user=evil)
        Booking.objects.create(student=other, slot=self.slot(), status=Booking.CONFIRMED)
        self.client.force_login(self.tutor_user)
        self.assertIn("'=cmd@example.test", self.client.get(reverse('analytics_csv')).content.decode())


class OnlineFilterTests(V3Base):
    """Harsh: search filter for tutors who offer online sessions."""

    def test_online_filter_only_lists_tutors_with_a_link(self):
        Tutor.objects.create(display_name='In Person Tutor', subjects='Math')
        resp = self.client.get(reverse('catalog'), {'online': 'yes'})
        self.assertContains(resp, 'T3')
        self.assertNotContains(resp, 'In Person Tutor')
        self.client.cookies.clear()  # the catalog remembers filters in a cookie
        self.assertContains(self.client.get(reverse('catalog')), 'In Person Tutor')

    def test_tutor_can_save_meeting_link_in_profile_form(self):
        from .forms import TutorProfileForm
        form = TutorProfileForm({'display_name': 'T3', 'subjects': 'Math', 'location': 'Leddy Library',
                                 'meeting_url': 'https://meet.example.test/new'}, instance=self.tutor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(TutorProfileForm({'display_name': 'T3', 'subjects': 'Math', 'location': 'x',
                                           'meeting_url': 'not a url'}, instance=self.tutor).is_valid())


class V3InterfaceTests(V3Base):
    """Bhavya: what people actually see on the new screens."""

    def test_detail_page_lists_full_slots_with_waitlist_button(self):
        slot = self.slot()
        services.create_booking(self.student, slot.pk)
        self.client.force_login(self.user2)
        resp = self.client.get(reverse('tutor_detail', args=[self.tutor.pk]))
        self.assertContains(resp, 'Join waitlist')
        services.join_waitlist(self.student2, slot)
        self.assertContains(self.client.get(reverse('tutor_detail', args=[self.tutor.pk])), 'On waitlist')

    def test_meeting_link_shown_for_confirmed_booking(self):
        booking = services.create_booking(self.student, self.slot().pk)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('booking_detail', args=[booking.pk])), 'https://meet.example.test/abc')

    def test_student_sees_session_notes_and_tutor_sees_form(self):
        booking = self.past_confirmed()
        booking.tutor_notes = 'Review chapter 4'
        booking.save()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('booking_detail', args=[booking.pk])), 'Review chapter 4')
        self.client.force_login(self.tutor_user)
        self.assertContains(self.client.get(reverse('booking_detail', args=[booking.pk])), 'Save and share with student')

    def test_unverified_user_sees_banner_and_verified_does_not(self):
        Student.objects.filter(pk=self.student.pk).update(email_verified=False)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('dashboard')), 'Resend link')
        Student.objects.filter(pk=self.student.pk).update(email_verified=True)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Resend link')

    def test_tutor_nav_has_analytics_and_no_show_button(self):
        booking = self.past_confirmed()
        self.client.force_login(self.tutor_user)
        self.assertContains(self.client.get(reverse('dashboard')), 'Analytics')
        self.assertContains(self.client.get(reverse('booking_detail', args=[booking.pk])), 'Mark as no-show')


class FacultyPageTests(TestCase):
    def test_faculty_page_is_public_and_lists_names_without_tutor_profiles(self):
        resp = self.client.get(reverse('faculty'))
        self.assertContains(resp, 'Dr. Aznam Yacoub')
        self.assertContains(resp, 'Dr. Olena Syrotkina')
        self.assertContains(resp, 'not StudySync tutors')
        self.assertFalse(Tutor.objects.filter(display_name__icontains='Yacoub').exists())


class PagerTests(TestCase):
    def test_previous_button_uses_a_left_arrow_and_is_not_mirrored(self):
        for i in range(30):
            Tutor.objects.create(display_name=f'Pager Tutor {i:02d}', subjects='Pagination')
        resp = self.client.get(reverse('catalog'), {'page': 2})
        self.assertContains(resp, 'Previous')
        self.assertContains(resp, 'M19 12H5M11 6l-6 6 6 6')   # left-pointing arrow
        self.assertNotContains(resp, 'sr-flip')                 # the old mirrored-text hack
        first = self.client.get(reverse('catalog'))
        self.assertContains(first, 'is-disabled')               # Previous is shown but disabled on page 1
