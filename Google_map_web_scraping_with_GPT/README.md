# 🤖 Intelligent Web Scraper: Google Maps + LLM-Powered Website Analyzer

### Automated Business Data Extraction Using OpenAI + Selenium + BeautifulSoup

This project is an **AI-enhanced web scraper** built for **Google Colab** or local Python environments.  
It extracts structured business information (name, emails, phones, social links, description) from any **Google Maps business URL** by automatically detecting the linked website and intelligently analyzing its most relevant pages using an **LLM (OpenAI GPT-4o-mini)**.

---

## 🚀 Features

- ✅ **Google Maps Website Extractor** – Automatically detects the business’s main website.  
- 🕷️ **Smart Web Crawler** – Crawls only relevant internal pages while skipping irrelevant or static assets.  
- 🧠 **LLM-Powered Page Selection** – Uses OpenAI GPT-4o-mini to pick pages like *About*, *Services*, *Contact*, *Home* automatically.  
- 📄 **Content Extraction** – Extracts visible, meaningful text from selected pages using BeautifulSoup.  
- 📊 **LLM Data Consolidation** – Combines extracted text and uses GPT to summarize and structure business data.  
- 💾 **JSON Output + Download** – Saves results (including metadata) as a downloadable JSON file.  
- ⚙️ **Colab-Ready** – Automatically detects OpenAI keys from Colab Secrets and handles driver setup with `webdriver-manager`.

---

## 🧩 Architecture Overview

| Step | Component | Description |
|------|------------|-------------|
| 1️⃣ | **Google Maps Parser** | Extracts main website from a Maps business link using Selenium or fallback HTML parsing. |
| 2️⃣ | **Crawler** | Discovers internal URLs recursively with domain-based filtering. |
| 3️⃣ | **LLM Page Ranker** | GPT model analyzes all URLs to select the most relevant pages for analysis. |
| 4️⃣ | **Content Extractor** | Scrapes readable text and cleans scripts, headers, and footers. |
| 5️⃣ | **Data Synthesizer** | GPT consolidates all text into structured business data JSON. |
| 6️⃣ | **Saver + Display** | Saves results with metadata and prints a summary in console. |

---

## 🧠 Extracted Data Fields

Each run produces a structured JSON file with:

```json
{
  "business_data": {
    "company_name": "Dynamic Clinic Pakistan",
    "company_main_url": "https://www.dynamiclinic.com.pk",
    "emails": ["info@dynamiclinic.com.pk"],
    "contact_numbers": ["+92 300 1234567"],
    "social_media_links": ["https://facebook.com/dynamicclinicpk"],
    "summary": "Dynamic Clinic Pakistan is a leading cosmetic surgery center offering..."
  },
  "extraction_metadata": {
    "total_pages_discovered": 30,
    "pages_analyzed": 6,
    "extraction_method": "LLM-powered intelligent page selection",
    "timestamp": "2025-11-12 01:11:53",
    "model_used": "gpt-4o-mini"
  }
}
