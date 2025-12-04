from celery import Celery
import os
from scraper import GoogleMapsScraper

# Initialize Celery
celery_app = Celery(
    'scraper_tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10
)

@celery_app.task(bind=True, name='scrape_task')
def scrape_task(self, maps_url: str, job_id: str):
    """
    Celery task to scrape Google Maps reviews
    
    Args:
        maps_url: Google Maps URL to scrape
        job_id: Unique job identifier
    
    Returns:
        Dictionary with job results
    """
    try:
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Starting scraper...'})
        
        scraper = GoogleMapsScraper(
            maps_url=maps_url,
            chromedriver_path=os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver"),
            headless=True
        )
        
        self.update_state(state='PROGRESS', meta={'status': 'Scraping reviews...'})
        
        reviews_data = scraper.scrape()
        
        # Save to file
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{job_id}.json"
        output_path = os.path.join(output_dir, output_file)
        
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(reviews_data, f, indent=4, ensure_ascii=False)
        
        return {
            'status': 'completed',
            'total_reviews': len(reviews_data),
            'output_file': output_path,
            'job_id': job_id
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'job_id': job_id
        }

# Run worker with: celery -A app.celery_worker worker --loglevel=info