import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.product import ProductCreate, ProductOut
from app.database import get_db

router = APIRouter()

@router.get("/api/products", response_model=List[ProductOut])
async def list_products():
    db = get_db()
    if db is None:
        return []
    cursor = db.products.find({}, {"_id": 0})
    return await cursor.to_list(length=100)

@router.post("/api/products", response_model=ProductOut)
async def create_product(payload: ProductCreate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    
    doc = payload.model_dump()
    if not doc.get("product_id"):
        doc["product_id"] = f"prod_{uuid.uuid4().hex[:6]}"
    await db.products.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/api/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    doc = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found.")
    return doc

