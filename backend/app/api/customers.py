import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.customer import CustomerCreate, CustomerOut
from app.database import get_db

router = APIRouter()

@router.get("/api/customers", response_model=List[CustomerOut])
async def list_customers():
    db = get_db()
    if db is None:
        return []
    cursor = db.customers.find({}, {"_id": 0})
    return await cursor.to_list(length=100)

@router.post("/api/customers", response_model=CustomerOut)
async def create_customer(payload: CustomerCreate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    
    doc = payload.model_dump()
    doc["customer_id"] = f"cust_{uuid.uuid4().hex[:6]}"
    await db.customers.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/api/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    doc = await db.customers.find_one({"customer_id": customer_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return doc

