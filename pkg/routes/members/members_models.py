from datetime import date, datetime, time, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr, constr
from bson.objectid import ObjectId


class Members(BaseModel):
    name: str
    email: str
    role: str
    created_time: datetime


class RequestModel(BaseModel):
    partner_id: str
    request_fields: List
    expiresAt: datetime
    created_time: datetime or None
