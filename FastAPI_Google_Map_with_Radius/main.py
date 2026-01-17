from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.routers.scraper import router as scraper_router
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Google Maps Radius Scraper", version="1.0.0")
    # Enable CORS for browser-based requests (adjust origins for production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(scraper_router, prefix="/api")
    return app


app = create_app()
