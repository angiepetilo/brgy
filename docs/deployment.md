# Barangay Information & Management System — Production Deployment Guide

## 1. Overview & Architecture
The system runs as an asynchronous Django application using:
- **Application Server**: Gunicorn (WSGI) + Daphne / Uvicorn (ASGI for Channels WebSockets)
- **Reverse Proxy & Web Server**: Nginx
- **Static Files**: WhiteNoise / Nginx
- **Database**: MySQL / MariaDB (charset `utf8mb4`)
- **Cache & Channel Layer**: Redis (or local memory for low volume)
- **Background Tasks**: Linux Cron / Systemd Timers

---

## 2. Environment Variables (.env)
Copy `.env.example` to `.env` in the project root (`chmod 600 .env`).

| Variable | Description | Production Example |
|---|---|---|
| `DEBUG` | Must be False in production | `False` |
| `SECRET_KEY` | Strong random secret key (>50 characters) | `generate via get_random_secret_key()` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `barangay.gov.ph,www.barangay.gov.ph` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins | `https://barangay.gov.ph` |
| `DB_ENGINE` | Database backend engine | `django.db.backends.mysql` |
| `DB_NAME` | Production database name | `brgy_production` |
| `DB_USER` | MySQL user | `brgy_user` |
| `DB_PASSWORD` | MySQL password | `<strong-database-password>` |
| `DB_HOST` | Database host | `127.0.0.1` |
| `DB_PORT` | Database port | `3306` |
| `EMAIL_BACKEND` | SMTP backend | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP server host | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Transport Layer Security | `True` |
| `EMAIL_HOST_USER` | Sending email address | `official@barangay.gov.ph` |
| `EMAIL_HOST_PASSWORD` | App-specific password (16 chars) | `<app-password>` |
| `DEFAULT_FROM_EMAIL` | Header From name and address | `Barangay e-Portal <official@barangay.gov.ph>` |
| `SECURE_SSL_REDIRECT` | Redirect all HTTP to HTTPS (default `True` when `DEBUG=False`) | `True` |
| `SESSION_COOKIE_SECURE`| Cookies only over HTTPS (default `True` when `DEBUG=False`) | `True` |
| `CSRF_COOKIE_SECURE`   | CSRF cookie only over HTTPS (default `True` when `DEBUG=False`) | `True` |
| `SECURE_HSTS_SECONDS`  | HSTS max-age (default `31536000` when `DEBUG=False`) | `31536000` (start with `3600` on a new domain) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS subdomains (default `True` when `DEBUG=False`) | `True` |
| `SECURE_HSTS_PRELOAD`  | HSTS preload list; manual, hard-to-undo opt-in (its deploy warning W021 is silenced) | `False` |
| `TRUSTED_PROXY_COUNT` | Reverse proxies in front of the app that append to `X-Forwarded-For`. `0` ignores the header. Behind one nginx: `1` (also enables `SECURE_PROXY_SSL_HEADER`) | `1` |
| `CSP_REPORT_ONLY` | `True` sends `Content-Security-Policy-Report-Only` instead of enforcing | `False` |
| `LOGIN_FAILURE_LIMIT` | Failed logins per username + IP before a 15-minute lockout | `5` |
| `LOGIN_LOCKOUT_SECONDS` | Lockout window and length | `900` |
| `LOGIN_IP_FAILURE_LIMIT` | Failed logins per IP across all usernames | `20` |
| `LOGIN_USER_FAILURE_LIMIT` | Failed logins per username across all IPs | `10` |
| `RATE_LIMIT_<NAME>` | Override a rate limit (`PASSWORD_RESET`, `SIGNUP`, `PUBLIC_BOOKING`, `EMAIL_VALIDATION`, `CHAT_SEND`, `STATISTICS_EXPORT`, `BLOTTER_CREATE`), format `count/period` | `5/15m` |
| `REDIS_URL` | Redis for Channels and the cache (rate-limit/login counters) | `redis://127.0.0.1:6379/0` |

