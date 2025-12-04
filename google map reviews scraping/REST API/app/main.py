from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import os
import json
from datetime import datetime
import uuid

from scraper import GoogleMapsScraper
from celery_worker import scrape_task

app = FastAPI(
    title="Google Maps Review Scraper API",
    description="REST API for scraping Google Maps reviews",
    version="1.0.0"
)

# In-memory storage for job status (use Redis in production)
jobs_db = {}

class ScrapeRequest(BaseModel):
    maps_url: HttpUrl
    output_format: str = "json"
    async_mode: bool = True

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    created_at: str
    completed_at: Optional[str] = None
    total_reviews: Optional[int] = None
    error: Optional[str] = None
    output_file: Optional[str] = None

class ReviewResponse(BaseModel):
    review_id: str
    reviewer: str
    rating: str
    review_text: str
    date: str
    company_name: str
    phone_number: str

@app.get("/")
async def root():
    return {
        "message": "Google Maps Review Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "POST /scrape": "Submit a scraping job",
            "GET /job/{job_id}": "Get job status",
            "GET /download/{job_id}": "Download results",
            "GET /health": "Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Check API and ChromeDriver health"""
    try:
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
        driver_exists = os.path.exists(chromedriver_path)
        
        return {
            "status": "healthy",
            "chromedriver_available": driver_exists,
            "chromedriver_path": chromedriver_path
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

def run_scraper_sync(job_id: str, maps_url: str):
    """Synchronous scraper execution"""
    try:
        jobs_db[job_id]["status"] = "processing"
        
        scraper = GoogleMapsScraper(
            maps_url=maps_url,
            chromedriver_path=os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver"),
            headless=True
        )
        
        reviews_data = scraper.scrape()
        
        # Save to file
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{job_id}.json"
        output_path = os.path.join(output_dir, output_file)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(reviews_data, f, indent=4, ensure_ascii=False)
        
        jobs_db[job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "total_reviews": len(reviews_data),
            "output_file": output_path
        })
        
    except Exception as e:
        jobs_db[job_id].update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        })

@app.post("/scrape", response_model=JobStatus)
async def scrape_reviews(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Submit a scraping job for a Google Maps URL
    
    - **maps_url**: Full Google Maps place URL
    - **output_format**: Output format (json only for now)
    - **async_mode**: If true, returns immediately with job_id
    """
    job_id = str(uuid.uuid4())
    
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "maps_url": str(request.maps_url)
    }
    
    if request.async_mode:
        # Run in background
        background_tasks.add_task(run_scraper_sync, job_id, str(request.maps_url))
        return JobStatus(
            job_id=job_id,
            status="pending",
            created_at=jobs_db[job_id]["created_at"]
        )
    else:
        # Run synchronously (blocking)
        run_scraper_sync(job_id, str(request.maps_url))
        job_data = jobs_db[job_id]
        return JobStatus(**job_data)

@app.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a scraping job"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs_db[job_id]
    return JobStatus(**job_data)

@app.get("/download/{job_id}")
async def download_results(job_id: str):
    """Download the scraped results as JSON"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs_db[job_id]
    
    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Job is not completed. Current status: {job_data['status']}"
        )
    
    output_file = job_data.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    return FileResponse(
        path=output_file,
        media_type="application/json",
        filename=f"reviews_{job_id}.json"
    )

@app.get("/reviews/{job_id}", response_model=List[ReviewResponse])
async def get_reviews(job_id: str, limit: Optional[int] = None):
    """Get reviews as JSON response (paginated)"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs_db[job_id]
    
    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job_data['status']}"
        )
    
    output_file = job_data.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    with open(output_file, "r", encoding="utf-8") as f:
        reviews = json.load(f)
    
    if limit:
        reviews = reviews[:limit]
    
    return reviews

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs_db[job_id]
    output_file = job_data.get("output_file")
    
    # Delete file if exists
    if output_file and os.path.exists(output_file):
        os.remove(output_file)
    
    # Remove from database
    del jobs_db[job_id]
    
    return {"message": f"Job {job_id} deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)