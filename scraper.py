from typing import List, Optional

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float
    lng: float


class Business(BaseModel):
    business_name: str
    address: str
    category: str
    rating: str
    reviews_count: str
    google_maps_url: str
    company_url: str
    phone: str
    opening_hours: List[str]
    price_level: str
    attributes: List[str]
    images: List[str]
    description: str
    latitude: Optional[float]
    longitude: Optional[float]
    distance_km: Optional[float]
    raw_page_text_snippet: str


class ScrapeRequest(BaseModel):
    input_url: str = Field(..., min_length=1)
    radius_km: int = Field(default=5, ge=1)
    keyword: Optional[str] = None
    desired_results: int = Field(default=10, ge=1)
    headless: bool = False


class ScrapeResponse(BaseModel):
    input_url: str
    resolved_url: str
    search_url: str
    radius_km: int
    coordinates: Coordinates
    zoom_level: int
    timestamp: str
    desired_results: int
    total_processed: int
    within_radius: int
    excluded_outside_radius: int
    data: List[Business]
    excluded_data: List[Business]
