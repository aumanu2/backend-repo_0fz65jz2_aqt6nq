import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from database import db, create_document, get_documents
from bson.objectid import ObjectId

# Pydantic models (mirror schemas.py but used for request validation)
class RegisterRequest(BaseModel):
    name: str
    email: str

class SubscribeRequest(BaseModel):
    email: str
    provider: str = Field(..., description="stripe | paypal | invoice")
    company: Optional[str] = None
    notes: Optional[str] = None

class MessageCreate(BaseModel):
    member_email: str
    content: str
    channel: str = "general"

class ResourceCreate(BaseModel):
    title: str
    type: str
    description: Optional[str] = None
    url: Optional[str] = None
    tags: Optional[List[str]] = []

class VideoCreate(BaseModel):
    title: str
    vimeo_id: str
    description: Optional[str] = None
    category: Optional[str] = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility helpers

def member_by_email(email: str):
    return db["member"].find_one({"email": email}) if db else None


def ensure_member(email: str):
    m = member_by_email(email)
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    return m


def is_admin(email: str) -> bool:
    m = member_by_email(email)
    return bool(m and m.get("role") == "admin")


@app.get("/")
def read_root():
    return {"message": "AI Sales Training Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Auth-lite endpoint to check admin
@app.get("/api/admin/is_admin")
def admin_check(email: str = Query(...)):
    return {"email": email, "is_admin": is_admin(email)}


# Members
@app.post("/api/members/register")
def register_member(payload: RegisterRequest):
    if member_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "name": payload.name,
        "email": payload.email,
        "role": "member",
        "subscription_status": "inactive",
        "provider": None,
        "plan": "$49/mo",
    }
    inserted_id = create_document("member", doc)
    return {"id": inserted_id, "message": "Registered"}


@app.get("/api/members")
def list_members(x_admin_email: Optional[str] = Header(None)):
    if not x_admin_email or not is_admin(x_admin_email):
        raise HTTPException(status_code=403, detail="Admin only")
    members = get_documents("member")
    for m in members:
        m["_id"] = str(m["_id"])  # serialize
    return members


@app.patch("/api/members/update")
def update_member(email: str, role: Optional[str] = None, subscription_status: Optional[str] = None, x_admin_email: Optional[str] = Header(None)):
    if not x_admin_email or not is_admin(x_admin_email):
        raise HTTPException(status_code=403, detail="Admin only")
    ensure_member(email)
    updates = {}
    if role:
        updates["role"] = role
    if subscription_status:
        updates["subscription_status"] = subscription_status
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    db["member"].update_one({"email": email}, {"$set": updates})
    return {"message": "Updated"}


# Subscriptions
@app.post("/api/subscribe")
def subscribe(payload: SubscribeRequest):
    m = ensure_member(payload.email)
    provider = payload.provider.lower()
    if provider not in ["stripe", "paypal", "invoice"]:
        raise HTTPException(status_code=400, detail="Invalid provider")

    checkout_url = None
    status = "active"

    if provider == "stripe":
        # In a real app, create a Stripe Checkout session here
        checkout_url = "https://buy.stripe.com/test_12345"  # placeholder
    elif provider == "paypal":
        # In a real app, create a PayPal order here
        checkout_url = "https://www.paypal.com/checkoutnow?token=TEST123"
    else:
        # Invoice flow
        status = "pending"
        create_document(
            "invoicerequest",
            {
                "member_email": payload.email,
                "company": payload.company,
                "notes": payload.notes,
                "status": "requested",
            },
        )

    db["member"].update_one(
        {"email": payload.email},
        {"$set": {"subscription_status": status, "provider": provider}},
    )

    return {"message": "Subscription initiated", "status": status, "checkout_url": checkout_url}


# Videos
@app.get("/api/videos")
def get_videos():
    vids = get_documents("video")
    for v in vids:
        v["_id"] = str(v["_id"])  # serialize
    return vids


@app.post("/api/videos")
def add_video(payload: VideoCreate, x_admin_email: Optional[str] = Header(None)):
    if not x_admin_email or not is_admin(x_admin_email):
        raise HTTPException(status_code=403, detail="Admin only")
    vid_id = create_document("video", payload.model_dump())
    return {"id": vid_id, "message": "Video added"}


# Resources
@app.get("/api/resources")
def get_resources():
    items = get_documents("resource")
    for r in items:
        r["_id"] = str(r["_id"])  # serialize
    return items


@app.post("/api/resources")
def add_resource(payload: ResourceCreate, x_admin_email: Optional[str] = Header(None)):
    if not x_admin_email or not is_admin(x_admin_email):
        raise HTTPException(status_code=403, detail="Admin only")
    res_id = create_document("resource", payload.model_dump())
    return {"id": res_id, "message": "Resource added"}


# Community messages
@app.get("/api/messages")
def list_messages(channel: str = "general", limit: int = 50):
    msgs = get_documents("message", {"channel": channel}, limit=limit)
    for m in msgs:
        m["_id"] = str(m["_id"])  # serialize
    # Sort newest first by created_at if present
    msgs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return msgs


@app.post("/api/messages")
def post_message(payload: MessageCreate):
    # Require that author exists and is active
    m = ensure_member(payload.member_email)
    if m.get("subscription_status") not in ["active", "past_due", "pending"]:
        raise HTTPException(status_code=403, detail="Subscription required")
    msg_id = create_document("message", payload.model_dump())
    return {"id": msg_id, "message": "Posted"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
