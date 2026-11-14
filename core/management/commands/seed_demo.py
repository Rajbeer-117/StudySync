"""Idempotent demo-only seed data. All people and rooms below are fictional."""
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from core import services
from core.models import AvailabilitySlot, Booking, BookingMessage, Review, Room, Student, Tutor, WaitlistEntry

User = get_user_model()

ADVISOR_SUFFIX = ' (Demo)'  # fictional faculty advisors: one per required MAC course, office hours only


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
            username='tutor@example.test', defaults={'email': 'tutor@example.test', 'first_name': 'Jordan', 'last_name': 'Smith'}
        )
        if made:
            tutor_user.set_password('Demo12345!')
            tutor_user.save()

        alex_user, made = User.objects.get_or_create(
            username='alex@example.test', defaults={'email': 'alex@example.test', 'first_name': 'Alex', 'last_name': 'Lee'})
        if made:
            alex_user.set_password('Demo12345!')
            alex_user.save()

        tutors = [  # every demo tutor is a peer tutor from the Master of Applied Computing (MAC) program
            ('Jordan Smith', 'Web Development, Django', 'Erie Hall', 'MAC student (Internet Applications). Django models, views, forms, REST and deployment.'),
            ('Alex Lee', 'Operating Systems, C Programming', 'Erie Hall', 'MAC student (Advanced Systems Programming). Processes, pipes, signals and sockets in C.'),
            ('Sam Rivera', 'Algorithms, Python', 'Lambton Tower', 'MAC student. Algorithm design, complexity analysis and Python problem solving.'),
            ('Casey Chen', 'Databases, SQL', 'Leddy Library', 'MAC student (Advanced Database Topics). Query tuning, indexing and transactions.'),
            ('Priya Nair', 'Machine Learning, Python', 'Lambton Tower', 'MAC student. Supervised learning, scikit-learn and model evaluation.'),
            ('Omar Haddad', 'Data Mining, Statistics', '300 Ouellette', 'MAC student. Clustering, association rules and practical statistics for projects.'),
            ('Mei Tanaka', 'Cloud and DevOps, Docker', 'Erie Hall', 'MAC student. Containers, CI/CD with GitHub Actions and cloud deployment.'),
            ('Daniel Okafor', 'Computer Networks, Cybersecurity', '300 Ouellette', 'MAC student. TCP/IP, web security basics and secure coding habits.'),
            ('Sofia Marino', 'Software Engineering, Testing', 'Leddy Library', 'MAC student. Requirements, UML, unit testing and team workflow with Git.'),
            ('Lucas Bernard', 'JavaScript, Mobile Development', 'CAW Student Centre', 'MAC student. Front-end JavaScript, responsive UI and progressive web apps.'),
            ('Hannah Kim', 'Computer Vision, Deep Learning', 'Lambton Tower', 'MAC student. CNNs, image datasets and PyTorch for course projects.'),
            ('Ibrahim Yusuf', 'Big Data, Cloud Computing', '300 Ouellette', 'MAC student. Spark, data pipelines and working with large datasets.'),
        ]
        online = {'Jordan Smith': 'https://meet.example.test/jordan-smith', 'Sam Rivera': 'https://meet.example.test/sam-rivera',
                  'Priya Nair': 'https://meet.example.test/priya-nair', 'Mei Tanaka': 'https://meet.example.test/mei-tanaka',
                  'Hannah Kim': 'https://meet.example.test/hannah-kim', 'Ibrahim Yusuf': 'https://meet.example.test/ibrahim-yusuf'}
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
            if name == 'Alex Lee' and (tutor.user_id is None or not tutor.requires_approval):
                tutor.user, tutor.requires_approval = alex_user, True
                tutor.save(update_fields=['user', 'requires_approval'])

        rooms = [
            ('Room 214', 'Leddy Library', 4, 'Whiteboard, Wi-Fi, power outlets', 'A focused study room for small teams.'),
            ('Room 308', 'Leddy Library', 6, 'Display, whiteboard, Wi-Fi', 'Great for project work and group discussion.'),
            ('Collaboration Pod', 'Erie Hall', 3, 'Wi-Fi, charging outlets', 'A quiet pod for quick study sessions.'),
            ('Room 112', 'Leddy Library', 2, 'Desk, Wi-Fi, power outlets', 'A small quiet room for pairs and one-on-one study.'),
            ('Room 420', 'Leddy Library', 10, 'Projector, whiteboards, Wi-Fi', 'Large room for study groups and presentation practice.'),
            ('Lab Commons', 'Lambton Tower', 8, 'Whiteboards, Wi-Fi, power outlets', 'Open group space beside the computing labs.'),
            ('Seminar Room A', '300 Ouellette', 12, 'Projector, video conferencing, Wi-Fi', 'Seats a full MAC tutorial group or presentation rehearsal.'),
            ('Project Room 2', '300 Ouellette', 6, 'Display, whiteboard, Wi-Fi', 'Built for group-project meetings and progress-evaluation practice.'),
            ('Coding Studio', 'Erie Hall', 5, 'Dual monitors, whiteboard, Wi-Fi', 'Pair programming and hackathon prep.'),
            ('Quiet Pod B', 'Erie Hall', 2, 'Wi-Fi, charging outlets', 'Sound-dampened pod for focused solo or pair work.'),
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
        self.stdout.write('Tutor:   tutor@example.test / Demo12345!')
        self.stdout.write('Tutor (approves requests): alex@example.test / Demo12345!')
        self.stdout.write(f'Totals: {Tutor.objects.count()} tutors, {Room.objects.count()} rooms, {AvailabilitySlot.objects.count()} slots, {Booking.objects.count()} bookings.')
        self.stdout.write('These credentials and demo data are for local development only.')

    def _seed_advisors(self):
        """Fictional faculty advisors, one per required MAC course, bookable during weekly office hours.

        Names are invented on purpose: real faculty have not agreed to appear in this demo.
        """
        advisors = [  # (name, subjects, bio, weekday 1=Tue 3=Thu, hour)
            ('Dr. Avery Quinn', 'Internet Applications, Distributed Systems', 'Faculty advisor for COMP 8347 (demo). Office hours: web architecture and course project guidance.', 1, 13),
            ('Dr. Morgan Ellis', 'Advanced Databases', 'Faculty advisor for COMP 8157 (demo). Office hours: schema design, indexing and query plans.', 3, 13),
            ('Dr. Riley Banerjee', 'Advanced Systems Programming', 'Faculty advisor for COMP 8567 (demo). Office hours: C, processes and sockets.', 1, 14),
            ('Dr. Casey Lindqvist', 'Advanced Software Engineering', 'Faculty advisor for COMP 8117 (demo). Office hours: requirements, testing and team process.', 3, 14),
            ('Dr. Jamie Okonkwo', 'Networking and Data Security', 'Faculty advisor for COMP 8677 (demo). Office hours: protocols, cryptography and secure design.', 1, 15),
            ('Dr. Taylor Brandt', 'Advanced Computing Concepts', 'Faculty advisor for COMP 8547 (demo). Office hours: algorithms and complexity.', 3, 15),
            ('Dr. Sam Whitfield', 'Internship and Project', 'Faculty advisor for COMP 8967/8977 (demo). Office hours: project scope and progress evaluations.', 1, 16),
            ('Dr. Robin Castellanos', 'Artificial Intelligence', 'Faculty advisor for the optional MAC AI specialization (demo). Office hours: course selection and project topics.', 3, 16),
        ]
        for i, (name, subjects, bio, weekday, hour) in enumerate(advisors):
            full_name = name + ADVISOR_SUFFIX
            user = None
            if i == 0:
                user, made = User.objects.get_or_create(username='advisor@example.test', defaults={
                    'email': 'advisor@example.test', 'first_name': 'Avery', 'last_name': 'Quinn (Demo)'})
                if made:
                    user.set_password('Demo12345!')
                    user.save()
            advisor, _ = Tutor.objects.get_or_create(display_name=full_name, defaults={
                'user': user, 'subjects': subjects, 'bio': bio, 'location': '300 Ouellette',
                'requires_approval': True, 'meeting_url': 'https://meet.example.test/advisor-%d' % (i + 1)})
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
        for name in ('Jordan Smith', 'Alex Lee', 'Sam Rivera', 'Mei Tanaka'):
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
        sam = Tutor.objects.filter(display_name='Sam Rivera').first()
        if sam:
            full = services.available_slots(AvailabilitySlot.objects.filter(tutor=sam)).order_by('date', 'start_time').first()
            if full:
                Booking.objects.create(student=people[0], slot=full, status=Booking.CONFIRMED, notes='Demo full slot')
                WaitlistEntry.objects.get_or_create(student=people[1], slot=full)

    def _seed_history(self, demo_user):
        """A finished session for the demo student (so the review flow works) plus sample reviews."""
        demo_student = Student.objects.get(user=demo_user)
        yesterday = timezone.localdate() - timedelta(days=1)
        past_tutor = Tutor.objects.filter(display_name='Alex Lee').first()
        if past_tutor:
            slot, _ = AvailabilitySlot.objects.get_or_create(
                tutor=past_tutor, room=None, date=yesterday, start_time=time(9, 0), end_time=time(10, 0))
            Booking.objects.get_or_create(student=demo_student, slot=slot, defaults={'notes': 'Django models and migrations review'})
        upcoming_tutor = Tutor.objects.filter(display_name='Jordan Smith').first()
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
        # a pending request waiting on Alex Lee (who approves each booking)
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
        sample = [
            ('Jordan Smith', 5, 'Made the Django ORM finally click. Super patient.'),
            ('Jordan Smith', 4, 'Clear explanations and great practice exercises.'),
            ('Sam Rivera', 5, 'Helped me debug my algorithms assignment in one session.'),
            ('Casey Chen', 5, 'SQL tuning advice was detailed and kind.'),
            ('Alex Lee', 4, 'Good pacing for pointers and processes in C.'),
        ]
        for i, (tutor_name, rating, comment) in enumerate(sample):
            tutor = Tutor.objects.filter(display_name=tutor_name).first()
            if not tutor:
                continue
            user, made = User.objects.get_or_create(
                username=f'reviewer{i}@example.test',
                defaults={'email': f'reviewer{i}@example.test', 'first_name': ['Maya', 'Noah', 'Liam', 'Aisha', 'Ethan'][i], 'last_name': 'Demo'})
            if made:
                user.set_unusable_password()
                user.save()
            reviewer, _ = Student.objects.get_or_create(user=user)
            Review.objects.get_or_create(student=reviewer, tutor=tutor, defaults={'rating': rating, 'comment': comment})
