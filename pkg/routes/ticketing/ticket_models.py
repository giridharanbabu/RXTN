from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Pydantic models
class TicketCreate(BaseModel):
    title: str
    description: str


class Ticket(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    title: str
    description: str
    Customer: str
    customer_name: Optional[str] = None
    admin_name: Optional[str] = None
    partner_name: Optional[str] = None
    partner: Optional[str] = None
    admin: Optional[str] = None
    status: str = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    current_status: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class ChatMessageCreate(BaseModel):
    content: str


class FileMetadata(BaseModel):
    file_id: str
    file_name: str


class ChatMessage(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    ticket_id: str
    sender_id: Optional[str] = None
    content: str
    receiver_id : Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None
    files: Optional[List[FileMetadata]] = None

    # file_id: Optional[str] = None
    # file_name: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class CloseTicket(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    ticket_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    current_status: Optional[str] = None
    status: str
    close_description: str
    closed_by: str
    role: str



