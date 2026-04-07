# Afghan Top Backend - Render + PostgreSQL Ready

This backend is now prepared for deployment on **Render** with **PostgreSQL**.

## What was changed

- PostgreSQL-ready database config using `DATABASE_URL`
- fixed `ALLOWED_HOSTS` parsing for Render domains
- production security settings controlled by environment variables
- WhiteNoise added for static file serving
- Gunicorn added for production start command
- `build.sh` added for install + collectstatic + migrate
- `render.yaml` added for one-click Render Blueprint deployment
- `.python-version` added and pinned to `3.14.3`
- cleanup support with `.gitignore`

## Local development

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Render deployment

### Option 1: Blueprint deployment using `render.yaml`

1. Push this project to GitHub.
2. In Render, click **New > Blueprint**.
3. Select your repository.
4. Render will create:
   - a web service
   - a PostgreSQL database
5. After first deploy, open **Shell** and run:
   ```bash
   python manage.py createsuperuser
   ```

### Option 2: Manual web service setup

Use these values in Render:

- **Runtime:** Python
- **Root Directory:** `backend`
- **Build Command:** `./build.sh`
- **Start Command:** `gunicorn config.wsgi:application`
- **Health Check Path:** `/health/`

Create a Render PostgreSQL database and set the web service environment variable:

- `DATABASE_URL` = your Render PostgreSQL connection string

Also set:

- `SECRET_KEY` = strong random secret
- `DEBUG` = `False`
- `ALLOWED_HOSTS` = `.onrender.com`
- `CORS_ALLOWED_ORIGINS` = your frontend URL, comma-separated if more than one
- `CSRF_TRUSTED_ORIGINS` = your backend/frontend HTTPS origins
- `PYTHON_VERSION` = `3.14.3`

## Important note about free plans

Render offers free web services and free PostgreSQL for testing, but Render says free instances have important limitations and are not meant for production use. For real production traffic, use a paid plan. citeturn468863search8turn707270view1

## Why these changes were needed

Render's Django guide recommends switching from SQLite to PostgreSQL, configuring WhiteNoise for static files, and creating a build script for deploys. Render's docs also show using a Python build command and a Gunicorn-based start command for web services. citeturn707270view0turn707270view1

## URLs

- Health: `/health/`
- Admin: `/admin/`
- API docs: `/api/docs/`
- OpenAPI schema: `/api/schema/`
