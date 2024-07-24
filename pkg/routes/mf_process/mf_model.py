from pydantic import BaseModel
from enum import Enum


class RequestStatus(str, Enum):
    requested = "requested"
    processed = "processed"


class MFRequest(BaseModel):
    fund_name: str
    amount: float
    status: RequestStatus = RequestStatus.requested


class MFAccount(BaseModel):
    fund_name: str
    amount: float

