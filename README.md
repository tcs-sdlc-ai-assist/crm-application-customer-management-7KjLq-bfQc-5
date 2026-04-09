# CRM Application

A comprehensive Customer Relationship Management system built with Python and Django.

## Tech Stack

- **Backend:** Python 3.11+, Django 4.2+
- **API:** Django REST Framework
- **Database:** PostgreSQL (recommended) / SQLite (development)
- **Authentication:** Django built-in auth + DRF token authentication
- **Testing:** pytest, pytest-django

## Folder Structure

```
crm-app/
├── config/                  # Project-level settings and root URL configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                # User authentication and profile management
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── contacts/                # Contact management module
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── leads/                   # Lead tracking and conversion
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── deals/                   # Deal/opportunity pipeline management
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── tasks/                   # Task and activity management
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── analytics/               # Reporting and dashboard analytics
│   ├── views.py
│   ├── urls.py
│   └── tests/
├── templates/               # Django HTML templates
├── static/                  # Static assets (CSS, JS, images)
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- PostgreSQL 14+ (for production) or SQLite (for development)
- Git
- virtualenv or venv

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd crm-app
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key (required) | — |
| `DEBUG` | Enable debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `localhost,127.0.0.1` |
| `DATABASE_URL` | Database connection string | `sqlite:///db.sqlite3` |
| `DB_NAME` | PostgreSQL database name | `crm_db` |
| `DB_USER` | PostgreSQL database user | `crm_user` |
| `DB_PASSWORD` | PostgreSQL database password | — |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `EMAIL_HOST` | SMTP email host | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP email port | `587` |
| `EMAIL_HOST_USER` | SMTP email user | — |
| `EMAIL_HOST_PASSWORD` | SMTP email password | — |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:3000` |

### 5. Database Setup

#### Using PostgreSQL (recommended for production):

```bash
# Create the database and user
psql -U postgres
CREATE DATABASE crm_db;
CREATE USER crm_user WITH PASSWORD 'your_password';
ALTER ROLE crm_user SET client_encoding TO 'utf8';
ALTER ROLE crm_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE crm_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE crm_db TO crm_user;
\q
```

#### Using SQLite (for development):

No additional setup is required. SQLite will be used by default if `DATABASE_URL` is not set.

### 6. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create a Superuser

```bash
python manage.py createsuperuser
```

### 8. Seed Data (Optional)

Load sample data for development:

```bash
python manage.py loaddata fixtures/sample_data.json
```

Or use the custom management command:

```bash
python manage.py seed_data
```

### 9. Start the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`.

- **Admin Panel:** `http://localhost:8000/admin/`
- **API Root:** `http://localhost:8000/api/v1/`

## Usage Guide

### Accounts Module

Manage user registration, authentication, and profiles.

- Register new users and assign roles (Admin, Manager, Sales Rep)
- Token-based authentication for API access
- User profile management with avatar and contact details

### Contacts Module

Manage customer and prospect contact information.

- Create, view, update, and delete contacts
- Associate contacts with companies/organizations
- Track communication history and notes
- Filter and search contacts by name, email, company, or tags

### Leads Module

Track and manage sales leads through the qualification pipeline.

- Capture leads from multiple sources (web forms, email, manual entry)
- Assign leads to sales representatives
- Track lead status: New → Contacted → Qualified → Converted → Lost
- Convert qualified leads into deals

### Deals Module

Manage the sales pipeline and deal lifecycle.

- Create and track deals through pipeline stages
- Pipeline stages: Prospecting → Qualification → Proposal → Negotiation → Closed Won / Closed Lost
- Associate deals with contacts and companies
- Track deal value, expected close date, and probability
- Pipeline view with drag-and-drop stage management

### Tasks Module

Manage activities, follow-ups, and reminders.

- Create tasks linked to contacts, leads, or deals
- Set due dates, priorities, and assignees
- Task types: Call, Email, Meeting, Follow-up, Other
- Track task completion status and overdue items

### Analytics Module

Dashboard and reporting for sales performance insights.

- Sales pipeline overview with deal values by stage
- Lead conversion rates and source analysis
- Revenue forecasts and trends
- Team performance metrics
- Activity reports and task completion rates

## API Endpoints Reference

