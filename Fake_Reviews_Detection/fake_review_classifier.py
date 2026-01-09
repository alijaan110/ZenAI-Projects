#!/usr/bin/env python3
"""
Production-grade fake review classifier using LLM-based approach.
Designed for Google Colab with OpenAI API.
"""

import json
import sys
from typing import Dict, List, Any
from google.colab import userdata
import openai

# Configuration
MODEL_NAME = "gpt-4o-mini"
TEMPERATURE = 0.1  # Low temperature for deterministic output
MAX_TOKENS = 300

# System prompt for LLM
SYSTEM_PROMPT = """You are a review authenticity analyzer. Analyze ONLY the linguistic patterns, writing style, and internal consistency of the review text.

Output ONLY valid JSON in this exact format:
{
  "label": "likely_real" or "uncertain" or "likely_fake",
  "risk_score": <integer 0-100>,
  "confidence": <float 0.0-1.0>,
  "reasons": [<string>, <string>, <string>]
}

Classification guidelines:
- likely_real: Natural language, specific details, balanced tone, coherent narrative
- uncertain: Mixed signals, insufficient context, ambiguous patterns
- likely_fake: Generic language, excessive emotion, promotional tone, vague claims

Be conservative. Favor "uncertain" when signals are mixed.
Output ONLY the JSON object. No explanations, no preamble, no markdown."""


def load_reviews(filepath: str) -> List[Dict[str, Any]]:
    """Load reviews from JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File {filepath} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        sys.exit(1)


def classify_review(review_text: str, rating: int, api_key: str) -> Dict[str, Any]:
    """Classify a single review using OpenAI API."""
    client = openai.OpenAI(api_key=api_key)
    
    user_prompt = f"""Review Text: {review_text}
Rating: {rating}/5

Analyze this review and output JSON only."""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        result = json.loads(result_text)
        
        # Validate required fields
        required_fields = ["label", "risk_score", "confidence", "reasons"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        return result
        
    except json.JSONDecodeError:
        return {
            "label": "uncertain",
            "risk_score": 50,
            "confidence": 0.0,
            "reasons": ["Error: Failed to parse LLM response"]
        }
    except Exception as e:
        return {
            "label": "uncertain",
            "risk_score": 50,
            "confidence": 0.0,
            "reasons": [f"Error: {str(e)}"]
        }


def process_reviews(reviews: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    """Process all reviews and return classification results."""
    results = []
    
    for idx, review in enumerate(reviews, 1):
        review_text = review.get("review_text", "")
        rating = review.get("rating", 3)
        
        print(f"Processing review {idx}/{len(reviews)}...", end="\r")
        
        classification = classify_review(review_text, rating, api_key)
        
        result = {
            "review_text": review_text,
            "rating": rating,
            "classification": classification
        }
        
        results.append(result)
    
    print(f"\nProcessed {len(results)} reviews successfully.")
    return results


def main():
    """Main entry point."""
    # Get API key from Colab secrets
    try:
        api_key = userdata.get('OPENAI_API_KEY')
    except Exception as e:
        print("Error: Could not retrieve OPENAI_API_KEY from Colab secrets.")
        print("Please add your OpenAI API key to Colab secrets with key name 'OPENAI_API_KEY'")
        sys.exit(1)
    
    # Load reviews
    input_file = "sample_reviews.json"
    reviews = load_reviews(input_file)
    
    print(f"Loaded {len(reviews)} reviews from {input_file}")
    
    # Process reviews
    results = process_reviews(reviews, api_key)
    
    # Save results
    output_file = "classification_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to {output_file}")
    
    # Print summary statistics
    label_counts = {"likely_real": 0, "uncertain": 0, "likely_fake": 0}
    for result in results:
        label = result["classification"]["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
    
    print("\n=== Classification Summary ===")
    for label, count in label_counts.items():
        percentage = (count / len(results)) * 100
        print(f"{label}: {count} ({percentage:.1f}%)")


if __name__ == "__main__":
    main()
