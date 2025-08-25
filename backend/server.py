from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date, time, timezone
from io import BytesIO

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Helpers for MongoDB serialization

def prepare_for_mongo(data: dict):
    # Convert datetime/date/time objects to serializable formats
    d = dict(data)
    if isinstance(d.get('created_at'), datetime):
        d['created_at'] = d['created_at'].astimezone(timezone.utc).isoformat()
    if isinstance(d.get('updated_at'), datetime):
        d['updated_at'] = d['updated_at'].astimezone(timezone.utc).isoformat()
    if isinstance(d.get('date'), date):
        d['date'] = d['date'].isoformat()
    if isinstance(d.get('time'), time):
        d['time'] = d['time'].strftime('%H:%M:%S')
    return d


def parse_from_mongo(item: dict):
    if not item:
        return item
    d = dict(item)
    # Remove Mongo _id if present
    d.pop('_id', None)
    # Parse ISO datetimes if needed
    if isinstance(d.get('created_at'), str):
        try:
            d['created_at'] = datetime.fromisoformat(d['created_at'])
        except Exception:
            pass
    if isinstance(d.get('updated_at'), str):
        try:
            d['updated_at'] = datetime.fromisoformat(d['updated_at'])
        except Exception:
            pass
    return d

# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class Mood(BaseModel):
    value: str
    emoji: str
    label: str
    color: Optional[str] = None  # hex or tailwind color hint

class MoodConfig(BaseModel):
    moods: List[Mood]

class MoodEntryCreate(BaseModel):
    date: str  # YYYY-MM-DD
    mood_value: str
    emoji: str
    note: Optional[str] = None

class MoodEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    mood_value: str
    emoji: str
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Defaults
DEFAULT_MOODS: List[dict] = [
    {"value": "happy", "emoji": "😀", "label": "Happy", "color": "#22c55e"},
    {"value": "content", "emoji": "🙂", "label": "Content", "color": "#10b981"},
    {"value": "meh", "emoji": "😐", "label": "Meh", "color": "#a3a3a3"},
    {"value": "anxious", "emoji": "😕", "label": "Anxious", "color": "#f59e0b"},
    {"value": "sad", "emoji": "😢", "label": "Sad", "color": "#3b82f6"},
    {"value": "angry", "emoji": "😠", "label": "Angry", "color": "#ef4444"},
    {"value": "tired", "emoji": "😴", "label": "Tired", "color": "#8b5cf6"},
]

# Base routes
@api_router.get("/")
async def root():
    return {"message": "Daily Feels API is running"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(client_name=input.client_name)
    await db.status_checks.insert_one(prepare_for_mongo(status_obj.model_dump()))
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**parse_from_mongo(s)) for s in status_checks]

# Mood config routes
@api_router.get("/moods/defaults", response_model=List[Mood])
async def get_default_moods():
    return [Mood(**m) for m in DEFAULT_MOODS]

@api_router.get("/moods/config", response_model=MoodConfig)
async def get_mood_config():
    doc = await db.settings.find_one({"key": "mood_config"})
    if not doc or not doc.get('moods'):
        return MoodConfig(moods=[Mood(**m) for m in DEFAULT_MOODS])
    moods = [Mood(**m) for m in doc['moods']]
    return MoodConfig(moods=moods)

@api_router.post("/moods/config", response_model=MoodConfig)
async def set_mood_config(config: MoodConfig):
    payload = {
        "key": "mood_config",
        "moods": [m.model_dump() for m in config.moods],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.settings.replace_one({"key": "mood_config"}, payload, upsert=True)
    return config

# Entries routes
@api_router.post("/entries", response_model=MoodEntry)
async def create_or_update_entry(payload: MoodEntryCreate):
    # Ensure single entry per date
    existing = await db.mood_entries.find_one({"date": payload.date})
    now = datetime.now(timezone.utc)
    if existing:
        # update
        existing = parse_from_mongo(existing)
        existing.update({
            "mood_value": payload.mood_value,
            "emoji": payload.emoji,
            "note": payload.note,
            "updated_at": now,
        })
        await db.mood_entries.update_one({"id": existing["id"]}, {"$set": prepare_for_mongo(existing)})
        return MoodEntry(**existing)
    else:
        entry = MoodEntry(
            date=payload.date,
            mood_value=payload.mood_value,
            emoji=payload.emoji,
            note=payload.note,
            created_at=now,
            updated_at=now,
        )
        await db.mood_entries.insert_one(prepare_for_mongo(entry.model_dump()))
        return entry

@api_router.get("/entries", response_model=List[MoodEntry])
async def list_entries(start: Optional[str] = None, end: Optional[str] = None):
    q = {}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    elif start:
        q["date"] = {"$gte": start}
    elif end:
        q["date"] = {"$lte": end}
    entries = await db.mood_entries.find(q, sort=[("date", 1)]).to_list(length=None)
    return [MoodEntry(**parse_from_mongo(e)) for e in entries]

@api_router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str):
    res = await db.mood_entries.delete_one({"id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}

# Export PDF
@api_router.get("/export/pdf")
async def export_pdf(start: Optional[str] = None, end: Optional[str] = None):
    # Fetch entries
    q = {}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    elif start:
        q["date"] = {"$gte": start}
    elif end:
        q["date"] = {"$lte": end}
    entries = await db.mood_entries.find(q, sort=[("date", 1)]).to_list(length=None)
    entries = [parse_from_mongo(e) for e in entries]

    # Fetch config
    cfg = await db.settings.find_one({"key": "mood_config"})
    moods = cfg.get('moods') if cfg and cfg.get('moods') else DEFAULT_MOODS
    color_map = {m['value']: m.get('color') or '#999999' for m in moods}
    label_map = {m['value']: m.get('label', m['value']) for m in moods}

    # Build PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title = Paragraph("Mood Report", styles['Title'])
    elements.append(title)
    timeframe = f"All time" if not (start or end) else f"From {start or '...'} to {end or '...'}"
    elements.append(Paragraph(timeframe, styles['Normal']))
    elements.append(Spacer(1, 12))

    # Summary table
    counts = {}
    for e in entries:
        counts[e['mood_value']] = counts.get(e['mood_value'], 0) + 1
    if counts:
        data = [["Mood", "Count"]]
        for mv, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            data.append([f"{label_map.get(mv, mv)}", str(cnt)])
        tbl = Table(data, hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(Paragraph("Summary", styles['Heading2']))
        elements.append(tbl)
        elements.append(Spacer(1, 12))

    # Detailed list
    elements.append(Paragraph("Entries", styles['Heading2']))
    data = [["Date", "Mood", "Emoji", "Note"]]
    for e in entries:
        mv = e.get('mood_value')
        row_color = colors.HexColor(color_map.get(mv, '#dddddd'))
        data.append([e.get('date'), label_map.get(mv, mv), e.get('emoji', ''), (e.get('note') or '')[:200]])
    table = Table(data, hAlign='LEFT', colWidths=[90, 120, 50, 270])
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    filename = f"mood_report_{(start or 'start')}_{(end or 'end')}.pdf"
    return StreamingResponse(buffer, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()