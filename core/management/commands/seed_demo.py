"""Idempotent seed data for local development.

Rooms are the University of Windsor Leddy Library study rooms listed at leddy.uwindsor.ca.
Tutors are School of Computer Science faculty; titles, offices and research interests are copied from their
public profile pages. Office-hour slots and the sample bookings are illustrative only.
"""
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from core import services
from core.models import AvailabilitySlot, Booking, BookingMessage, Room, Student, Tutor, WaitlistEntry

User = get_user_model()

PROFILE_BASE = 'https://www.uwindsor.ca/science/computerscience/'
# (name, subjects, location, title, office, research interests, profile path, weekday 1=Tue 3=Thu, hour)
FACULTY = [
    ('Dr. Prashanth Cheluvasai Ranga', 'Systems Programming, Operating Systems, Database Design, High-Performance Computing, Algorithms',
     '300 Ouellette', 'Assistant Professor', '4011, 300 Ouellette',
     'Systems programming; operating systems; database design; high-performance computing; design and analysis of algorithms.',
     '242400/dr-prashanth-cheluvasai-ranga', 1, 13),
    ('Dr. Kalyani Selvarajah', 'Computer Science', '300 Ouellette', 'Assistant Professor', '4033, 300 Ouellette', '',
     '242401/dr-kalyani-selvarajah', 3, 13),
    ('Dr. Ziad Kobti', 'Evolutionary Computation, Multi-Agent Simulation, Decision Support, Social Network Analysis',
     'Lambton Tower', 'Professor and Director, School of Computer Science', 'L.T. 5116 / 300 Ouellette 4007',
     'Evolutionary computation (genetic and cultural algorithms, co-evolution, PSO); multi-agent simulation of artificial human societies; '
     'decision support systems in health care and safety; social network analysis.', '1060/dr-ziad', 1, 14),
    ('Dr. Aznam Yacoub', 'Cognitive Modelling, Computational Intelligence, Evolutionary Algorithms, Systems Engineering',
     '300 Ouellette', 'Assistant Professor', '4017, 300 Ouellette',
     'Cognitive modelling and computing; computational intelligence and decision-making; evolutionary algorithms; software and system engineering methodologies; '
     'modelling and simulation of complex smart and cyber systems; formal modelling and checking; knowledge representation and reasoning; '
     'robotics and cybernetics; human-computer interaction; metaverse design and integration.', '242402/dr-aznam-yacoub', 3, 14),
    ('Dr. Shaoquan Jiang', 'Network Security, Blockchain, Cryptographic Protocols, Post-Quantum Security',
     '300 Ouellette', 'Assistant Professor', '4024, 300 Ouellette',
     'Network security; blockchain; cryptographic protocols; quantum and post-quantum security; cyber security education.',
     '242398/dr-shaoquan-jiang', 1, 15),
    ('Dr. Boubakeur Boufama', 'Computer Vision, Image Processing, Computer Graphics, Pattern Recognition',
     'Lambton Tower', 'Professor', 'L.T. 8113',
     'Computer vision; image processing; computer graphics; three-dimensional computer vision; pattern recognition.',
     '1059/dr-boubakeur-boufama', 3, 15),
    ('Dr. Olena Syrotkina', 'Machine Learning, Data Mining, Big Data Analytics, Discrete Mathematics',
     'Lambton Tower', 'Professor', 'Lambton Tower',
     'SCADA diagnostics; big data analytics and data mining; discrete mathematics; machine learning algorithms.',
     '318557/dr-olena-syrotkina', 1, 16),
    ('Dr. Imran Ahmad', 'Computer Science', 'Lambton Tower', 'Professor', '8114, Lambton Tower', '',
     '1064/dr-imran-ahmad', 3, 16),
    ('Dr. Christie Ezeife', 'Data Mining, Database Systems, Recommendation Systems, Social Network Analysis',
     'Lambton Tower', 'Professor', '5103, Lambton Tower',
     'Physical design of database and warehouse systems; sequential pattern mining; recommendation systems for the web, e-commerce and education; social network analysis.',
     '1062/dr-christie-ezeife', 1, 11),
    ('Dr. Luis Rueda', 'Machine Learning, Deep Learning, Bioinformatics, Data Security',
     'Lambton Tower', 'Professor', '5110, Lambton Tower',
     'Machine learning, pattern recognition and deep learning; computational biology and bioinformatics; biological knowledge discovery; data security and user authentication.',
     '1033/dr-luis-rueda', 3, 11),
]
FACULTY_NAMES = [row[0] for row in FACULTY]

