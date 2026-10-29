"""Idempotent demo-only seed data. All people and rooms below are fictional."""
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from core import services
from core.models import AvailabilitySlot, Booking, BookingMessage, Review, Room, Student, Tutor

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample StudySync users, tutors, rooms, and upcoming availability.'

    def handle(self, *args, **options):
        student, made = User.objects.get_or_create(
            username='student@example.test', defaults={'email': 'student@example.test', 'first_name': 'Taylor', 'last_name': 'Morgan'}
        )
        if made:
            student.set_password('Demo12345!')
            student.save()
        Student.objects.get_or_create(user=student)

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

        tutors = [
            ('Jordan Smith', 'Mathematics, Statistics', 'Leddy Library', 'Calculus, linear algebra, and statistics study support.'),
            ('Alex Lee', 'Physics, Mathematics', 'Science Building', 'Mechanics and introductory physics tutoring.'),
            ('Sam Rivera', 'Computer Science, Mathematics', 'Erie Hall', 'Python, Java, algorithms, and discrete mathematics.'),
            ('Casey Chen', 'Chemistry, Writing', 'Leddy Library', 'Chemistry concepts and scientific writing help.'),
        ]
        for i, (name, subjects, location, bio) in enumerate(tutors):
            tutor, _ = Tutor.objects.get_or_create(display_name=name, defaults={
                'user': tutor_user if i == 0 else None,
                'subjects': subjects, 'location': location, 'bio': bio,
            })
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
        ]
        for name, building, capacity, amenities, description in rooms:
            Room.objects.get_or_create(name=name, building=building, defaults={
                'capacity': capacity, 'amenities': amenities, 'description': description,
            })

        count = 0
        starts = [time(10, 0), time(11, 30), time(14, 0), time(15, 30)]
        ends = [time(11, 0), time(12, 30), time(15, 0), time(16, 30)]
        for delta in range(1, 11):
            day = timezone.localdate() + timedelta(days=delta)
            if day.weekday() >= 5:  # keep the demo on weekdays
                continue
            for tutor in Tutor.objects.filter(is_active=True):
                for start, end in zip(starts[:3], ends[:3]):
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
        self._seed_history(student)
        self.stdout.write(self.style.SUCCESS(f'Demo ready; added {count} availability slots.'))
        self.stdout.write('Student: student@example.test / Demo12345!')
        self.stdout.write('Tutor:   tutor@example.test / Demo12345!')
        self.stdout.write('Tutor (approves requests): alex@example.test / Demo12345!')
        self.stdout.write('These credentials and demo data are for local development only.')

    def _seed_history(self, demo_user):
        """A finished session for the demo student (so the review flow works) plus sample reviews."""
        demo_student = Student.objects.get(user=demo_user)
        yesterday = timezone.localdate() - timedelta(days=1)
        past_tutor = Tutor.objects.filter(display_name='Alex Lee').first()
        if past_tutor:
            slot, _ = AvailabilitySlot.objects.get_or_create(
                tutor=past_tutor, room=None, date=yesterday, start_time=time(9, 0), end_time=time(10, 0))
            Booking.objects.get_or_create(student=demo_student, slot=slot, defaults={'notes': 'Newton\'s laws review'})
        upcoming_tutor = Tutor.objects.filter(display_name='Jordan Smith').first()
        if upcoming_tutor:
            nxt = AvailabilitySlot.objects.filter(
                tutor=upcoming_tutor, is_active=True, date__gt=timezone.localdate()).order_by('date', 'start_time').first()
            if nxt and not Booking.objects.filter(student=demo_student, status=Booking.CONFIRMED, slot__date__gte=timezone.localdate()).exists():
                booking, made = Booking.objects.get_or_create(
                    student=demo_student, slot=nxt, defaults={'notes': 'Linear algebra: eigenvalues'})
                if made:
                    services.notify_booking(booking, 'confirmed')
                    BookingMessage.objects.create(booking=booking, sender=demo_user, body='Hi! Could we focus on eigenvalues and diagonalization?')
                    BookingMessage.objects.create(booking=booking, sender=upcoming_tutor.user, body='Absolutely. Bring the practice set and we will work through it.')
        # a pending request waiting on Alex Lee (who approves each booking)
        if past_tutor:
            nxt_alex = services.available_slots(AvailabilitySlot.objects.filter(tutor=past_tutor)).first()
            ru, made = User.objects.get_or_create(username='maya@example.test', defaults={'email': 'maya@example.test', 'first_name': 'Maya', 'last_name': 'Demo'})
            if made:
                ru.set_unusable_password()
                ru.save()
            requester, _ = Student.objects.get_or_create(user=ru)
            if nxt_alex and requester and not Booking.objects.filter(student=requester, status=Booking.PENDING).exists():
                req = Booking.objects.create(student=requester, slot=nxt_alex, status=Booking.PENDING, notes='Help with projectile motion')
                services.notify_booking(req, 'requested')
        sample = [
            ('Jordan Smith', 5, 'Made linear algebra finally click. Super patient.'),
            ('Jordan Smith', 4, 'Clear explanations and great practice problems.'),
            ('Sam Rivera', 5, 'Helped me debug my algorithms assignment in one session.'),
            ('Casey Chen', 5, 'Lab-report feedback was detailed and kind.'),
            ('Alex Lee', 4, 'Good pacing for first-year mechanics.'),
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
