from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import os
import secrets
import hashlib
import json

# ─── Database ───
import databases
import sqlalchemy

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/thrivingmindz")
# Railway uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

registrations = sqlalchemy.Table(
    "registrations", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("type", sqlalchemy.String(20)),  # student, parent, professional, school, donor
    sqlalchemy.Column("status", sqlalchemy.String(20), default="new"),  # new, contacted, enrolled, active
    sqlalchemy.Column("name", sqlalchemy.String(200)),
    sqlalchemy.Column("email", sqlalchemy.String(200)),
    sqlalchemy.Column("phone", sqlalchemy.String(30)),
    # Student fields
    sqlalchemy.Column("district", sqlalchemy.String(100), nullable=True),
    sqlalchemy.Column("school", sqlalchemy.String(200), nullable=True),
    sqlalchemy.Column("grade", sqlalchemy.String(30), nullable=True),
    sqlalchemy.Column("interests", sqlalchemy.Text, nullable=True),  # JSON array
    # Parent fields
    sqlalchemy.Column("child_age", sqlalchemy.String(20), nullable=True),
    sqlalchemy.Column("concern", sqlalchemy.String(100), nullable=True),
    # Professional fields
    sqlalchemy.Column("discipline", sqlalchemy.String(100), nullable=True),
    sqlalchemy.Column("license_num", sqlalchemy.String(50), nullable=True),
    sqlalchemy.Column("specialty", sqlalchemy.String(200), nullable=True),
    sqlalchemy.Column("pro_interest", sqlalchemy.String(200), nullable=True),
    # School admin fields
    sqlalchemy.Column("role", sqlalchemy.String(100), nullable=True),
    sqlalchemy.Column("school_interest", sqlalchemy.String(200), nullable=True),
    # Donor fields
    sqlalchemy.Column("donor_type", sqlalchemy.String(100), nullable=True),
    sqlalchemy.Column("donor_interest", sqlalchemy.String(200), nullable=True),
    sqlalchemy.Column("notes", sqlalchemy.Text, nullable=True),
)

engine = sqlalchemy.create_engine(DATABASE_URL)
metadata.create_all(engine)

# ─── App ───
app = FastAPI(title="ThrivingMindz API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://thrivingmindz.org",
        "https://www.thrivingmindz.org",
        "https://thrivingmindz.netlify.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Admin Auth ───
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "thrivingmindz2026")

security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (correct_user and correct_pass):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

# ─── Models ───
class RegistrationCreate(BaseModel):
    type: str  # student, parent, professional, school, donor
    name: str
    email: str
    phone: Optional[str] = None
    # Student
    district: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    interests: Optional[List[str]] = None
    # Parent
    child_age: Optional[str] = None
    concern: Optional[str] = None
    # Professional
    discipline: Optional[str] = None
    license_num: Optional[str] = None
    specialty: Optional[str] = None
    pro_interest: Optional[str] = None
    # School
    role: Optional[str] = None
    school_interest: Optional[str] = None
    # Donor
    donor_type: Optional[str] = None
    donor_interest: Optional[str] = None
    notes: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str  # new, contacted, enrolled, active

# ─── Startup/Shutdown ───
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# ─── Public Endpoints ───
@app.get("/")
async def root():
    return {"status": "ok", "service": "ThrivingMindz API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/register")
async def create_registration(reg: RegistrationCreate):
    values = {
        "created_at": datetime.utcnow(),
        "type": reg.type,
        "status": "new",
        "name": reg.name,
        "email": reg.email,
        "phone": reg.phone,
        "district": reg.district,
        "school": reg.school,
        "grade": reg.grade,
        "interests": json.dumps(reg.interests) if reg.interests else None,
        "child_age": reg.child_age,
        "concern": reg.concern,
        "discipline": reg.discipline,
        "license_num": reg.license_num,
        "specialty": reg.specialty,
        "pro_interest": reg.pro_interest,
        "role": reg.role,
        "school_interest": reg.school_interest,
        "donor_type": reg.donor_type,
        "donor_interest": reg.donor_interest,
        "notes": reg.notes,
    }
    query = registrations.insert().values(**values)
    record_id = await database.execute(query)
    
    # TODO: Add email/SMS notification here (Twilio/SendGrid)
    
    return {"success": True, "id": record_id, "message": "Registration received! We will contact you soon."}

