"""
Database Schemas for AI Sales Training Course Subscription Website

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class Member(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    role: str = Field("member", description="Role: admin | moderator | member")
    subscription_status: str = Field("inactive", description="inactive | active | past_due | canceled")
    provider: Optional[str] = Field(None, description="stripe | paypal | invoice")
    plan: Optional[str] = Field("$49/mo", description="Subscription plan label")

class InvoiceRequest(BaseModel):
    member_email: str = Field(..., description="Email for invoicing")
    company: Optional[str] = Field(None, description="Company name")
    notes: Optional[str] = Field(None, description="Additional info")
    status: str = Field("requested", description="requested | sent | paid")

class Message(BaseModel):
    member_email: str = Field(..., description="Author's email")
    content: str = Field(..., description="Message content")
    channel: str = Field("general", description="Channel name")

class Resource(BaseModel):
    title: str
    type: str = Field(..., description="prompt | tool")
    description: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = []

class Video(BaseModel):
    title: str
    vimeo_id: str = Field(..., description="Vimeo video ID")
    description: Optional[str] = None
    category: Optional[str] = None
