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
- **Security**: login throttling, CSP, HSTS, secure cookies, CSRF, validated redirects, branded error pages.
- **Design**: dark (black / cobalt, lime touches) and light (beige / sage, burgundy touches) liquid-glass themes.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # optional sample data
python manage.py runserver
```
Demo logins (password `Demo12345!`): `student@example.test`, `tutor@example.test`, `alex@example.test` (approves each request). Create an admin with `python manage.py createsuperuser` (site at `/admin/`).

## Production
```bash
cp .env.example .env     # set DJANGO_SECRET_KEY, ALLOWED_HOSTS, passwords
docker compose up -d --build
```
This starts gunicorn + PostgreSQL + Redis and an hourly reminder worker. Without Docker: `pip install psycopg[binary] redis`, set the variables in `.env.example`, then `python manage.py collectstatic --noinput && python manage.py migrate && gunicorn studysync.wsgi -c gunicorn.conf.py`. Static files are served by WhiteNoise; `/healthz/` is the health probe. Verify with `DJANGO_DEBUG=0 python manage.py check --deploy`.

## Tests
`python manage.py test` (39 tests).