# ─── Admin Endpoints ───
@app.get("/api/admin/stats")
async def get_stats(admin: str = Depends(verify_admin)):
    """Dashboard stats"""
    total = await database.fetch_one("SELECT COUNT(*) as count FROM registrations")
    
    # By type
    by_type = await database.fetch_all(
        "SELECT type, COUNT(*) as count FROM registrations GROUP BY type ORDER BY count DESC"
    )
    
    # By status
    by_status = await database.fetch_all(
        "SELECT status, COUNT(*) as count FROM registrations GROUP BY status ORDER BY count DESC"
    )
    
    # This week
    week_ago = datetime.utcnow() - timedelta(days=7)
    this_week = await database.fetch_one(
        "SELECT COUNT(*) as count FROM registrations WHERE created_at >= :date",
        {"date": week_ago}
    )
    
    # Today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await database.fetch_one(
        "SELECT COUNT(*) as count FROM registrations WHERE created_at >= :date",
        {"date": today_start}
    )
    
    # Last 30 days by day
    month_ago = datetime.utcnow() - timedelta(days=30)
    daily = await database.fetch_all(
        "SELECT DATE(created_at) as date, COUNT(*) as count FROM registrations WHERE created_at >= :date GROUP BY DATE(created_at) ORDER BY date",
        {"date": month_ago}
    )
    
    # By district
    by_district = await database.fetch_all(
        "SELECT district, COUNT(*) as count FROM registrations WHERE district IS NOT NULL AND district != '' GROUP BY district ORDER BY count DESC"
    )
    
    return {
        "total": total["count"] if total else 0,
        "this_week": this_week["count"] if this_week else 0,
        "today": today["count"] if today else 0,
        "by_type": [dict(r) for r in by_type],
        "by_status": [dict(r) for r in by_status],
        "daily": [{"date": str(r["date"]), "count": r["count"]} for r in daily],
        "by_district": [dict(r) for r in by_district],
    }

@app.get("/api/admin/registrations")
async def get_registrations(
    type: Optional[str] = None,
    status: Optional[str] = None,
    district: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    admin: str = Depends(verify_admin),
):
    """Get all registrations with filters"""
    query = "SELECT * FROM registrations WHERE 1=1"
    params = {}
    
    if type:
        query += " AND type = :type"
        params["type"] = type
    if status:
        query += " AND status = :status"
        params["status"] = status
    if district:
        query += " AND district = :district"
        params["district"] = district
    if search:
        query += " AND (name ILIKE :search OR email ILIKE :search OR phone ILIKE :search)"
        params["search"] = f"%{search}%"
    
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    
    rows = await database.fetch_all(query, params)
    
    # Get total count
    count_query = "SELECT COUNT(*) as count FROM registrations WHERE 1=1"
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    if type:
        count_query += " AND type = :type"
    if status:
        count_query += " AND status = :status"
    if district:
        count_query += " AND district = :district"
    if search:
        count_query += " AND (name ILIKE :search OR email ILIKE :search OR phone ILIKE :search)"
    
    total = await database.fetch_one(count_query, count_params)
    
    return {
        "total": total["count"] if total else 0,
        "registrations": [
            {**dict(r), "created_at": str(r["created_at"]), "interests": json.loads(r["interests"]) if r["interests"] else None}
            for r in rows
        ],
    }

@app.put("/api/admin/registrations/{reg_id}/status")
async def update_status(reg_id: int, update: StatusUpdate, admin: str = Depends(verify_admin)):
    """Update registration status"""
    query = registrations.update().where(registrations.c.id == reg_id).values(status=update.status)
    await database.execute(query)
    return {"success": True, "id": reg_id, "status": update.status}

@app.delete("/api/admin/registrations/{reg_id}")
async def delete_registration(reg_id: int, admin: str = Depends(verify_admin)):
    """Delete a registration"""
    query = registrations.delete().where(registrations.c.id == reg_id)
    await database.execute(query)
    return {"success": True, "id": reg_id}

@app.get("/api/admin/export")
async def export_csv(
    type: Optional[str] = None,
    admin: str = Depends(verify_admin),
):
    """Export registrations as CSV"""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    query = "SELECT * FROM registrations"
    params = {}
    if type:
        query += " WHERE type = :type"
        params["type"] = type
    query += " ORDER BY created_at DESC"
    
    rows = await database.fetch_all(query, params)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Date", "Type", "Status", "Name", "Email", "Phone",
        "District", "School", "Grade", "Interests",
        "Child Age", "Concern",
        "Discipline", "License", "Specialty", "Pro Interest",
        "Role", "School Interest",
        "Donor Type", "Donor Interest", "Notes"
    ])
    
    for r in rows:
        writer.writerow([
            r["id"], str(r["created_at"]), r["type"], r["status"], r["name"], r["email"], r["phone"],
            r["district"], r["school"], r["grade"], r["interests"],
            r["child_age"], r["concern"],
            r["discipline"], r["license_num"], r["specialty"], r["pro_interest"],
            r["role"], r["school_interest"],
            r["donor_type"], r["donor_interest"], r["notes"]
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=thrivingmindz-registrations-{datetime.utcnow().strftime('%Y%m%d')}.csv"}
    )
