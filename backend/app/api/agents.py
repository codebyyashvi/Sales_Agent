import time
import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut
from app.database import get_db

router = APIRouter()


def _require_db():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    return db


@router.get("/api/agents", response_model=List[AgentOut])
async def list_agents():
    db = get_db()
    if db is None:
        return []
    cursor = db.agents.find({}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=200)


@router.post("/api/agents", response_model=AgentOut)
async def create_agent(payload: AgentCreate):
    db = _require_db()
    now = time.time()
    doc = payload.model_dump()
    doc["agent_id"] = f"agent_{uuid.uuid4().hex[:8]}"
    doc["created_at"] = now
    doc["updated_at"] = now
    await db.agents.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/api/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str):
    db = _require_db()
    doc = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return doc


@router.put("/api/agents/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, payload: AgentUpdate):
    db = _require_db()
    updates = payload.model_dump()
    updates["updated_at"] = time.time()
    result = await db.agents.update_one({"agent_id": agent_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})


@router.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    db = _require_db()
    result = await db.agents.delete_one({"agent_id": agent_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return {"status": "deleted", "agent_id": agent_id}