All API endpoints are prefixed with `/api/v1/`.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register/` | Register a new user |
| POST | `/api/v1/auth/login/` | Obtain auth token |
| POST | `/api/v1/auth/logout/` | Revoke auth token |
| GET | `/api/v1/auth/profile/` | Get current user profile |
| PUT | `/api/v1/auth/profile/` | Update current user profile |

### Contacts

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/contacts/` | List all contacts |
| POST | `/api/v1/contacts/` | Create a new contact |
| GET | `/api/v1/contacts/{id}/` | Retrieve a contact |
| PUT | `/api/v1/contacts/{id}/` | Update a contact |
| PATCH | `/api/v1/contacts/{id}/` | Partially update a contact |
| DELETE | `/api/v1/contacts/{id}/` | Delete a contact |
| GET | `/api/v1/contacts/{id}/notes/` | List notes for a contact |
| POST | `/api/v1/contacts/{id}/notes/` | Add a note to a contact |

### Leads

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/leads/` | List all leads |
| POST | `/api/v1/leads/` | Create a new lead |
| GET | `/api/v1/leads/{id}/` | Retrieve a lead |
| PUT | `/api/v1/leads/{id}/` | Update a lead |
| PATCH | `/api/v1/leads/{id}/` | Partially update a lead |
| DELETE | `/api/v1/leads/{id}/` | Delete a lead |
| POST | `/api/v1/leads/{id}/convert/` | Convert a lead to a deal |

### Deals

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/deals/` | List all deals |
| POST | `/api/v1/deals/` | Create a new deal |
| GET | `/api/v1/deals/{id}/` | Retrieve a deal |
| PUT | `/api/v1/deals/{id}/` | Update a deal |
| PATCH | `/api/v1/deals/{id}/` | Partially update a deal |
| DELETE | `/api/v1/deals/{id}/` | Delete a deal |
| GET | `/api/v1/deals/pipeline/` | Get pipeline summary |

### Tasks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/tasks/` | List all tasks |
| POST | `/api/v1/tasks/` | Create a new task |
| GET | `/api/v1/tasks/{id}/` | Retrieve a task |
| PUT | `/api/v1/tasks/{id}/` | Update a task |
| PATCH | `/api/v1/tasks/{id}/` | Partially update a task |
| DELETE | `/api/v1/tasks/{id}/` | Delete a task |
| POST | `/api/v1/tasks/{id}/complete/` | Mark a task as complete |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/analytics/dashboard/` | Get dashboard summary |
| GET | `/api/v1/analytics/pipeline/` | Get pipeline analytics |
| GET | `/api/v1/analytics/leads/` | Get lead analytics |
| GET | `/api/v1/analytics/revenue/` | Get revenue analytics |
| GET | `/api/v1/analytics/team/` | Get team performance |

### Filtering and Pagination

All list endpoints support:

- **Pagination:** `?page=1&page_size=25`
- **Search:** `?search=keyword`
- **Ordering:** `?ordering=-created_at` (prefix with `-` for descending)
- **Filtering:** `?status=active&assigned_to=1`

## Testing

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run Tests for a Specific Module

```bash
pytest contacts/tests/
pytest leads/tests/
pytest deals/tests/
pytest tasks/tests/
pytest accounts/tests/
```

### Run a Specific Test

```bash
pytest contacts/tests/test_models.py::test_contact_str_returns_full_name
```

### Test Configuration

Tests are configured in `pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## Deployment Notes

### Production Checklist

1. **Set `DEBUG=False`** in environment variables
2. **Set a strong `SECRET_KEY`** — generate one with:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
3. **Configure `ALLOWED_HOSTS`** with your domain(s)
4. **Use PostgreSQL** as the production database
5. **Collect static files:**
   ```bash
   python manage.py collectstatic --noinput
   ```
6. **Run migrations:**
   ```bash
   python manage.py migrate --noinput
   ```
7. **Use Gunicorn** as the WSGI server:
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
   ```
8. **Set up a reverse proxy** (Nginx recommended) in front of Gunicorn
9. **Enable HTTPS** with a valid SSL certificate
10. **Configure CORS** for your frontend domain(s)
11. **Set up logging** to file or external service
12. **Configure email backend** for notifications

### Docker Deployment

```bash
docker build -t crm-app .
docker run -p 8000:8000 --env-file .env crm-app
```

### Environment-Specific Settings

- **Development:** `DEBUG=True`, SQLite, console email backend
- **Staging:** `DEBUG=False`, PostgreSQL, SMTP email backend
- **Production:** `DEBUG=False`, PostgreSQL, SMTP email backend, HTTPS enforced

## License

**Private** — All rights reserved. This software is proprietary and confidential. Unauthorized copying, distribution, or modification is strictly prohibited.