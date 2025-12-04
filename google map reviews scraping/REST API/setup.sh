#!/bin/bash

# Google Maps Review Scraper API - Ubuntu Setup Script
# Run with: sudo bash setup.sh

set -e

echo "🚀 Setting up Google Maps Review Scraper API on Ubuntu..."

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install Python 3.11 and pip
echo "🐍 Installing Python 3.11..."
apt-get install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install Chrome dependencies
echo "🌐 Installing Chrome dependencies..."
apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils

# Install Google Chrome
echo "🌐 Installing Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

# Install ChromeDriver
echo "🚗 Installing ChromeDriver..."
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1)
CHROMEDRIVER_VERSION=$(curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}")
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver
rm /tmp/chromedriver.zip

# Verify installations
echo "✅ Verifying installations..."
google-chrome --version
chromedriver --version
python3.11 --version

# Create application directory
echo "📁 Creating application directory..."
mkdir -p /opt/maps-scraper-api
cd /opt/maps-scraper-api

# Create virtual environment
echo "🔧 Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Docker (optional but recommended)
echo "🐳 Installing Docker..."
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
systemctl start docker
systemctl enable docker

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Clone or copy your project files to /opt/maps-scraper-api"
echo "2. Create .env file from .env.example"
echo "3. Install Python dependencies:"
echo "   source /opt/maps-scraper-api/venv/bin/activate"
echo "   pip install -r requirements.txt"
echo "4. Run with Docker:"
echo "   docker-compose up -d"
echo "   OR run directly:"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "🌐 API will be available at http://your-server-ip:8000"
echo "📖 Documentation at http://your-server-ip:8000/docs"