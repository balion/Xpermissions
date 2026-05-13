# Admin Xpermisions

A Django 5.2 web application for managing users, roles, permissions, projects, and email templates. Provides both a classic HTML interface (Django views + Bootstrap) and a REST API (DRF + JWT).

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5.2 |
| REST API | Django REST Framework 3.15, SimpleJWT |
| Database | PostgreSQL 16 (dev: SQLite) |
| Email | MJML templates |
| API docs | drf-spectacular (Swagger / ReDoc) |
| Static files | WhiteNoise |

---

## Project structure

```
admin_Xpermisions/
├── backend/                  # Django project root
│   ├── apps/
│   │   ├── accounts/         # Users (custom User model)
│   │   ├── roles/            # Roles, module and project permissions
│   │   ├── projects/         # External projects
│   │   ├── email_templates/  # MJML templates + project actions
│   │   ├── audit/            # Audit log
│   │   └── core/             # Shared models (TimestampedModel)
│   ├── api/                  # DRF ViewSets and serializers
│   ├── config/               # settings/, urls.py, wsgi.py
│   ├── templates/            # HTML templates
│   ├── static/               # CSS / JS
│   └── tests/                # Pytest test suite
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── requirements_dev.txt
└── .env                      # (see Configuration section)
```

---

## Quick start (local development)

### 1. Virtual environment and dependencies

```bash
cd admin_Xpermisions
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_dev.txt
```

### 2. Configuration

Create a `.env` file in `admin_Xpermisions/` (or export variables manually):

```env
SECRET_KEY=django-insecure-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# SQLite is used by default in dev — no DB_* vars needed
# For PostgreSQL uncomment:
# DB_NAME=admin_Xpermisions
# DB_USER=postgres
# DB_PASSWORD=postgres
# DB_HOST=localhost
# DB_PORT=5432

EMAIL_BACKEND=django.core.mail.backends.Xpermisions.EmailBackend
```

### 3. Migrations and superuser

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run the development server

```bash
python manage.py runserver
```

The application will be available at **http://localhost:8000**.

| URL | Description |
|---|---|
| `/` | Redirects to dashboard |
| `/accounts/login/` | Login |
| `/dashboard/` | Main dashboard |
| `/users/` | User management |
| `/roles/` | Roles and permissions |
| `/projects/` | External projects |
| `/email-templates/` | Email templates |
| `/audit/` | Audit log |
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |

---

## Running with Docker

```bash
cd admin_Xpermisions

# Start database + web server
docker compose -f docker/docker-compose.yml up --build

# Database only (if you want to run the dev server locally)
docker compose -f docker/docker-compose.yml up db
```

Migrations and `collectstatic` run automatically on container startup.

---

## Tests

Tests are run from the `backend/` directory. SQLite is used automatically (configured in `pytest.ini`).

```bash
cd backend

# Run all tests
pytest tests/

# Verbose output
pytest tests/ -v

# Single file
pytest tests/test_roles_services.py

# Single class or test
pytest tests/test_api_auth.py::TestLoginView::test_valid_credentials_returns_tokens

# With code coverage
coverage run -m pytest tests/
coverage report
coverage html   # output at htmlcov/index.html
```

### Test modules

| File | Covers |
|---|---|
| `test_roles_services.py` | `check_module_permission`, `check_project_permission`, `get_accessible_projects` |
| `test_api_auth.py` | Login, token refresh, /me endpoint |
| `test_api_users.py` | User CRUD, `set_password` validation |
| `test_api_roles.py` | Role CRUD, `user_count` annotation, UserPermissionOverride |
| `test_api_projects.py` | Project CRUD, write-only `api_key` |
| `test_api_permissions.py` | `ModuleAPIPermission`, `IsSuperadminOrReadOnly` |
| `test_email_templates.py` | MJML compilation, email sending, `send_project_action_email` |
| `test_audit.py` | `log_model_change`, `log_auth_event`, IP address handling |
| `test_forms.py` | `UserCreateForm`, `UserUpdateForm`, `RolePermissionsForm`, `ProjectEmailActionsForm` |

---

## Pylint

Configuration lives in `.pylintrc` at the `admin_Xpermisions/` root. Run from the `backend/` directory:

```bash
cd backend
pylint --rcfile=../.pylintrc apps/ api/
```

Target score: **10.00/10**.

Key settings in `.pylintrc`:

- `load-plugins=pylint_django` — Django-aware checks
- `django-settings-module=config.settings.dev`
- `ignore-paths=.*/migrations/.*` — migrations are excluded
- `max-line-length=120`

---

## REST API

All protected endpoints require a JWT Bearer token.

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}'

# Call a protected endpoint
curl http://localhost:8000/api/users/ \
  -H "Authorization: Bearer <access_token>"
```

Full endpoint documentation: **http://localhost:8000/api/docs/**
