import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import get_settings
from .database import get_session
from .models import PortalUser, Application, BlockedContact, FaqItem, SupportTicket

router = APIRouter(prefix="/api")
class InitPayload(BaseModel): init_data: str = Field(min_length=10)
class ApplicationIn(BaseModel): kind: str; payload: dict
class TicketIn(BaseModel): subject: str; text: str; category: str = "general"

def validate_init(raw: str):
    settings=get_settings(); pairs=dict(parse_qsl(raw, keep_blank_values=True)); received=pairs.pop("hash", None)
    if not received: raise HTTPException(401, "Telegram initData is required")
    check="\n".join(f"{k}={pairs[k]}" for k in sorted(pairs)); secret=hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest(); expected=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received): raise HTTPException(401, "Invalid Telegram signature")
    if int(time.time())-int(pairs.get("auth_date", 0)) > 86400: raise HTTPException(401, "Expired Telegram data")
    try: return json.loads(pairs["user"])
    except Exception: raise HTTPException(401, "Invalid Telegram user")

async def current_user(x_telegram_init_data: str = Header(default=""), db: AsyncSession = Depends(get_session)):
    tg=validate_init(x_telegram_init_data); row=(await db.execute(select(PortalUser).where(PortalUser.telegram_id==tg["id"]))).scalar_one_or_none()
    if row is None: row=PortalUser(telegram_id=tg["id"],username=tg.get("username"),first_name=tg.get("first_name"),last_name=tg.get("last_name"),language_code=tg.get("language_code"),photo_url=tg.get("photo_url")); db.add(row)
    else: row.username=tg.get("username"); row.first_name=tg.get("first_name"); row.last_name=tg.get("last_name")
    await db.commit(); return row

@router.post("/auth")
async def auth(payload: InitPayload, db: AsyncSession = Depends(get_session)):
    tg=validate_init(payload.init_data); return {"user": {"telegram_id":tg["id"],"username":tg.get("username"),"first_name":tg.get("first_name"),"role":"guest"}}

@router.get("/me")
async def me(user=Depends(current_user)): return {"telegram_id":user.telegram_id,"username":user.username,"first_name":user.first_name,"last_name":user.last_name,"role":user.role}

@router.post("/applications")
async def application(data: ApplicationIn, user=Depends(current_user), db: AsyncSession=Depends(get_session)):
    if data.kind not in {"agent","partner"}: raise HTTPException(400,"Invalid application type")
    row=Application(telegram_id=user.telegram_id,kind=data.kind,payload=json.dumps(data.payload,ensure_ascii=False)); db.add(row); await db.commit(); return {"ok":True,"status":"new"}

@router.get("/check-contact")
async def check_contact(value: str, user=Depends(current_user), db: AsyncSession=Depends(get_session)):
    hit=(await db.execute(select(Application).where(Application.payload.ilike(f"%{value}%")))).first(); return {"available": hit is None, "message":"✅ Контакт свободен" if hit is None else "⚠️ Контакт уже есть в системе"}

@router.get("/blocked")
async def blocked(value: str, user=Depends(current_user), db: AsyncSession=Depends(get_session)):
    hit=(await db.execute(select(BlockedContact).where(BlockedContact.value.ilike(value)))).scalar_one_or_none(); return {"blocked":hit is not None,"message":"⛔ Контакт заблокирован" if hit else "✅ Контакт не находится в блок-листе"}

@router.get("/faq")
async def faq(audience: str="partner", db: AsyncSession=Depends(get_session)):
    rows=(await db.execute(select(FaqItem).where(FaqItem.audience==audience,FaqItem.active.is_(True)).order_by(FaqItem.position))).scalars().all(); return [{"question":x.question,"answer":x.answer} for x in rows]

@router.post("/support")
async def support(data: TicketIn,user=Depends(current_user),db: AsyncSession=Depends(get_session)):
    row=SupportTicket(telegram_id=user.telegram_id,subject=data.subject,text=data.text,category=data.category);db.add(row);await db.commit();return {"ok":True,"status":"open"}
