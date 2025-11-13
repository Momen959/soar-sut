"""AI classification endpoints for phishing detection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query

from models.email_models import EmailAnalysis, EmailPayload, EmailRecord
from services.email_service import EmailService


router = APIRouter(prefix="/api/ai", tags=["classification"])


def get_email_service(request: Request) -> EmailService:
    """Dependency to get the email service from app state."""
    service: EmailService = request.app.state.email_service
    return service

@router.get("/classifications", response_model=list[EmailRecord])
def list_emails(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: EmailService = Depends(get_email_service),
) -> list[EmailRecord]:
    return service.list_emails(limit=limit, offset=offset)


@router.get("/classify/{gmail_id}", response_model=EmailAnalysis, status_code=status.HTTP_200_OK)
def classify_email_by_id(
    gmail_id: str,
    service: EmailService = Depends(get_email_service),
) -> EmailAnalysis:
    """
    Classify an email by its Gmail ID.
    
    Re-analyzes the specified email using the phishing detection model
    and returns the classification results. The email must exist in the
    database (either from a previous sync or manual submission).
    """
    try:
        analysis = service.classify_email_by_id(gmail_id)
        return analysis
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

