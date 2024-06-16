from datetime import date, datetime, time, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr, constr
from bson.objectid import ObjectId


class Customer(BaseModel):
    name: str
    email: str
    phone: str
    partner_id: Optional[list] or None
    created_at: datetime or None or ''
    role: str or None = None


class EditCustomer(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class LoginCustomerSchema(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    partner_id: list or None = None


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    partner_id: Optional[list] or None
    created_at: str
    role: str or None = None


class AdminApprovalRequest(BaseModel):
    approve: bool
