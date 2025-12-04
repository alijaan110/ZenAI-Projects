# Google Maps Review Scraper - REST API

A production-ready REST API for scraping Google Maps reviews using Selenium WebDriver and FastAPI.

## 🚀 Features

- ✅ **RESTful API** with FastAPI
- ✅ **Async job processing** with background tasks
- ✅ **Docker support** for easy deployment
- ✅ **Headless Chrome** scraping with anti-detection
- ✅ **Automatic pagination** and scroll handling
- ✅ **JSON export** of all review data
- ✅ **Health check** endpoints
- ✅ **Interactive API docs** (Swagger/OpenAPI)

## 📋 Requirements

- Python 3.11+
- Google Chrome
- ChromeDriver
- Docker (optional but recommended)

## 🛠️ Installation

### Option 1: Docker (Recommended)

1. **Clone the repository**
```bash
git clone <your-repo>
cd maps-scraper-api
```

2. **Build and run with Docker Compose**
```bash
docker-compose up -d
```

3. **Access the API**
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs

### Option 2: Manual Installation (Ubuntu)

1. **Run the setup script**
```bash
sudo bash setup.sh
```

2. **Copy project files**
```bash
cp -r app /opt/maps-scraper-api/
cp requirements.txt /opt/maps-scraper-api/
```

3. **Install Python dependencies**
```bash
cd /opt/maps-scraper-api
source venv/bin/activate
pip install -r requirements.txt
```

4. **Run the application**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option 3: Systemd Service (Production)

1. **Copy the service file**
```bash
sudo cp maps-scraper.service /etc/systemd/system/
```

2. **Enable and start the service**
```bash
sudo systemctl enable maps-scraper
sudo systemctl start maps-scraper
```

3. **Check status**
```bash
sudo systemctl status maps-scraper
```

## 📡 API Endpoints

### 1. Health Check
```bash
GET /health
```

### 2. Submit Scraping Job
```bash
POST /scrape
Content-Type: application/json

{
  "maps_url": "https://www.google.com/maps/place/...",
  "output_format": "json",
  "async_mode": true
}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "pending",
  "created_at": "2025-01-15T10:30:00"
}
```

### 3. Check Job Status
```bash
GET /job/{job_id}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "completed",
  "created_at": "2025-01-15T10:30:00",
  "completed_at": "2025-01-15T10:35:00",
  "total_reviews": 150,
  "output_file": "output/uuid-here.json"
}
```

### 4. Download Results
```bash
GET /download/{job_id}
```

Returns JSON file with all scraped reviews.

### 5. Get Reviews as JSON
```bash
GET /reviews/{job_id}?limit=50
```

Returns reviews as JSON response (paginated).

### 6. Delete Job
```bash
DELETE /job/{job_id}
```

## 🧪 Usage Examples

### Using cURL

```bash
# Submit a job
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "maps_url": "https://www.google.com/maps/place/Semicolon+Cafe/@47.6119559,-122.200889,17z/...",
    "async_mode": true
  }'

# Check status
curl "http://localhost:8000/job/{job_id}"

# Download results
curl "http://localhost:8000/download/{job_id}" -o reviews.json
```

### Using Python

```python
import requests
import time

# Submit job
response = requests.post("http://localhost:8000/scrape", json={
    "maps_url": "https://www.google.com/maps/place/...",
    "async_mode": True
})
job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"http://localhost:8000/job/{job_id}").json()
    print(f"Status: {status['status']}")
    
    if status["status"] == "completed":
        break
    elif status["status"] == "failed":
        print(f"Error: {status['error']}")
        break
    
    time.sleep(5)

# Download results
reviews = requests.get(f"http://localhost:8000/reviews/{job_id}").json()
print(f"Total reviews: {len(reviews)}")
```

### Using JavaScript/Node.js

```javascript
const axios = require('axios');

async function scrapeReviews(mapsUrl) {
  // Submit job
  const { data } = await axios.post('http://localhost:8000/scrape', {
    maps_url: mapsUrl,
    async_mode: true
  });
  
  const jobId = data.job_id;
  console.log(`Job submitted: ${jobId}`);
  
  // Poll for completion
  while (true) {
    const status = await axios.get(`http://localhost:8000/job/${jobId}`);
    console.log(`Status: ${status.data.status}`);
    
    if (status.data.status === 'completed') {
      break;
    } else if (status.data.status === 'failed') {
      throw new Error(status.data.error);
    }
    
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
  
  // Get reviews
  const reviews = await axios.get(`http://localhost:8000/reviews/${jobId}`);
  return reviews.data;
}

scrapeReviews('https://www.google.com/maps/place/...')
  .then(reviews => console.log(`Got ${reviews.length} reviews`))
  .catch(console.error);
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file:

```bash
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
HEADLESS=true
WAIT_TIMEOUT=20
SCROLL_PAUSE=1.5
MAX_SCROLLS=500
```

### Nginx Reverse Proxy

1. Install Nginx:
```bash
sudo apt install nginx
```

2. Copy configuration:
```bash
sudo cp nginx.conf /etc/nginx/sites-available/maps-scraper
sudo ln -s /etc/nginx/sites-available/maps-scraper /etc/nginx/sites-enabled/
```

3. Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 📊 Response Format

Each review contains:

```json
{
  "review_id": "unique-google-id",
  "reviewer": "John Doe",
  "rating": "5 stars",
  "review_text": "Great place! Highly recommend...",
  "date": "2 months ago",
  "company_name": "Semicolon Cafe",
  "phone_number": "+1 234 567 8900"
}
```

## 🐛 Troubleshooting

### ChromeDriver version mismatch
```bash
# Check Chrome version
google-chrome --version

# Install matching ChromeDriver
CHROME_VERSION=131
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}
```

### Permission issues
```bash
sudo chown -R www-data:www-data /opt/maps-scraper-api
sudo chmod +x /usr/local/bin/chromedriver
```

### Docker issues
```bash
# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# View logs
docker-compose logs -f api
```

## 📝 Notes

- Scraping may take several minutes for places with many reviews
- Google Maps may rate-limit or block excessive requests
- Use responsibly and respect Google's Terms of Service
- Consider adding delays between requests for large-scale scraping

## 🔒 Security Considerations

- Add authentication (JWT, API keys) for production use
- Use HTTPS (Let's Encrypt SSL)
- Implement rate limiting
- Add input validation and sanitization
- Use Redis for persistent job storage instead of in-memory dict

## 📄 License

MIT License - Feel free to use and modify

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

---

**Made with ❤️ using FastAPI and Selenium**
    