from pydantic import BaseModel, Field
from typing import Optional

class CustomerBase(BaseModel):
    name: str = Field(..., description="Customer full name")
    phone: str = Field(..., description="Phone number with country code")
    company: Optional[str] = Field(default="", description="Company or organization")
    designation: Optional[str] = Field(default="", description="Job title")
    city: Optional[str] = Field(default="", description="City location")
    preferred_product_id: Optional[str] = Field(default="prod_smartsave", description="Target product")
    notes: Optional[str] = Field(default="", description="Sales notes")
    status: Optional[str] = Field(default="lead", description="Lead status: lead, contacted, converted, lost")

class CustomerCreate(CustomerBase):
    pass

class CustomerOut(CustomerBase):
    customer_id: str

