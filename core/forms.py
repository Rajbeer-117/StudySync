from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from datetime import timedelta
from .models import AvailabilitySlot, Review, Room, Student, Tutor

User = get_user_model()


class StyledFormMixin:
    """Bootstrap-free consistent native form styling."""
    def apply_styles(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'check-input'})
            elif isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.update({'class': 'role-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})


class RegistrationForm(UserCreationForm, StyledFormMixin):
    full_name = forms.CharField(max_length=120, label='Full name')
    email = forms.EmailField(max_length=150, label='University or personal email')
    role = forms.ChoiceField(choices=[('student', 'Student'), ('tutor', 'Tutor')], widget=forms.RadioSelect, initial='student', label='I am joining as')

    class Meta:
        model = User
        fields = ('full_name', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('username', None)
        self.apply_styles()
        self.fields['password1'].help_text = 'At least 8 characters. Avoid common passwords.'

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        parts = self.cleaned_data['full_name'].strip().split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
            if self.cleaned_data['role'] == 'tutor':
                Tutor.objects.create(user=user, display_name=user.get_full_name(), subjects='General study help')
            else:
                Student.objects.create(user=user)
        return user


class EmailLoginForm(AuthenticationForm, StyledFormMixin):
    username = forms.EmailField(label='Email address')
    remember_me = forms.BooleanField(required=False, label='Remember me for 14 days')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SearchForm(forms.Form, StyledFormMixin):
    TYPE_CHOICES = [('', 'Tutors & rooms'), ('tutor', 'Tutors'), ('room', 'Study rooms')]
    SORT_CHOICES = [('', 'Best match'), ('rating', 'Top rated'), ('name', 'Name A–Z')]
    CAPACITY_CHOICES = [('', 'Any size'), ('2', '2+ seats'), ('4', '4+ seats'), ('6', '6+ seats')]
    WHEN_CHOICES = [('', 'Any time frame'), ('today', 'Open today'), ('week', 'Next 7 days')]

    kind = forms.ChoiceField(choices=TYPE_CHOICES, required=False, label='Category')
    q = forms.CharField(required=False, max_length=90, label='Keyword',
                        widget=forms.TextInput(attrs={'placeholder': 'Name, subject, building…', 'autocomplete': 'off'}))
    subject = forms.ChoiceField(choices=[('', 'Any subject')], required=False)
    date = forms.ChoiceField(required=False, choices=[('', 'Any date')], label='Date')
    time = forms.ChoiceField(required=False, choices=[('', 'Any time')], label='Time')
    location = forms.ChoiceField(required=False, choices=[('', 'Any location')], label='Location')
    when = forms.ChoiceField(required=False, choices=WHEN_CHOICES, label='Availability')
    capacity = forms.ChoiceField(required=False, choices=CAPACITY_CHOICES, label='Room size')
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, label='Sort by')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Choices reflect live data so every option returns something real.
        upcoming = AvailabilitySlot.objects.filter(is_active=True, date__gte=timezone.localdate())
        dates = upcoming.order_by('date').values_list('date', flat=True).distinct()[:40]
        times = upcoming.order_by('start_time').values_list('start_time', flat=True).distinct()
        locations = set(Tutor.objects.filter(is_active=True).values_list('location', flat=True))
        locations.update(Room.objects.filter(is_active=True).values_list('building', flat=True))
        subjects = set()
        for text in Tutor.objects.filter(is_active=True).values_list('subjects', flat=True):
            subjects.update(item.strip() for item in text.split(',') if item.strip())
        self.fields['subject'].choices = [('', 'Any subject')] + [(name, name) for name in sorted(subjects)]
        self.fields['date'].choices = [('', 'Any date')] + [(d.isoformat(), d.strftime('%a, %b %d')) for d in dates]
        self.fields['time'].choices = [('', 'Any time')] + [
            (t.strftime('%H:%M'), t.strftime('%I:%M %p').lstrip('0')) for t in times]
        self.fields['location'].choices = [('', 'Any location')] + [(x, x) for x in sorted(locations) if x]
        self.apply_styles()
        for name in ('kind', 'subject', 'date', 'time', 'location', 'when', 'capacity', 'sort'):
            self.fields[name].widget.attrs['data-filter-select'] = 'true'


class MessageForm(forms.Form, StyledFormMixin):
    body = forms.CharField(max_length=1000, label='Message', widget=forms.Textarea(
        attrs={'rows': 2, 'placeholder': 'Write a message…', 'maxlength': 1000}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write something first.')
        return body


class BookingNotesForm(forms.Form, StyledFormMixin):
    notes = forms.CharField(label='A note for your session (optional)', required=False,
                            max_length=750, widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'What would you like to work on?'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class AccountNameForm(forms.ModelForm, StyledFormMixin):
    class Meta:
        model = User
        fields = ('first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class StudentProfileForm(forms.ModelForm, StyledFormMixin):
    class Meta:
        model = Student
        fields = ('bio', 'photo', 'study_notes')
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class TutorProfileForm(forms.ModelForm, StyledFormMixin):
    class Meta:
        model = Tutor
        fields = ('display_name', 'subjects', 'location', 'bio', 'photo', 'requires_approval')
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}
        labels = {'requires_approval': 'Approve each booking request myself'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ReviewForm(forms.ModelForm, StyledFormMixin):
    rating = forms.TypedChoiceField(
        coerce=int, label='Your rating',
        choices=[(5, '5 – Excellent'), (4, '4 – Very good'), (3, '3 – Good'), (2, '2 – Fair'), (1, '1 – Poor')])

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        labels = {'comment': 'Share a few words (optional)'}
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What helped most in this session?'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SlotCreateForm(forms.Form, StyledFormMixin):
    """Tutor-managed availability: one slot, optionally repeated weekly."""
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='First date')
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Start')
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='End')
    repeat_weeks = forms.IntegerField(min_value=1, max_value=12, initial=1, label='Repeat weekly for (weeks)',
                                      help_text='1 = just this date.')

    def __init__(self, *args, tutor=None, **kwargs):
        self.tutor = tutor
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields['date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean(self):
        data = super().clean()
        day, start, end = data.get('date'), data.get('start_time'), data.get('end_time')
        if day and day < timezone.localdate():
            self.add_error('date', 'Choose today or a future date.')
        if start and end and start >= end:
            self.add_error('end_time', 'End time must be later than the start time.')
        if day and start and end and start < end and self.tutor:
            for week in range(data.get('repeat_weeks') or 1):
                target = day + timedelta(weeks=week)
                if AvailabilitySlot.objects.filter(
                        tutor=self.tutor, date=target, is_active=True,
                        start_time__lt=end, end_time__gt=start).exists():
                    self.add_error(None, f'You already have a slot overlapping {target:%b %d}. Adjust the time or remove it first.')
                    break
        return data

    def save(self):
        d = self.cleaned_data
        created = []
        for week in range(d['repeat_weeks']):
            created.append(AvailabilitySlot.objects.create(
                tutor=self.tutor, date=d['date'] + timedelta(weeks=week),
                start_time=d['start_time'], end_time=d['end_time']))
        return created
