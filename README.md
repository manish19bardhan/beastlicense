# Vercel License Manager

This version replaces Vercel-local SQLite storage with PostgreSQL while keeping the Flask admin dashboard and `/api/license/check` API.

## 1. Create PostgreSQL
Create a PostgreSQL database with Neon, Supabase, or another PostgreSQL provider. Copy its connection string as `DATABASE_URL`.

## 2. Local migration
Put the old `licenses.db` in this folder, create a Python environment, install requirements, set `DATABASE_URL`, then run:

```bash
python migrate_sqlite.py
```

## 3. Vercel environment variables
Add these in Vercel Project Settings > Environment Variables:

- `FLASK_SESSION_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `LICENSE_SECRET_KEY`
- `DATABASE_URL`

Keep `LICENSE_SECRET_KEY` identical to the key used when generating existing licenses if existing license keys must remain valid.

## 4. Deploy
```bash
vercel --prod
```

## 5. Test
Open:

`https://YOUR-DOMAIN/health`

Expected:

```json
{"ok":true,"database":true}
```

API:

```http
POST /api/license/check
Content-Type: application/json
```

```json
{"license_key":"YOUR_LICENSE_KEY","hwid":"YOUR_HWID"}
```
