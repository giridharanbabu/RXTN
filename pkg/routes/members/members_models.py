from datetime import date, datetime, time, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr, constr
from bson.objectid import ObjectId


class Members(BaseModel):
    name: str
    email: str
    role: str
    created_at: datetime


class RequestModel(BaseModel):
    partner_id: str
    request_fields: List
    expiresAt: datetime
    created_time: datetime or None


class MemberBaseSchema(BaseModel):
    name: str
    email: str
    photo: str
    organization_name: Optional[str] = None
    organization_type: Optional[str] = None
    description: Optional[str] = None
    role: str
    created_at: datetime or None = None
    updated_at: datetime or None = None


class CreateMemberSchema(MemberBaseSchema):
    password: constr(min_length=8)
    passwordConfirm: str
    verified: bool = False


class LoginMemberSchema(BaseModel):
    email: EmailStr
    password: constr(min_length=8)

