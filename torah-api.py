from flask import Flask, jsonify
import requests
import re
import logging
import os
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CALENDAR_URL = "https://www.sefaria.org/api/calendars"

def fetch_calendar_text(title_en):
    response_today = requests.get(CALENDAR_URL)

    # Calculate tomorrow's date
    tomorrow = datetime.now() + timedelta(days=1)
    year = tomorrow.year
    month = tomorrow.month
    day = tomorrow.day

    # Fetch tomorrow's calendar using year, month, and day parameters
    response_tomorrow = requests.get(CALENDAR_URL, params={"year": year, "month": month, "day": day})

    if response_today.status_code != 200 or response_tomorrow.status_code != 200:
        return None, f"Error fetching calendar: {response_today.status_code} or {response_tomorrow.status_code}"

    data_today = response_today.json()
    data_tomorrow = response_tomorrow.json()


    url_today = next((item['url'] for item in data_today['calendar_items'] if item['title']['en'] == title_en), None)
    url_tomorrow = next((item['url'] for item in data_tomorrow['calendar_items'] if item['title']['en'] == title_en), None)

    if not url_today or not url_tomorrow:
        return None, f"{title_en} not found"

    print(f"Fetching text from URL: https://www.sefaria.org/api/v3/texts/{url_today}")


    # Construct the URL dynamically
    if title_en == "Tanya Yomi":
        range_url = f"https://www.sefaria.org/api/v3/texts/{url_today} - {url_tomorrow}"
    else:
        range_url = f"https://www.sefaria.org/api/v3/texts/{url_today}"

    print(f"Fetching text from range URL: {range_url}")
    text_response_today = requests.get(range_url, params={"version": "english"})

    if text_response_today.status_code != 200:
        return None, f"Error fetching text for {title_en}: {text_response_today.status_code}"

    # Directly access the text field from the JSON response
    text_data_today = text_response_today.json().get('versions', [{}])[0].get('text', [])
    if not isinstance(text_data_today, list):
        text_data_today = []
    text_data_today = ' '.join(text_data_today)

    # Print the extracted text before cleaning
    print(f"Extracted text for Tanya (before cleaning): {text_data_today}")

    # Clean HTML and parentheses
    cleaned = re.sub(r'<.*?>', '', text_data_today)
    cleaned = re.sub(r'\(.*?\)', '', cleaned)

    # Print the cleaned text
    print(f"Cleaned text for Tanya: {cleaned}")

    return cleaned.strip(), None

def summarize_text(input_content, label):
    if not DEEPSEEK_API_KEY:
        return None, "Missing DeepSeek API key"

    if not input_content:
        return None, f"{label} input is empty"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a powerful and exciting Jewish content summarizer. Your job is to create compelling, accurate summaries for torah texts in under 400 words."
            },
            {
                "role": "user",
                "content": f"Summarize the following {label} text for social media. Use short paragraphs, line breaks, and end with a call to action:\n\n{input_content}"
            }
        ],
        "temperature": 0.4,
        "max_tokens": 1000
    }

    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json=payload
    )

    if response.status_code != 200:
        return None, f"{label} summarization error: {response.status_code}"

    data = response.json()
    print(f"📦 Raw DeepSeek response for {label}:")
    print(data)
    summary = data['choices'][0].get('text') or data['choices'][0].get('message', {}).get('content', "No content returned")
    return summary.strip(), None

def fetch_rambam():
    response = requests.get(CALENDAR_URL)

    if response.status_code != 200:
        return None, f"Error fetching calendar: {response.status_code}"

    data = response.json()
    url = next((item['url'] for item in data['calendar_items'] if item['title']['en'] == "Daily Rambam (3 Chapters)"), None)

    if not url:
        return None, "Rambam not found"

    # print(f"Fetching Rambam text from URL: https://www.sefaria.org/api/v3/texts/{url}")
    text_response = requests.get(f"https://www.sefaria.org/api/v3/texts/{url}", params={"version": "english"})

    if text_response.status_code != 200:
        return None, f"Error fetching text for Rambam: {text_response.status_code}"

    text_data = text_response.json().get('versions', [{}])[0].get('text', [])
    print("THIS IS TEXT DATA")
    print(text_data)
    text_data = ' '.join(item for sublist in text_data for item in (sublist if isinstance(sublist, list) else [sublist]))

    # Print the full JSON response for Rambam
    # print(f"Full JSON response for Rambam: {text_response.json()}")

    return text_data.strip(), None

@app.route("/summarize", methods=["POST"])
def summarize_tanya_and_rambam():
    # --- Fetch Tanya ---
    print("fetching tanya")
    tanya_text, error = fetch_calendar_text("Tanya Yomi")
    if error:
        return jsonify({"error": f"Tanya: {error}"}), 500

    print(f"Tanya text fetched: {tanya_text}")
    print(f"Full response for Tanya: {tanya_text}")

    # Print the text being passed to the summarization function
    print(f"Text being summarized for Tanya: {tanya_text}")

    # --- Fetch Rambam ---
    print("fetching Rambam")
    rambam_text, error = fetch_rambam()
    if error:
        return jsonify({"error": f"Rambam: {error}"}), 500

    # Print the fetched Rambam text
    print(f"Rambam text fetched: {rambam_text}")

    # --- Summarize Tanya ---
    print("summarizing Tanya")
    tanya_summary, error = summarize_text(tanya_text, "Tanya")
    if error:
        return jsonify({"error": f"Tanya summary: {error}"}), 500

    print("summarizing Rambam")
    # --- Summarize Rambam ---
    rambam_summary, error = summarize_text(rambam_text, "Rambam")
    if error:
        return jsonify({"error": f"Rambam summary: {error}"}), 500

    return jsonify({
        "tanya_summary": tanya_summary,
        "rambam_summary": rambam_summary
    })


@app.route("/ping", methods=["GET"])
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(port=5001, debug=True)
