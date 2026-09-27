import os, hashlib, hmac, base64, json, secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SESSION_SECRET", "CHANGE_ME")
USER = os.environ.get("ADMIN_USERNAME", "admin").strip()
PASS = os.environ.get("ADMIN_PASSWORD", "CHANGE_ME")
SECRET = os.environ.get("LICENSE_SECRET_KEY", "CHANGE_ME").encode()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)


def init_db():
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id BIGSERIAL PRIMARY KEY,
                    license_key TEXT UNIQUE NOT NULL,
                    license_hash TEXT UNIQUE NOT NULL,
                    customer TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    expires TEXT NOT NULL,
                    max_groups TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    hwid TEXT,
                    activated_at TEXT,
                    last_seen TEXT,
                    created_at TEXT NOT NULL
                )
            """)
        c.commit()
    finally:
        c.close()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def b64(x):
    return base64.urlsafe_b64encode(x).decode().rstrip("=")


def sign(x):
    return hmac.new(SECRET, x, hashlib.sha256).digest()


def makekey(customer, plan, days, groups):
    e = now() + timedelta(days=days)
    p = {
        "customer": customer,
        "plan": plan,
        "expires": e.isoformat(timespec="seconds"),
        "max_groups": groups,
    }
    raw = json.dumps(p, separators=(",", ":"), sort_keys=True).encode()
    return b64(raw) + "." + b64(sign(raw)), p


def verify(k):
    try:
        a, b = k.split(".", 1)
        raw = base64.urlsafe_b64decode(a + "=" * (-len(a) % 4))
        sig = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4))
        if not hmac.compare_digest(sign(raw), sig):
            return None, "invalid signature"
        p = json.loads(raw)
        e = datetime.fromisoformat(p["expires"])
        if now() > e:
            return None, "license expired"
        return p, None
    except Exception:
        return None, "malformed license"


def auth(f):
    @wraps(f)
    def w(*a, **k):
        return f(*a, **k) if session.get("admin") else redirect(url_for("login"))
    return w


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("username", ""), USER) and hmac.compare_digest(request.form.get("password", ""), PASS):
            session["admin"] = True
            return redirect("/")
        flash("Invalid login", "error")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.get("/")
@auth
def home():
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM licenses")
            total = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM licenses WHERE active=1")
            active = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM licenses WHERE active=0")
            revoked = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM licenses WHERE hwid IS NOT NULL")
            activated = cur.fetchone()["n"]
            cur.execute("SELECT * FROM licenses ORDER BY id DESC LIMIT 10")
            rows = cur.fetchall()
        stats = [total, active, revoked, activated]
    finally:
        c.close()
    return render_template("dashboard.html", stats=stats, rows=rows)


@app.post("/create")
@auth
def create():
    customer = request.form.get("customer", "").strip()
    plan = request.form.get("plan", "standard").strip()
    groups = request.form.get("groups", "unlimited").strip()
    try:
        days = int(request.form.get("days", "30"))
    except ValueError:
        days = 0
    if not customer or days < 1:
        flash("Invalid customer or duration", "error")
        return redirect("/")
    key, p = makekey(customer, plan, days, groups)
    h = hashlib.sha256(key.encode()).hexdigest()
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO licenses
                (license_key, license_hash, customer, plan, expires, max_groups, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (key, h, customer, plan, p["expires"], groups, now().isoformat(timespec="seconds")))
        c.commit()
        flash("License generated: " + key, "success")
    except Exception:
        c.rollback()
        flash("Could not create license", "error")
    finally:
        c.close()
    return redirect("/")


@app.get("/licenses")
@auth
def all_licenses():
    q = request.args.get("q", "")
    c = db()
    try:
        with c.cursor() as cur:
            like = f"%{q}%"
            cur.execute("""
                SELECT * FROM licenses
                WHERE customer ILIKE %s OR plan ILIKE %s OR license_key ILIKE %s
                ORDER BY id DESC
            """, (like, like, like))
            rows = cur.fetchall()
    finally:
        c.close()
    return render_template("licenses.html", rows=rows, q=q)


@app.post("/action/<act>")
@auth
def action(act):
    key = request.form.get("license_key", "")
    h = hashlib.sha256(key.encode()).hexdigest()
    c = db()
    try:
        with c.cursor() as cur:
            if act == "revoke":
                cur.execute("UPDATE licenses SET active=0 WHERE license_hash=%s", (h,))
            elif act == "restore":
                cur.execute("UPDATE licenses SET active=1 WHERE license_hash=%s", (h,))
            elif act == "reset":
                cur.execute("UPDATE licenses SET hwid=NULL, activated_at=NULL, last_seen=NULL WHERE license_hash=%s", (h,))
        c.commit()
    finally:
        c.close()
    return redirect(request.referrer or "/licenses")


@app.post("/api/license/check")
def check():
    d = request.get_json(silent=True) or {}
    key = str(d.get("license_key", "")).strip()
    hwid = str(d.get("hwid", "")).strip()
    if not key or not hwid:
        return jsonify(valid=False, reason="license_key and hwid are required"), 400

    p, e = verify(key)
    if e:
        return jsonify(valid=False, reason=e)

    h = hashlib.sha256(key.encode()).hexdigest()
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM licenses WHERE license_hash=%s", (h,))
            r = cur.fetchone()
            if not r:
                return jsonify(valid=False, reason="license not registered")
            if not r["active"]:
                return jsonify(valid=False, reason="license revoked")
            if r["hwid"] and r["hwid"] != hwid:
                return jsonify(valid=False, reason="license activated on another machine")

            t = now().isoformat(timespec="seconds")
            if r["hwid"]:
                cur.execute("UPDATE licenses SET last_seen=%s WHERE license_hash=%s", (t, h))
            else:
                cur.execute("UPDATE licenses SET hwid=%s, activated_at=%s, last_seen=%s WHERE license_hash=%s", (hwid, t, t, h))
            c.commit()

            expires = datetime.fromisoformat(r["expires"])
            remaining = max(0, (expires - now()).days)
            return jsonify(
                valid=True,
                reason=f"valid ({remaining} days remaining)",
                payload={
                    "customer": r["customer"],
                    "plan": r["plan"],
                    "expires": r["expires"],
                    "max_groups": r["max_groups"],
                },
                expires=r["expires"],
            )
    finally:
        c.close()


@app.get("/health")
def health():
    try:
        c = db()
        with c.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        c.close()
        return jsonify(ok=True, database=True)
    except Exception as ex:
        return jsonify(ok=False, database=False, error=str(ex)), 500


# Vercel imports this module; do not start a local server there.
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
