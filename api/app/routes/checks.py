"""Check a posting, and list your past checks."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..clients.ml_client import MlServiceUnavailable
from ..deps import get_check_service, get_token_claims
from ..schemas import CheckHistoryOut, CheckOut, CheckSummary, PostingIn
from ..services.check_service import CheckService

router = APIRouter(prefix="/api/v1", tags=["checks"])


@router.post("/check", response_model=CheckOut)
def check_posting(body: PostingIn,
                  claims: dict = Depends(get_token_claims),   # token only, no user lookup
                  service: CheckService = Depends(get_check_service)):
    try:
        result = service.check(int(claims["sub"]), body)
    except MlServiceUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The scoring service is unavailable. Please try again in a moment.")
    c = result.check
    return CheckOut(id=c.id, score=c.score, verdict=c.verdict, flags=c.flags,
                    limited_info=result.limited_info, note=result.note,
                    model_version=c.model_version, cache_hit=c.cache_hit, created_at=c.created_at)


@router.get("/checks/me", response_model=CheckHistoryOut)
def my_checks(limit: int = Query(20, ge=1, le=100),
              before: datetime | None = Query(None, description="next_before from the previous page"),
              claims: dict = Depends(get_token_claims),
              service: CheckService = Depends(get_check_service)):
    items, next_before = service.history(int(claims["sub"]), limit, before)
    return CheckHistoryOut(items=[CheckSummary.model_validate(i) for i in items], next_before=next_before)
