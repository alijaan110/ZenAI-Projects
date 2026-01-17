from fastapi import APIRouter, HTTPException
import anyio

from app.schemas.scraper import ScrapeRequest, ScrapeResponse
from app.services.scraper import scrape_area


router = APIRouter(tags=["scraper"])


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    try:
        result = await anyio.to_thread.run_sync(
            scrape_area,
            payload.input_url,
            payload.radius_km,
            payload.keyword,
            payload.desired_results,
            payload.headless,
        )
        return ScrapeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