### 2.1 Startup safety checks
With `DEBUG=False` the app refuses to start (`ImproperlyConfigured`) when `SECRET_KEY` is missing, is the development default, starts with `django-insecure`, or is shorter than 50 characters, or when `ALLOWED_HOSTS` is empty or contains `*`. Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Verify the configuration with `python manage.py check --deploy` (expected: `System check identified no issues (1 silenced)`).

### 2.2 Cache table
Without `REDIS_URL` the cache (login lockouts and rate limits) is the database table `brgy_cache_table`. Create it once per database: `python manage.py createcachetable`. The test runner creates it automatically.

### 2.3 Content-Security-Policy rollout
`apps.core.middleware.SecurityHeadersMiddleware` sends `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'` plus `Permissions-Policy: camera=(), microphone=(), geolocation=()`. All JavaScript lives in `static/js` and all third-party assets in `static/vendor` (no CDN). If a template change might break a page, deploy with `CSP_REPORT_ONLY=True`, check the browser console for violations, fix them, then switch back to `False` (enforce).

### 2.4 Phone numbers stored before the 09XXXXXXXXX rule
Migrations `accounts 0019` and `appointments 0018` rewrite stored numbers to `09XXXXXXXXX` (dashes/spaces removed, `+63`/`63` converted). Values that cannot be converted are left unchanged and their ids are printed during `migrate` and logged (logger `apps.migrations`). Fix each one by hand: Residents page > Edit (users), the Django admin (Resident / Appointment), or ask the resident to update their profile. Saving a form with an invalid number shows the 11-digit message.

---

## 3. Web Server (Nginx) & Private Media Security

### Private Media Protection
Resident identification documents (`private_media/id_photos/`) contain sensitive personal data and **must never be accessible directly by web browser or web server request**.

### Nginx Configuration Snippet (`/etc/nginx/sites-available/barangay.conf`):
```nginx
server {
    listen 80;
    server_name barangay.gov.ph www.barangay.gov.ph;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name barangay.gov.ph www.barangay.gov.ph;

    ssl_certificate /etc/letsencrypt/live/barangay.gov.ph/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/barangay.gov.ph/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 10M;

    # Public static files
    location /static/ {
        alias /var/www/brgy/staticfiles/;
        expires 30d;
        access_log off;
    }

    # Public media (avatars, announcements, public attachments)
    location /media/ {
        alias /var/www/brgy/media/;
        expires 7d;
    }

    # CRITICAL: Deny ALL direct web server access to private_media
    location ^~ /private_media/ {
        deny all;
        return 403;
    }

    # CRITICAL: Deny direct web access to sensitive ID photo paths if requested under media
    location ^~ /media/id_photos/ {
        deny all;
        return 403;
    }

    # CRITICAL: legacy public copies of ID proofs and appointment supporting documents.
    # Supporting documents are served only by /appointments/<id>/supporting-id/.
    location ^~ /media/id_proofs/ {
        deny all;
        return 403;
    }
    location ^~ /media/appointments/ {
        deny all;
        return 403;
    }

    # Reverse proxy to Gunicorn WSGI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Reverse proxy to Daphne ASGI (WebSockets / Channels)
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Proof Test (Private Media Isolation)
Run from any terminal while unauthenticated:
```bash
curl -I https://barangay.gov.ph/private_media/id_photos/sample.jpg
```
**Expected Result**:
```http
HTTP/1.1 403 Forbidden
```
Direct access is completely blocked. ID photos are only viewable by authorized staff (and the owner) via the authenticated route `/accounts/id-photo/<resident_id>/`; appointment supporting documents via `/appointments/<id>/supporting-id/` (owner, admin/kapitan, in-scope staff).

With nginx in front, set `TRUSTED_PROXY_COUNT=1` so login lockouts and audit logs use the real client IP from `X-Forwarded-For` and HTTPS is detected from `X-Forwarded-Proto`. Leave it at `0` when clients reach the app directly, otherwise they can fake their IP.

---

## 4. HTTPS Certificate Setup (Let's Encrypt / Certbot)
```bash
sudo apt update && sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d barangay.gov.ph -d www.barangay.gov.ph
sudo systemctl enable certbot.timer
```

---

## 5. Scheduled Tasks (Cron Table)
Place in `/etc/cron.d/barangay_tasks` or in the application user's `crontab -e`:

```cron
# Send queued background emails every minute
* * * * * cd /var/www/brgy && /var/www/brgy/.venv/bin/python manage.py send_queued_emails >> /var/www/brgy/logs/cron.log 2>&1

