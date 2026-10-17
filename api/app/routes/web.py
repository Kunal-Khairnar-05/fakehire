"""Web check: search the internet for evidence about who posted a job."""
from dataclasses import asdict

from fastapi import APIRouter, Depends

from ..deps import enforce_rate_limit, get_web_check_service
from ..schemas import WebCheckIn, WebCheckOut
from ..services.check_service import normalize
from ..services.web_check import WebCheckService

router = APIRouter(prefix="/api/v1", tags=["web check"])


# Login required and rate-limited: every uncached search spends paid API quota.
# Always answers 200: "unavailable" is a normal result, the check itself never depends on it.
@router.post("/web-check", response_model=WebCheckOut, dependencies=[Depends(enforce_rate_limit)])
def web_check(body: WebCheckIn, service: WebCheckService = Depends(get_web_check_service)):
    result = service.check(normalize(body.posting), body.company_name)
    return WebCheckOut(**asdict(result))
