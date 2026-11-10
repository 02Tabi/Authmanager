# Auth Manager

A centralized authentication and access-management service built with Django. Auth Manager is the single place where users are created, applications are registered, and permissions are granted and approved. Internal applications (such as the **Prepaid Transfer Portal**) do not manage passwords or roles themselves. They send the user's credentials to Auth Manager and receive back a verdict plus the role that user holds for that specific application.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [How it fits together](#how-it-fits-together)
3. [Key features](#key-features)
4. [Roles and permissions](#roles-and-permissions)
5. [Login API](#login-api)
6. [Data model](#data-model)
7. [Project structure](#project-structure)
8. [Tech stack](#tech-stack)
9. [Getting started](#getting-started)
10. [Configuration](#configuration)
11. [Connecting a new application](#connecting-a-new-application)
12. [Security notes](#security-notes)
13. [Troubleshooting](#troubleshooting)
14. [License](#license)

---

## What it does

Without a central service, every internal tool ends up with its own user table, its own passwords and its own idea of who is allowed to do what. Auth Manager replaces that with one source of truth:

- **One identity per person.** Staff sign in with their Active Directory credentials (or a local account where AD is not applicable).
- **Per-application access.** Having an account does not mean access to everything. A user must be granted a permission for each application they use.
- **Maker-checker control.** Permission grants go through an approval step, so one person cannot silently give themselves or others access.
- **Full traceability.** Every login attempt and every administrative action is recorded.

## How it fits together

```
   +-------------------+      POST /api/login/       +--------------------+
   |  Client app       | --------------------------> |   Auth Manager     |
   |  (e.g. Prepaid    |   username, password,       |                    |
   |   Transfer Portal)|   app_id                    |  - checks identity |
   |                   | <-------------------------- |    (AD or local)   |
   |                   |   permission_type, role     |  - checks app      |
   +-------------------+                             |    permission      |
                                                     |  - logs the attempt|
                                                     +--------------------+
                                                              |
                                                     Active Directory / DB
```

1. A user opens a client application and submits their username and password.
2. The client forwards them to Auth Manager together with its own `app_id`.
3. Auth Manager verifies the credentials, confirms the user holds an approved, active permission for that application, records the attempt, and replies.
4. The client creates its own local session and applies the returned permission (for example, showing Approve/Reject buttons to a checker).

## Key features

**Authentication**
- Active Directory (LDAP) and local-database authentication, chosen per user (`auth_type`).
- Account lockout after repeated failed attempts, with an admin action to reset the counter.
- Forced password reset and password-age tracking.
- Password history, to prevent reuse of recent passwords.
- One-time password (OTP) verification and secure set-password / activate-account flows.
- Session binding and an active-sessions view.

**Access management**
- Register applications with a unique `app_id`; applications go through an approval status of their own.
- Grant users a permission type per application: `maker`, `checker`, `admin` or `super_admin`.
- Approval workflow for permissions (`pending`, `approved`, `rejected`), recording who approved and when.
- Application access policies and a user access control screen for administrators.

**Monitoring and audit**
- **Login logs (AuthTrail):** username, application, success or failure, reason, IP address and user agent.
- **Audit log:** user created or deleted, user activated or deactivated, app created, approved, rejected or deleted, permission granted, revoked, approved or rejected, failed attempts reset, account locked, password changed.
- Dashboard with charts, a failed-attempts page and an active-sessions page.

**Notifications**
- Email notifications for events such as account activation and credential delivery, with background processing through Celery.

## Roles and permissions

Auth Manager has two separate concepts. Do not confuse them:

| Concept | Where | Purpose |
|---|---|---|
| **Profile role** (`admin`, `staff`, `manager`, `user`) | `Profile.user_role` | What the person can do **inside Auth Manager itself** |
| **Permission type** (`maker`, `checker`, `admin`, `super_admin`) | `Permission.permission_type` | What the person can do **inside a specific client application** |

Permission types, as used by client applications:

| Permission type | Typical meaning in a client app |
|---|---|
| `maker` | Can create or submit requests; cannot approve them |
| `checker` | Can review and approve or reject requests; cannot create them |
| `admin` | Administrative access in that application |
| `super_admin` | Full access across the application |

A permission only counts when it is **approved** and **active**. Pending or rejected permissions do not grant access.

> **Important for client developers:** read `permission_type` from the login response, **not** `role`. The `role` field is a free-text label that is often blank. Reading it instead of `permission_type` will make every user fall back to your default role.

## Login API

### `POST /api/login/`

**Request body (JSON)**

```json
{
  "username": "jdoe",
  "password": "********",
  "app_id": "PREPAID-PORTAL"
}
```

**Successful response (`200 OK`)**

```json
{
  "message": "Login successful",
  "permission_type": "checker",
  "role": ""
}
```

**Failed response (non-200)**

```json
{
  "message": "Invalid credentials. Please try again."
}
```

Failures include wrong credentials, a locked or inactive account, an unknown `app_id`, and a user with no approved permission for that application. Every attempt, successful or not, is written to the login log.

### Example client call (Python)

```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/api/login/",
    json={"username": username, "password": password, "app_id": "PREPAID-PORTAL"},
    timeout=5,
)

if response.status_code == 200:
    data = response.json()
    permission_type = data["permission_type"].lower().strip()   # maker / checker / admin / super_admin
else:
    error = response.json().get("message", "Login failed.")
```

## Data model

| Model | Purpose |
|---|---|
| `Authenticationtype` | Categories of application authentication |
| `Application` | A registered client app: name, unique `app_id`, description, approval status, type |
| `Profile` | Extra details for each Django user: name, email, phone, auth type (AD or DB), role, status, lock state, failed-attempt count, password-reset flags, last login and logout |
| `Permission` | Links a user to an application with a `permission_type`, an approval status, who approved it, and when |
| `AuthTrail` | One row per login attempt (success or failed) with IP and user agent |
| `AuditLog` | One row per administrative action, with who did it, the target and details |
| `PasswordHistory` | Hashes of previous passwords, used to block reuse |
| `OtpToken` | One-time codes for verification flows |

## Project structure

```
Auth1/
├── config/                  # Django project settings, URLs, ASGI/WSGI, Celery app
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── Middleware/              # Main application
│   ├── models.py            # Data model (see above)
│   ├── views.py             # Login API and admin dashboard views
│   ├── serializers.py       # DRF serializers
│   ├── urls.py / dashboard_urls.py
│   ├── decorators.py        # Access-control decorators
│   ├── audit.py             # Audit-log helpers
│   ├── session_binding.py   # Session binding and active sessions
│   ├── notification_service.py / notifications.py / tasks.py
│   ├── libs/ad.py           # Active Directory integration
│   ├── migrations/
│   ├── static/              # CSS, JS, images for the admin UI
│   └── templates/           # base, dashboard, charts, notifications, pages, portal
├── static/                  # Vendor assets (Chart.js, CoreUI, SimpleBar)
├── manage.py
├── requirements.txt
├── .env.example             # Template for required environment variables
└── .gitignore
```

## Tech stack

- **Python** 3.12+ and **Django** 6.x
- **Django REST Framework** for the API
- **Celery** for background tasks (notifications)
- **SQLite** for development (switch to a production database for deployment)
- **CoreUI**, **Chart.js** and **SimpleBar** for the admin interface
- **Active Directory / LDAP** for staff authentication

## Getting started

These steps are for Windows (PowerShell). On macOS or Linux, use the equivalent commands.

**1. Clone the repository**

```powershell
git clone https://github.com/02Tabi/Authmanager.git
cd Authmanager
```

**2. Create and activate a virtual environment**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**3. Install dependencies**

```powershell
pip install -r requirements.txt
```

**4. Create your environment file**

```powershell
copy .env.example .env
```

Open `.env` and fill in real values (see [Configuration](#configuration)). Never commit this file.

**5. Set up the database**

```powershell
python manage.py migrate
python manage.py createsuperuser
```

**6. Run the server**

```powershell
python manage.py runserver 8000
```

Auth Manager is now available at `http://127.0.0.1:8000/`. Client applications call `http://127.0.0.1:8000/api/login/`.

**7. (Optional) Start the Celery worker** for background email notifications:

```powershell
celery -A config worker -l info --pool=solo
```

The `--pool=solo` flag is needed on Windows. A message broker such as Redis must be running and configured in `.env`.

## Configuration

All secrets and environment-specific settings live in `.env`, which is excluded from Git. `.env.example` lists every variable.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key. Generate a long random value for each environment |
| `DEBUG` | `True` for development only. Must be `False` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames the server may serve |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Database connection (if not using SQLite) |
| `AD_SERVER`, `AD_BIND_USER`, `AD_BIND_PASSWORD` | Active Directory connection details |

Generate a new secret key with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

## Connecting a new application

1. **Register the application** in the Auth Manager admin interface and note its `app_id` (for example `PREPAID-PORTAL`).
2. **Get the application approved**, since newly registered applications start as pending.
3. **Grant users a permission** for that application (`maker`, `checker`, `admin` or `super_admin`) and have it approved.
4. **Call the login API** from your application, sending `username`, `password` and your `app_id`.
5. **Map the response** to your own roles using `permission_type`. For example, the Prepaid Transfer Portal maps `checker`, `admin` and `super_admin` to its *checker* group and everything else to *maker*.
6. **Re-sync on every login.** Refresh the user's local role from the response each time they sign in, so changes made in Auth Manager take effect immediately.

## Security notes

- Never commit `.env`, `db.sqlite3` or any file containing credentials. The `.gitignore` in this repository excludes them.
- Run with `DEBUG=False` and a strong, unique `SECRET_KEY` in any shared or production environment.
- Serve the API over **HTTPS** in production. Credentials are sent in the request body and must not travel over plain HTTP outside a trusted local network.
- Use a production-grade database rather than SQLite, and restrict who can read it. It contains account data and password hashes.
- Treat the `PREPAID-PORTAL`-style `app_id` values as identifiers, not secrets. Access is controlled by the permission records, not by knowing an `app_id`.
- If a secret is ever committed to Git, rotate it. Deleting the file in a later commit does not remove it from history.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Every user shows up as a *maker* in a client app | The client is reading `role` instead of `permission_type` from the login response |
| A role change in Auth Manager does not appear in the client | The client is not re-syncing the role on each login, or a stale session is being reused |
| Login fails for a valid user | The account is locked or inactive, the permission is not yet approved, or the `app_id` does not match a registered application |
| "Authentication server is unreachable" in a client | Auth Manager is not running, or the client is pointing at the wrong URL or port |
| Emails are not being sent | The Celery worker or message broker is not running, or email settings are missing from `.env` |

## License

Specify your license here (for example MIT, or "Proprietary, internal use only").
