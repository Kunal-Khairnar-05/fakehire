"""Public: trending scam companies and company search. No login needed, so anyone can
look a company up before replying to a recruiter. (Nginx's per-IP limit still applies.)"""
from fastapi import APIRouter, Depends, Query

from ..deps import get_company_service
from ..schemas import CompanyOut, TrendingItem, TrendingOut
from ..services.company_service import CompanyService

router = APIRouter(prefix="/api/v1", tags=["companies"])


@router.get("/trending", response_model=TrendingOut)
def trending(limit: int = Query(10, ge=1, le=50), service: CompanyService = Depends(get_company_service)):
    entries, source = service.trending_now(limit)
    items = [TrendingItem(**CompanyOut.model_validate(e.company).model_dump(), this_week=e.this_week)
             for e in entries]
    return TrendingOut(items=items, source=source)


@router.get("/companies/search", response_model=list[CompanyOut])
def search_companies(q: str = Query(..., min_length=2, max_length=100, description="Company name, or the start of it"),
                     limit: int = Query(10, ge=1, le=50),
                     service: CompanyService = Depends(get_company_service)):
    return service.search(q, limit)