# Send appointment reminder emails daily at 3:00 PM Asia/Manila (07:00 UTC)
0 15 * * * cd /var/www/brgy && /var/www/brgy/.venv/bin/python manage.py send_appointment_reminders >> /var/www/brgy/logs/cron.log 2>&1

# Expire posts daily at midnight Asia/Manila
0 0 * * * cd /var/www/brgy && /var/www/brgy/.venv/bin/python manage.py expire_posts >> /var/www/brgy/logs/cron.log 2>&1

# Clean up rejected registrations older than 90 days weekly (Sunday 2:00 AM)
0 2 * * 0 cd /var/www/brgy && /var/www/brgy/.venv/bin/python manage.py cleanup_rejected_registrations >> /var/www/brgy/logs/cron.log 2>&1

# Purge read notifications older than 90 days weekly (Sunday 3:00 AM)
0 3 * * 0 cd /var/www/brgy && /var/www/brgy/.venv/bin/python manage.py purge_read_notifications >> /var/www/brgy/logs/cron.log 2>&1

# Nightly database dump & off-site backup at 1:00 AM Asia/Manila
0 1 * * * /var/www/brgy/scripts/nightly_backup.sh >> /var/www/brgy/logs/backup.log 2>&1
```

---

## 6. WebSockets, ASGI & Redis Channel Layer

The system uses Django Channels for real-time 1-on-1 chat and instant notification badge updates.

### 6.1 Redis Channel Layer Configuration
In production, install Redis and configure `REDIS_URL` in `.env`:
```ini
REDIS_URL=redis://127.0.0.1:6379/1
```

Django Channels reads this via `config/settings.py`:
```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")],
        },
    },
}
```

### 6.2 ASGI Server (Daphne / Uvicorn)
Run Daphne on an internal loopback port (e.g., `8001`):
```bash
/var/www/brgy/.venv/bin/daphne -b 127.0.0.1 -p 8001 config.asgi:application
```
Or via Uvicorn:
```bash
/var/www/brgy/.venv/bin/uvicorn config.asgi:application --host 127.0.0.1 --port 8001 --workers 4
```

### 6.3 Systemd Service Units

#### Gunicorn WSGI Service (`/etc/systemd/system/barangay-web.service`):
```ini
[Unit]
Description=Barangay Web Application (Gunicorn WSGI)
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/brgy
Environment="PATH=/var/www/brgy/.venv/bin"
ExecStart=/var/www/brgy/.venv/bin/gunicorn --workers 4 --bind 127.0.0.1:8000 --access-logfile /var/www/brgy/logs/gunicorn.access.log --error-logfile /var/www/brgy/logs/gunicorn.error.log config.wsgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

#### Daphne ASGI Service (`/etc/systemd/system/barangay-websocket.service`):
```ini
[Unit]
Description=Barangay WebSockets & Channels (Daphne ASGI)
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/brgy
Environment="PATH=/var/www/brgy/.venv/bin"
ExecStart=/var/www/brgy/.venv/bin/daphne -b 127.0.0.1 -p 8001 --access-log /var/www/brgy/logs/daphne.log config.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

To enable and start the services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now barangay-web barangay-websocket
sudo systemctl status barangay-web barangay-websocket
```

