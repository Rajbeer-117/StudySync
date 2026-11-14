# StudySync

Book tutors and study rooms in seconds. Students search real-time availability, book instantly or request approval, message their tutor, reschedule, and get reminders. Tutors publish availability, approve requests and track their week.

## Features
- **Smart search**: keyword, subject, date, time, location, capacity, sort; pagination; Ctrl/⌘ + K command palette.
- **Race-safe booking**: database-level availability checks, atomic transactions and a unique active-booking constraint.
- **Approval workflow**: tutors can approve or decline each request; statuses Pending / Confirmed / Declined / Cancelled.
- **Rescheduling, cancellation, .ics calendar export** (with reminder alarm).
- **Booking messages** between student and tutor.
- **Notifications**: in-app bell and email; `send_reminders` command for 24h reminders.
- **Tutor studio**: recurring weekly availability, request inbox, 7-week session chart, public profile.
- **Reviews and favourites**, verified by completed sessions.
- **Email verification**: signed, expiring links; unverified accounts see a banner and cannot book until verified.
- **Waitlist** for full slots, with an email and notification when a place opens.
- **Weekly recurring bookings** (up to 6 weeks), skipping weeks that are taken.
- **No-show tracking**: tutors mark no-shows; three in 60 days pauses booking.
- **Session notes and meeting links** for online sessions, plus an Online/In person filter.
- **Analytics** for tutors, with CSV export (spreadsheet-formula safe).
- **Security**: login throttling, CSP, HSTS, secure cookies, CSRF, validated redirects, branded error pages.
- **Works everywhere**: responsive from 320px phones to 4K desktops; installable app (PWA) on Windows, macOS, Linux, Android and iOS; safe-area, touch-target and high-contrast support; offline page.
- **Design**: dark (black / cobalt, lime touches) and light (beige / sage, burgundy touches) liquid-glass themes.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # optional sample data
python manage.py runserver
```
Seed data uses real University of Windsor information. Rooms are the bookable Leddy Library study rooms (group rooms 218C/D, 318A-D, 206-209, 310, 311 and 4111C for four people, plus personal study rooms), with equipment and booking rules copied from leddy.uwindsor.ca. Tutors are ten School of Computer Science faculty members; their titles, offices and research interests come from their public profile pages. The office-hour slots and sample bookings are illustrative, and the faculty have not taken part in building this app.

Logins (password `Demo12345!`): `student@example.test`; `tutor@example.test` (Dr. Ziad Kobti) and `advisor@example.test` (Dr. Olena Syrotkina), who both approve requests. Local development only.

## Production
```bash
cp .env.example .env     # set DJANGO_SECRET_KEY, ALLOWED_HOSTS, passwords
docker compose up -d --build
```
This starts gunicorn + PostgreSQL + Redis and an hourly reminder worker. Without Docker: `pip install psycopg[binary] redis`, set the variables in `.env.example`, then `python manage.py collectstatic --noinput && python manage.py migrate && gunicorn studysync.wsgi -c gunicorn.conf.py`. Static files are served by WhiteNoise; `/healthz/` is the health probe. Verify with `DJANGO_DEBUG=0 python manage.py check --deploy`.

## Tests
`python manage.py test` (75 tests).
