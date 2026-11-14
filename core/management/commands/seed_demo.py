"""Idempotent demo-only seed data. Peer tutors are the Group 11 members; faculty profiles are marked demo."""
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from core import services
from core.models import AvailabilitySlot, Booking, BookingMessage, Review, Room, Student, Tutor, WaitlistEntry

User = get_user_model()

ADVISOR_SUFFIX = ' (Demo)'  # faculty office-hours demo profiles, always visibly marked


class Command(BaseCommand):
    help = 'Create sample StudySync users, tutors, rooms, and upcoming availability.'

    def handle(self, *args, **options):
        student, made = User.objects.get_or_create(
            username='student@example.test', defaults={'email': 'student@example.test', 'first_name': 'Taylor', 'last_name': 'Morgan'}
        )
        if made:
            student.set_password('Demo12345!')
            student.save()
        Student.objects.get_or_create(user=student, defaults={'bio': 'Master of Applied Computing (MAC) student, University of Windsor.'})

        tutor_user, made = User.objects.get_or_create(
            username='tutor@example.test', defaults={'email': 'tutor@example.test', 'first_name': 'Vrajkumar', 'last_name': 'Patel'}
        )
        if made:
            tutor_user.set_password('Demo12345!')
            tutor_user.save()

        alex_user, made = User.objects.get_or_create(
            username='alex@example.test', defaults={'email': 'alex@example.test', 'first_name': 'Rajbeer', 'last_name': 'Kaur Dutta'})
        if made:
            alex_user.set_password('Demo12345!')
            alex_user.save()

        self._remove_old_fictional_tutors()
        tutors = [  # real Group 11 members (MAC students) as peer tutors; subjects follow what each built for COMP 8347
            ('Vrajkumar Patel', 'Internet Applications, Advanced Systems Programming', 'Leddy Library', 'Group 11 member and MAC student. Built the StudySync booking engine and tests. Peer help with Django, C and Linux.'),
            ('Rajbeer Kaur Dutta', 'Advanced Databases, Cloud and DevOps', 'Erie Hall', 'Group 11 member and MAC student. Built the StudySync data models, migrations and Docker setup. Peer help with schemas, SQL and deployment.'),
            ('Harsh Patel', 'Internet Applications, Python', 'Lambton Tower', 'Group 11 member and MAC student. Built StudySync search, uploads and sessions. Peer help with Django forms, search and file handling.'),
            ('Krishkumar Patel', 'Networking and Data Security, Internet Applications', 'Leddy Library', 'Group 11 member and MAC student. Built StudySync authentication, forms and security. Peer help with login flows and secure web practices.'),
            ('Bhavya Patel', 'Internet Applications, JavaScript', '300 Ouellette', 'Group 11 member and MAC student. Built the StudySync templates and CSS design. Peer help with HTML, CSS and front-end JavaScript.'),
        ]
        online = {'Vrajkumar Patel': 'https://meet.example.test/vrajkumar-patel', 'Harsh Patel': 'https://meet.example.test/harsh-patel',
                  'Bhavya Patel': 'https://meet.example.test/bhavya-patel'}
        for i, (name, subjects, location, bio) in enumerate(tutors):
            tutor, _ = Tutor.objects.get_or_create(display_name=name, defaults={
                'user': tutor_user if i == 0 else None,
                'subjects': subjects, 'location': location, 'bio': bio,
            })
            if (tutor.subjects, tutor.bio, tutor.location) != (subjects, bio, location):  # refresh older demo rows
                tutor.subjects, tutor.bio, tutor.location = subjects, bio, location
                tutor.save(update_fields=['subjects', 'bio', 'location'])
            if name in online and not tutor.meeting_url:
                tutor.meeting_url = online[name]
                tutor.save(update_fields=['meeting_url'])
            if i == 0 and tutor.user_id is None:
                tutor.user = tutor_user
                tutor.save(update_fields=['user'])
            if name == 'Rajbeer Kaur Dutta' and (tutor.user_id is None or not tutor.requires_approval):
                tutor.user, tutor.requires_approval = alex_user, True
                tutor.save(update_fields=['user', 'requires_approval'])

        rooms = [  # Leddy rooms follow the library's published types: group rooms hold 4, personal rooms are single-seat
            ('Group Study Room 4111C', 'Leddy Library', 4, 'Whiteboard, Wi-Fi; sign out the key at the Information Desk', 'Fourth-floor group room for up to four people.'),
            ('Group Study Room 1', 'Leddy Library', 4, 'Whiteboard, Wi-Fi, power outlets', 'Bookable group room (up to 4 people, max 3 hours per day).'),
            ('Group Study Room 2', 'Leddy Library', 4, 'Whiteboard, Wi-Fi, power outlets', 'Bookable group room (up to 4 people, max 3 hours per day).'),
            ('Personal Study Room 1', 'Leddy Library', 1, 'Desk, Wi-Fi, power outlet', 'Quiet single-person room for focused work.'),
            ('Personal Study Room 2', 'Leddy Library', 1, 'Desk, Wi-Fi, power outlet', 'Quiet single-person room for focused work.'),
            ('Collaboration Pod', 'Erie Hall', 3, 'Wi-Fi, charging outlets', 'A quiet pod for quick study sessions.'),
            ('Coding Studio', 'Erie Hall', 5, 'Dual monitors, whiteboard, Wi-Fi', 'Pair programming and project work for computer science students.'),
            ('Lab Commons', 'Lambton Tower', 8, 'Whiteboards, Wi-Fi, power outlets', 'Open group space beside the computing labs.'),
            ('Seminar Room A', '300 Ouellette', 12, 'Projector, video conferencing, Wi-Fi', 'Seats a full MAC tutorial group or presentation rehearsal.'),
            ('Project Room 2', '300 Ouellette', 6, 'Display, whiteboard, Wi-Fi', 'Built for group-project meetings and progress-evaluation practice.'),
            ('Student Centre Lounge 3', 'CAW Student Centre', 8, 'Sofas, whiteboard, Wi-Fi', 'Relaxed group study with a casual feel.'),
        ]
        for name, building, capacity, amenities, description in rooms:
            Room.objects.get_or_create(name=name, building=building, defaults={
                'capacity': capacity, 'amenities': amenities, 'description': description,
            })

        count = 0
        starts = [time(10, 0), time(11, 30), time(14, 0), time(15, 30), time(9, 0), time(17, 0)]
        ends = [time(11, 0), time(12, 30), time(15, 0), time(16, 30), time(10, 0), time(18, 0)]
        for delta in range(1, 15):
            day = timezone.localdate() + timedelta(days=delta)
            if day.weekday() >= 5:  # tutors work weekdays; rooms also open Saturday mornings
                if day.weekday() == 5:
                    for room in Room.objects.filter(is_active=True):
                        for start, end in zip(starts[:2], ends[:2]):
                            _, created = AvailabilitySlot.objects.get_or_create(
                                room=room, tutor=None, date=day, start_time=start, end_time=end)
                            count += int(created)
                continue
            for tutor in Tutor.objects.filter(is_active=True).exclude(display_name__endswith=ADVISOR_SUFFIX):
                for start, end in zip(starts[:5], ends[:5]):
                    _, created = AvailabilitySlot.objects.get_or_create(
                        tutor=tutor, room=None, date=day, start_time=start, end_time=end
                    )
                    count += int(created)
            for room in Room.objects.filter(is_active=True):
                for start, end in zip(starts, ends):
                    _, created = AvailabilitySlot.objects.get_or_create(
                        room=room, tutor=None, date=day, start_time=start, end_time=end
                    )
                    count += int(created)
        self._seed_advisors()
        self._seed_history(student)
        self._seed_activity()
        self.stdout.write(self.style.SUCCESS(f'Demo ready; added {count} availability slots.'))
        self.stdout.write('Faculty advisor (demo, approves requests): advisor@example.test / Demo12345!')
        self.stdout.write('Student: student@example.test / Demo12345!')
        self.stdout.write('Tutor (Vrajkumar Patel): tutor@example.test / Demo12345!')
        self.stdout.write('Tutor (Rajbeer Kaur Dutta, approves requests): alex@example.test / Demo12345!')
        self.stdout.write(f'Totals: {Tutor.objects.count()} tutors, {Room.objects.count()} rooms, {AvailabilitySlot.objects.count()} slots, {Booking.objects.count()} bookings.')
        self.stdout.write('These credentials and demo data are for local development only.')

    def _remove_old_fictional_tutors(self):
        """Earlier demo versions used invented peer tutors; remove them so only real people remain."""
        old = ['Jordan Smith', 'Alex Lee', 'Sam Rivera', 'Casey Chen', 'Priya Nair', 'Omar Haddad', 'Mei Tanaka',
               'Daniel Okafor', 'Sofia Marino', 'Lucas Bernard', 'Hannah Kim', 'Ibrahim Yusuf']
        Tutor.objects.filter(display_name__in=old).delete()

    def _seed_advisors(self):
        """Bookable faculty office hours, using names from the School of Computer Science faculty page.

        This is a prototype: the profiles are demo illustrations and carry a visible "(Demo)" marker.
        Courses, research areas and contact details are deliberately not stated; see the official page.
        """
        advisors = [  # (name, weekday 1=Tue 3=Thu, hour)
            ('Dr. Olena Syrotkina', 1, 13), ('Dr. Aznam Yacoub', 3, 13), ('Dr. Imran Ahmad', 1, 14),
            ('Dr. Christie Ezeife', 3, 14), ('Dr. Ziad Kobti', 1, 15), ('Dr. Luis Rueda', 3, 15),
            ('Dr. Alioune Ngom', 1, 16), ('Dr. Sherif Saad Ahmed', 3, 16),
        ]
        bio = ('Demo office-hours profile for the StudySync prototype. The person named is listed on the University of '
               'Windsor School of Computer Science faculty page; they have not endorsed or taken part in this app. '
               'For real office hours, use the official page.')
        for i, (name, weekday, hour) in enumerate(advisors):
            full_name = name + ADVISOR_SUFFIX
            user = None
            if i == 0:
                user, made = User.objects.get_or_create(username='advisor@example.test', defaults={
                    'email': 'advisor@example.test', 'first_name': 'Olena', 'last_name': 'Syrotkina (Demo)'})
                if made:
                    user.set_password('Demo12345!')
                    user.save()
            advisor, _ = Tutor.objects.get_or_create(display_name=full_name, defaults={
                'user': user, 'subjects': 'Faculty office hours', 'bio': bio, 'location': '300 Ouellette',
                'requires_approval': True, 'meeting_url': ''})
            for week in range(0, 5):
                day = timezone.localdate() + timedelta(days=1) + timedelta(days=(weekday - (timezone.localdate() + timedelta(days=1)).weekday()) % 7 + 7 * week)
                AvailabilitySlot.objects.get_or_create(tutor=advisor, room=None, date=day,
                                                       start_time=time(hour, 0), end_time=time(hour + 1, 0))

    def _seed_activity(self):
        """Past bookings (completed, cancelled, no-show) so Analytics has data, plus a full slot with a waitlist."""
        marker = '[demo-activity]'
        if Booking.objects.filter(notes=marker).exists():
            return
        people = []
        for i in range(12):
            u, made = User.objects.get_or_create(username=f'learner{i}@example.test', defaults={
                'email': f'learner{i}@example.test', 'first_name': f'Learner{i}', 'last_name': 'Demo'})
            if made:
                u.set_unusable_password()
                u.save()
            people.append(Student.objects.get_or_create(user=u, defaults={'bio': 'MAC student, University of Windsor.'})[0])
        # statuses spread over three weeks; no student gets enough no-shows to be paused
        pattern = ['confirmed'] * 6 + ['cancelled', 'no_show', 'confirmed', 'declined', 'confirmed', 'no_show']
        hours = [(9, 10), (10, 11), (11, 12), (14, 15), (15, 16), (10, 11), (14, 15), (9, 10), (15, 16), (11, 12), (14, 15), (10, 11)]
        n = 0
        for name in ('Vrajkumar Patel', 'Rajbeer Kaur Dutta', 'Harsh Patel', 'Bhavya Patel'):
            tutor = Tutor.objects.filter(display_name=name).first()
            if not tutor:
                continue
            for k, status in enumerate(pattern):
                day = timezone.localdate() - timedelta(days=2 + (k * 2 + n) % 21)
                start, end = hours[(k + n) % len(hours)]
                slot, _ = AvailabilitySlot.objects.get_or_create(
                    tutor=tutor, room=None, date=day, start_time=time(start, 0), end_time=time(end, 0))
                student_row = people[(k + n) % len(people)]
                if Booking.objects.filter(slot=slot, status__in=Booking.ACTIVE).exists():
                    continue
                Booking.objects.create(student=student_row, slot=slot, notes=marker if n == 0 and k == 0 else 'Demo history',
                                       status={'no_show': Booking.NO_SHOW, 'declined': Booking.DECLINED,
                                               'cancelled': Booking.CANCELLED}.get(status, Booking.CONFIRMED))
            n += 1
        # a fully booked future slot with someone waiting, so the waitlist can be shown
        sam = Tutor.objects.filter(display_name='Harsh Patel').first()
        if sam:
            full = services.available_slots(AvailabilitySlot.objects.filter(tutor=sam)).order_by('date', 'start_time').first()
            if full:
                Booking.objects.create(student=people[0], slot=full, status=Booking.CONFIRMED, notes='Demo full slot')
                WaitlistEntry.objects.get_or_create(student=people[1], slot=full)

    def _seed_history(self, demo_user):
        """A finished session for the demo student (so the review flow works) plus sample reviews."""
        demo_student = Student.objects.get(user=demo_user)
        yesterday = timezone.localdate() - timedelta(days=1)
        past_tutor = Tutor.objects.filter(display_name='Rajbeer Kaur Dutta').first()
        if past_tutor:
            slot, _ = AvailabilitySlot.objects.get_or_create(
                tutor=past_tutor, room=None, date=yesterday, start_time=time(9, 0), end_time=time(10, 0))
            Booking.objects.get_or_create(student=demo_student, slot=slot, defaults={'notes': 'Django models and migrations review'})
        upcoming_tutor = Tutor.objects.filter(display_name='Vrajkumar Patel').first()
        if upcoming_tutor:
            nxt = AvailabilitySlot.objects.filter(
                tutor=upcoming_tutor, is_active=True, date__gt=timezone.localdate()).order_by('date', 'start_time').first()
            if nxt and not Booking.objects.filter(student=demo_student, status=Booking.CONFIRMED, slot__date__gte=timezone.localdate()).exists():
                booking, made = Booking.objects.get_or_create(
                    student=demo_student, slot=nxt, defaults={'notes': 'Django ORM: relationships and queries'})
                if made:
                    services.notify_booking(booking, 'confirmed')
                    BookingMessage.objects.create(booking=booking, sender=demo_user, body='Hi! Could we focus on ORM relationships and migrations?')
                    BookingMessage.objects.create(booking=booking, sender=upcoming_tutor.user, body='Absolutely. Bring your models.py and we will walk through it.')
        # a pending request waiting on Rajbeer (who approves each booking)
        if past_tutor:
            nxt_alex = services.available_slots(AvailabilitySlot.objects.filter(tutor=past_tutor)).first()
            ru, made = User.objects.get_or_create(username='maya@example.test', defaults={'email': 'maya@example.test', 'first_name': 'Maya', 'last_name': 'Demo'})
            if made:
                ru.set_unusable_password()
                ru.save()
            requester, _ = Student.objects.get_or_create(user=ru)
            if nxt_alex and requester and not Booking.objects.filter(student=requester, status=Booking.PENDING).exists():
                req = Booking.objects.create(student=requester, slot=nxt_alex, status=Booking.PENDING, notes='Help with Django forms and validation')
                services.notify_booking(req, 'requested')
