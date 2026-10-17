"""Scam reports: students report, moderators review."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_report_service, get_token_claims, require_role
from ..schemas import QueueItem, QueueOut, ReportIn, ReportOut, ReviewIn
from ..services.report_service import (
    AlreadyReported,
    AlreadyReviewed,
    CheckNotFound,
    PostingMismatch,
    ReportNotFound,
    ReportService,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# Any logged-in user can report; only these roles can see and review the queue
is_moderator = require_role("moderator", "admin")


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def report_scam(body: ReportIn,
                claims: dict = Depends(get_token_claims),
                service: ReportService = Depends(get_report_service)):
    try:
        return service.report(int(claims["sub"]), body.check_id, body.company_name, body.reason, body.posting)
    except CheckNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Check not found")
    except PostingMismatch:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "The posting doesn't match the one that was checked. Check it again, then report.")
    except AlreadyReported:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already reported this check")


@router.get("/me", response_model=list[ReportOut])
def my_reports(limit: int = Query(20, ge=1, le=100),
               claims: dict = Depends(get_token_claims),
               service: ReportService = Depends(get_report_service)):
    return service.mine(int(claims["sub"]), limit)


@router.get("/queue", response_model=QueueOut)
def moderation_queue(limit: int = Query(20, ge=1, le=100),
                     after: datetime | None = Query(None, description="next_after from the previous page"),
                     _: dict = Depends(is_moderator),
                     service: ReportService = Depends(get_report_service)):
    rows, next_after = service.queue(limit, after)
    items = [QueueItem(**ReportOut.model_validate(report).model_dump(),
                       title=check.title, snippet=check.snippet, score=check.score, verdict=check.verdict)
             for report, check in rows]
    return QueueOut(items=items, next_after=next_after)


@router.patch("/{report_id}", response_model=ReportOut)
def review_report(report_id: int, body: ReviewIn,
                  claims: dict = Depends(is_moderator),
                  service: ReportService = Depends(get_report_service)):
    try:
        return service.review(int(claims["sub"]), report_id, body.status)
    except ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    except AlreadyReviewed:
        raise HTTPException(status.HTTP_409_CONFLICT, "This report was already reviewed")
