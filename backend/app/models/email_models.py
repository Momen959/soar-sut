"""Pydantic models for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class EmailPayload(BaseModel):
    sender: EmailStr
    recipients: List[EmailStr] = Field(default_factory=list)
    subject: str = Field(..., max_length=512)
    body: str = Field(..., min_length=1)
    attachments: List[str] = Field(default_factory=list)


class EmailAnalysis(BaseModel):
    engine: str = Field(default="heuristic")
    probability: Optional[float] = None
    spelling_score: Optional[float] = None
    keyword_score: Optional[float] = None
    composite_score: float
    model_label: str
    model_config = {"protected_namespaces": ()}


class EmailRecord(BaseModel):
    id: int
    gmail_id: str
    subject: Optional[str]
    sender: Optional[str]
    recipients: List[str]
    snippet: Optional[str]
    body: Optional[str]
    has_attachments: bool
    date: Optional[datetime]
    is_starred: bool
    labels: List[str] = Field(default_factory=list)
    analysis: Optional[EmailAnalysis]
    created_at: datetime


class EmailCreateResponse(BaseModel):
    record_id: int
    gmail_id: str
    analysis: EmailAnalysis


class EmailSyncResponse(BaseModel):
    synced: int
    analysed: int
    folder: str




