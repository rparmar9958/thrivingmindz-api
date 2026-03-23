from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import os
import secrets
import json
import databases
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:sbwhzgdXEfKWuuFvtgubRxnGXGhnKcWP@postgres.railway.internal:5432/railway")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

database = databases.Database(DATABASE_URL)

app = FastAPI(title="ThrivingMindz API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "thrivingmindz2026")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "thrivingmindz@gmail.com")
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not (secrets.compare_digest(credentials.username, ADMIN_USER) and secrets.compare_digest(credentials.password, ADMIN_PASS)):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

def send_email_notification(subject, body_html):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("Email not configured, skipping notification")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"ThrivingMindz <{SMTP_EMAIL}>"
        msg["To"] = NOTIFY_EMAIL
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")

class RegistrationCreate(BaseModel):
    type: str
    name: str
    email: str
    phone: Optional[str] = None
    district: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    interests: Optional[List[str]] = None
    child_age: Optional[str] = None
    concern: Optional[str] = None
    discipline: Optional[str] = None
    license_num: Optional[str] = None
    specialty: Optional[str] = None
    pro_interest: Optional[str] = None
    role: Optional[str] = None
    school_interest: Optional[str] = None
    donor_type: Optional[str] = None
    donor_interest: Optional[str] = None
    notes: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str

class ContactCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subject: Optional[str] = None
    message: str

@app.on_event("startup")
async def startup():
    await database.connect()
    try:
        await database.execute(query="""
        CREATE TABLE IF NOT EXISTS registrations (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            type VARCHAR(20),
            status VARCHAR(20) DEFAULT 'new',
            name VARCHAR(200),
            email VARCHAR(200),
            phone VARCHAR(30),
            district VARCHAR(100),
            school VARCHAR(200),
            grade VARCHAR(30),
            interests TEXT,
            child_age VARCHAR(20),
            concern VARCHAR(100),
            discipline VARCHAR(100),
            license_num VARCHAR(50),
            specialty VARCHAR(200),
            pro_interest VARCHAR(200),
            role VARCHAR(100),
            school_interest VARCHAR(200),
            donor_type VARCHAR(100),
            donor_interest VARCHAR(200),
            notes TEXT
        )""")
        await database.execute(query="""
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            name VARCHAR(200),
            email VARCHAR(200),
            phone VARCHAR(30),
            subject VARCHAR(200),
            message TEXT,
            status VARCHAR(20) DEFAULT 'new'
        )""")
        print("Database connected and tables ready.")
    except Exception as e:
        print(f"Table creation note: {e}")

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/")
async def root():
    return {"status": "ok", "service": "ThrivingMindz API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/contact")
async def create_contact(contact: ContactCreate):
    query = """INSERT INTO contacts (created_at, name, email, phone, subject, message, status)
    VALUES (:created_at, :name, :email, :phone, :subject, :message, 'new')
    RETURNING id"""
    values = {"created_at": datetime.utcnow(), "name": contact.name, "email": contact.email, "phone": contact.phone, "subject": contact.subject, "message": contact.message}
    record_id = await database.execute(query=query, values=values)
    # Send email notification
    asyncio.get_event_loop().run_in_executor(None, send_email_notification,
        f"📩 New Contact Message from {contact.name}",
        f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#FF6B9D;">New Contact Message</h2>
        <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Name:</td><td style="padding:8px;">{contact.name}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Email:</td><td style="padding:8px;"><a href="mailto:{contact.email}">{contact.email}</a></td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Phone:</td><td style="padding:8px;">{contact.phone or 'N/A'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Type:</td><td style="padding:8px;">{contact.subject or 'N/A'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Message:</td><td style="padding:8px;">{contact.message}</td></tr>
        </table>
        <p style="margin-top:20px;color:#888;font-size:12px;">View all contacts at <a href="https://thrivingmindz.org/admin">thrivingmindz.org/admin</a></p>
        </div>""")
    return {"success": True, "id": record_id, "message": "Message sent! We'll get back to you soon."}

@app.get("/api/admin/contacts")
async def get_contacts(admin: str = Depends(verify_admin)):
    rows = await database.fetch_all("SELECT * FROM contacts ORDER BY created_at DESC")
    return {"contacts": [{**dict(r), "created_at": str(r["created_at"])} for r in rows]}

@app.post("/api/register")
async def create_registration(reg: RegistrationCreate):
    existing = await database.fetch_one("SELECT id FROM registrations WHERE (email = :email OR (phone = :phone AND phone IS NOT NULL AND phone != '')) AND type = :type", {"email": reg.email, "phone": reg.phone, "type": reg.type})
    if existing:
        return {"success": True, "id": existing["id"], "message": "You're already registered! We'll be in touch soon."}
    query = """INSERT INTO registrations (created_at, type, status, name, email, phone, district, school, grade, interests, child_age, concern, discipline, license_num, specialty, pro_interest, role, school_interest, donor_type, donor_interest, notes)
    VALUES (:created_at, :type, :status, :name, :email, :phone, :district, :school, :grade, :interests, :child_age, :concern, :discipline, :license_num, :specialty, :pro_interest, :role, :school_interest, :donor_type, :donor_interest, :notes)
    RETURNING id"""
    values = {
        "created_at": datetime.utcnow(), "type": reg.type, "status": "new",
        "name": reg.name, "email": reg.email, "phone": reg.phone,
        "district": reg.district, "school": reg.school, "grade": reg.grade,
        "interests": json.dumps(reg.interests) if reg.interests else None,
        "child_age": reg.child_age, "concern": reg.concern,
        "discipline": reg.discipline, "license_num": reg.license_num,
        "specialty": reg.specialty, "pro_interest": reg.pro_interest,
        "role": reg.role, "school_interest": reg.school_interest,
        "donor_type": reg.donor_type, "donor_interest": reg.donor_interest, "notes": reg.notes,
    }
    record_id = await database.execute(query=query, values=values)
    # Send email notification
    asyncio.get_event_loop().run_in_executor(None, send_email_notification,
        f"🎉 New {reg.type.title()} Registration: {reg.name}",
        f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#FF6B9D;">New Registration!</h2>
        <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Type:</td><td style="padding:8px;"><span style="background:#FF6B9D22;color:#FF6B9D;padding:4px 12px;border-radius:12px;font-weight:bold;">{reg.type}</span></td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Name:</td><td style="padding:8px;">{reg.name}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Email:</td><td style="padding:8px;"><a href="mailto:{reg.email}">{reg.email}</a></td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">Phone:</td><td style="padding:8px;">{reg.phone or 'N/A'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">District:</td><td style="padding:8px;">{reg.district or 'N/A'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;color:#555;">School:</td><td style="padding:8px;">{reg.school or 'N/A'}</td></tr>
        </table>
        <p style="margin-top:20px;color:#888;font-size:12px;">View all registrations at <a href="https://thrivingmindz.org/admin">thrivingmindz.org/admin</a></p>
        </div>""")
    return {"success": True, "id": record_id, "message": "Registration received!"}

@app.get("/api/admin/stats")
async def get_stats(admin: str = Depends(verify_admin)):
    total = await database.fetch_one("SELECT COUNT(*) as count FROM registrations")
    by_type = await database.fetch_all("SELECT type, COUNT(*) as count FROM registrations GROUP BY type ORDER BY count DESC")
    by_status = await database.fetch_all("SELECT status, COUNT(*) as count FROM registrations GROUP BY status ORDER BY count DESC")
    week_ago = datetime.utcnow() - timedelta(days=7)
    this_week = await database.fetch_one("SELECT COUNT(*) as count FROM registrations WHERE created_at >= :date", {"date": week_ago})
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await database.fetch_one("SELECT COUNT(*) as count FROM registrations WHERE created_at >= :date", {"date": today_start})
    month_ago = datetime.utcnow() - timedelta(days=30)
    daily = await database.fetch_all("SELECT DATE(created_at) as date, COUNT(*) as count FROM registrations WHERE created_at >= :date GROUP BY DATE(created_at) ORDER BY date", {"date": month_ago})
    by_district = await database.fetch_all("SELECT district, COUNT(*) as count FROM registrations WHERE district IS NOT NULL AND district != '' GROUP BY district ORDER BY count DESC")
    contacts_count = await database.fetch_one("SELECT COUNT(*) as count FROM contacts")
    return {
        "total": total["count"] if total else 0,
        "this_week": this_week["count"] if this_week else 0,
        "today": today["count"] if today else 0,
        "contacts": contacts_count["count"] if contacts_count else 0,
        "by_type": [dict(r) for r in by_type],
        "by_status": [dict(r) for r in by_status],
        "daily": [{"date": str(r["date"]), "count": r["count"]} for r in daily],
        "by_district": [dict(r) for r in by_district],
    }

@app.get("/api/admin/registrations")
async def get_registrations(type: Optional[str] = None, status: Optional[str] = None, district: Optional[str] = None, search: Optional[str] = None, limit: int = Query(default=50, le=500), offset: int = 0, admin: str = Depends(verify_admin)):
    query = "SELECT * FROM registrations WHERE 1=1"
    params = {}
    if type: query += " AND type = :type"; params["type"] = type
    if status: query += " AND status = :status"; params["status"] = status
    if district: query += " AND district = :district"; params["district"] = district
    if search: query += " AND (name ILIKE :search OR email ILIKE :search OR phone ILIKE :search)"; params["search"] = f"%{search}%"
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit; params["offset"] = offset
    rows = await database.fetch_all(query, params)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = await database.fetch_one(count_query, count_params)
    return {
        "total": total["count"] if total else 0,
        "registrations": [{**dict(r), "created_at": str(r["created_at"])} for r in rows],
    }

@app.put("/api/admin/registrations/{reg_id}/status")
async def update_status(reg_id: int, update: StatusUpdate, admin: str = Depends(verify_admin)):
    await database.execute("UPDATE registrations SET status = :status WHERE id = :id", {"status": update.status, "id": reg_id})
    return {"success": True, "id": reg_id, "status": update.status}

@app.delete("/api/admin/registrations/{reg_id}")
async def delete_registration(reg_id: int, admin: str = Depends(verify_admin)):
    await database.execute("DELETE FROM registrations WHERE id = :id", {"id": reg_id})
    return {"success": True, "id": reg_id}

@app.get("/api/admin/export")
async def export_csv(type: Optional[str] = None, admin: str = Depends(verify_admin)):
    from fastapi.responses import StreamingResponse
    import csv, io
    query = "SELECT * FROM registrations"
    params = {}
    if type: query += " WHERE type = :type"; params["type"] = type
    query += " ORDER BY created_at DESC"
    rows = await database.fetch_all(query, params)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Date","Type","Status","Name","Email","Phone","District","School","Grade","Interests","Child Age","Concern","Discipline","License","Specialty","Pro Interest","Role","School Interest","Donor Type","Donor Interest","Notes"])
    for r in rows:
        writer.writerow([r["id"],str(r["created_at"]),r["type"],r["status"],r["name"],r["email"],r["phone"],r["district"],r["school"],r["grade"],r["interests"],r["child_age"],r["concern"],r["discipline"],r["license_num"],r["specialty"],r["pro_interest"],r["role"],r["school_interest"],r["donor_type"],r["donor_interest"],r["notes"]])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=thrivingmindz-{datetime.utcnow().strftime('%Y%m%d')}.csv"})
