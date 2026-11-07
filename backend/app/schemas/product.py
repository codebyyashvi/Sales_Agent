from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class FAQItem(BaseModel):
    q: str
    a: str

class ProductBase(BaseModel):
    name: str = Field(..., description="Product name")
    tagline: Optional[str] = Field(default="", description="Catchy one-line value proposition")
    category: Optional[str] = Field(default="General", description="Category")
    description: str = Field(..., description="Full product overview")
    features: List[str] = Field(default_factory=list, description="Core benefits and capabilities")
    pricing: str = Field(..., description="Exact pricing model")
    faqs: List[Dict[str, str]] = Field(default_factory=list, description="Frequently asked questions")
    objections: Dict[str, str] = Field(default_factory=dict, description="Objection rebuttals")
    key_terms: List[str] = Field(default_factory=list, description="STT vocabulary terms")

class ProductCreate(ProductBase):
    product_id: Optional[str] = None

class ProductOut(ProductBase):
    product_id: str