GROUP_RULES = 'Group study room for up to 4 people. Up to 3 hours per day, bookable up to 30 days ahead.'
# Leddy Library bookable rooms and the equipment listed for each (leddy.uwindsor.ca/spaces-bookings/study-rooms)
ROOMS = [
    ('Group Study Room 218C', 'Leddy Library', 4, 'Blackboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 218D', 'Leddy Library', 4, 'Blackboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 318A', 'Leddy Library', 4, 'Blackboard, Whiteboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 318B', 'Leddy Library', 4, 'Blackboard, Whiteboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 318C', 'Leddy Library', 4, 'Blackboard, Whiteboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 318D', 'Leddy Library', 4, 'Blackboard, Whiteboard', 'Leddy Library main building. ' + GROUP_RULES),
    ('Group Study Room 206', 'Leddy Library', 4, 'Whiteboard', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 207', 'Leddy Library', 4, 'Display Screen, Whiteboard', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 208', 'Leddy Library', 4, '', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 209', 'Leddy Library', 4, 'Whiteboard', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 310', 'Leddy Library', 4, 'Whiteboard', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 311', 'Leddy Library', 4, 'Whiteboard', 'Leddy Library west building. ' + GROUP_RULES),
    ('Group Study Room 4111C', 'Leddy Library', 4, 'Key from the Information Desk', 'Sign out the key at the Information Desk. ' + GROUP_RULES),
    ('Personal Study Rooms, 2nd Floor', 'Leddy Library', 1, '', 'Quiet single-person rooms for personal use only. Up to 3 hours per booking, bookable up to 30 days ahead.'),
    ('Personal Study Rooms, 3rd Floor', 'Leddy Library', 1, '', 'Quiet single-person rooms for personal use only. Up to 3 hours per booking, bookable up to 30 days ahead.'),
]


def _purge_tutor(tutor):
    """Bookings protect their slots, so clear them before removing a tutor."""
    Booking.objects.filter(slot__tutor=tutor).delete()
    AvailabilitySlot.objects.filter(tutor=tutor).delete()
    tutor.delete()


class Command(BaseCommand):
    help = 'Create sample StudySync users, faculty tutors, Leddy Library rooms, and upcoming availability.'

    def handle(self, *args, **options):
        self._remove_old_people_and_rooms()
        student, made = User.objects.get_or_create(
            username='student@example.test', defaults={'email': 'student@example.test', 'first_name': 'Taylor', 'last_name': 'Morgan'})
        if made:
            student.set_password('Demo12345!')
            student.save()
        Student.objects.get_or_create(user=student, defaults={'bio': 'Master of Applied Computing (MAC) student, University of Windsor.'})

        logins = {'Dr. Ziad Kobti': ('tutor@example.test', 'Ziad', 'Kobti'), 'Dr. Olena Syrotkina': ('advisor@example.test', 'Olena', 'Syrotkina')}
        users = {}
        for name, (email, first, last) in logins.items():
            user, made = User.objects.get_or_create(username=email, defaults={'email': email, 'first_name': first, 'last_name': last})
            if made:
                user.set_password('Demo12345!')
            user.first_name, user.last_name = first, last
            user.save()
            users[name] = user

        for name, subjects, location, title, office, interests, path, weekday, hour in FACULTY:
            bio = f'{title}, School of Computer Science, University of Windsor. Office: {office}.'
            if interests:
                bio += f' Research interests: {interests}'
            bio += f' Profile: {PROFILE_BASE}{path}'
            tutor, _ = Tutor.objects.get_or_create(display_name=name, defaults={'subjects': subjects, 'location': location, 'bio': bio})
            tutor.subjects, tutor.location, tutor.bio = subjects, location, bio
            tutor.requires_approval, tutor.meeting_url = True, ''
            if name in users:
                tutor.user = users[name]
            tutor.save()
            first_day = timezone.localdate() + timedelta(days=1)
            for week in range(5):
                day = first_day + timedelta(days=(weekday - first_day.weekday()) % 7 + 7 * week)
                AvailabilitySlot.objects.get_or_create(tutor=tutor, room=None, date=day, start_time=time(hour, 0), end_time=time(hour + 1, 0))

        for name, building, capacity, amenities, description in ROOMS:
            room, _ = Room.objects.get_or_create(name=name, building=building, defaults={'capacity': capacity})
            room.capacity, room.amenities, room.description, room.is_active = capacity, amenities, description, True
            room.save()

        count = 0
        starts = [time(10, 0), time(11, 30), time(14, 0), time(15, 30), time(9, 0), time(17, 0)]
        ends = [time(11, 0), time(12, 30), time(15, 0), time(16, 30), time(10, 0), time(18, 0)]
        for delta in range(1, 15):
            day = timezone.localdate() + timedelta(days=delta)
            if day.weekday() == 6:
                continue
            slots = list(zip(starts[:2], ends[:2])) if day.weekday() == 5 else list(zip(starts, ends))
            for room in Room.objects.filter(is_active=True):
                for start, end in slots:
                    _, created = AvailabilitySlot.objects.get_or_create(room=room, tutor=None, date=day, start_time=start, end_time=end)
                    count += int(created)
        self._seed_history(student, users)
        self._seed_activity()
        self.stdout.write(self.style.SUCCESS(f'Ready; added {count} room slots.'))
        self.stdout.write('Student: student@example.test / Demo12345!')
        self.stdout.write('Faculty (Dr. Ziad Kobti, approves requests): tutor@example.test / Demo12345!')
        self.stdout.write('Faculty (Dr. Olena Syrotkina, approves requests): advisor@example.test / Demo12345!')
        self.stdout.write(f'Totals: {Tutor.objects.count()} tutors, {Room.objects.count()} rooms, {AvailabilitySlot.objects.count()} slots, {Booking.objects.count()} bookings.')
        self.stdout.write('These credentials are for local development only.')

    def _remove_old_people_and_rooms(self):
        """Earlier seeds used invented tutors, Group 11 members, '(Demo)' profiles and made-up rooms; remove them."""
        for tutor in Tutor.objects.exclude(display_name__in=FACULTY_NAMES):
            _purge_tutor(tutor)
        User.objects.filter(username='alex@example.test').delete()
        keep = [(r[0], r[1]) for r in ROOMS]
        for room in Room.objects.all():
            if (room.name, room.building) not in keep:
                Booking.objects.filter(slot__room=room).delete()
                AvailabilitySlot.objects.filter(room=room).delete()
                room.delete()

    def _seed_activity(self):
        """Sample past bookings (completed, cancelled, no-show) on the two login accounts, plus a full slot with a waitlist."""
        marker = '[demo-activity]'
        if Booking.objects.filter(notes=marker).exists():
            return
        people = []
        for i in range(12):
            u, made = User.objects.get_or_create(username=f'learner{i}@example.test', defaults={
                'email': f'learner{i}@example.test', 'first_name': f'Learner{i}', 'last_name': 'Sample'})
            if made:
                u.set_unusable_password()
                u.save()
            people.append(Student.objects.get_or_create(user=u, defaults={'bio': 'MAC student, University of Windsor.'})[0])
        pattern = ['confirmed'] * 6 + ['cancelled', 'no_show', 'confirmed', 'declined', 'confirmed', 'no_show']
        hours = [(9, 10), (10, 11), (11, 12), (14, 15), (15, 16), (10, 11), (14, 15), (9, 10), (15, 16), (11, 12), (14, 15), (10, 11)]
        n = 0
        for name in ('Dr. Ziad Kobti', 'Dr. Olena Syrotkina'):
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
                Booking.objects.create(student=student_row, slot=slot, notes=marker if n == 0 and k == 0 else 'Sample history',
                                       status={'no_show': Booking.NO_SHOW, 'declined': Booking.DECLINED,
                                               'cancelled': Booking.CANCELLED}.get(status, Booking.CONFIRMED))
            n += 1
        target = Tutor.objects.filter(display_name='Dr. Ziad Kobti').first()
        if target:
            full = services.available_slots(AvailabilitySlot.objects.filter(tutor=target)).order_by('date', 'start_time').first()
            if full:
                Booking.objects.create(student=people[0], slot=full, status=Booking.CONFIRMED, notes='Sample full slot')
                WaitlistEntry.objects.get_or_create(student=people[1], slot=full)

    def _seed_history(self, demo_user, users):
        """A finished session and an upcoming one for the demo student, plus a pending request for the approver."""
        demo_student = Student.objects.get(user=demo_user)
        kobti = Tutor.objects.filter(display_name='Dr. Ziad Kobti').first()
        syrotkina = Tutor.objects.filter(display_name='Dr. Olena Syrotkina').first()
        yesterday = timezone.localdate() - timedelta(days=1)
        if kobti:
            slot, _ = AvailabilitySlot.objects.get_or_create(
                tutor=kobti, room=None, date=yesterday, start_time=time(9, 0), end_time=time(10, 0))
            Booking.objects.get_or_create(student=demo_student, slot=slot, defaults={'notes': 'Project scope discussion'})
        if syrotkina:
            nxt = AvailabilitySlot.objects.filter(
                tutor=syrotkina, is_active=True, date__gt=timezone.localdate()).order_by('date', 'start_time').first()
            if nxt and not Booking.objects.filter(student=demo_student, status=Booking.CONFIRMED, slot__date__gte=timezone.localdate()).exists():
                booking, made = Booking.objects.get_or_create(
                    student=demo_student, slot=nxt, defaults={'notes': 'Machine learning course project topic'})
                if made:
                    services.notify_booking(booking, 'confirmed')
                    BookingMessage.objects.create(booking=booking, sender=demo_user, body='Hi! Could we talk about choosing a project topic?')
        if kobti:
            pending_slot = services.available_slots(AvailabilitySlot.objects.filter(tutor=kobti)).first()
            ru, made = User.objects.get_or_create(username='maya@example.test', defaults={'email': 'maya@example.test', 'first_name': 'Maya', 'last_name': 'Sample'})
            if made:
                ru.set_unusable_password()
                ru.save()
            requester, _ = Student.objects.get_or_create(user=ru)
            if pending_slot and not Booking.objects.filter(student=requester, status=Booking.PENDING).exists():
                req = Booking.objects.create(student=requester, slot=pending_slot, status=Booking.PENDING, notes='Question about the MAC internship course')
                services.notify_booking(req, 'requested')
