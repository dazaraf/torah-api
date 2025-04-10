from flask import Flask, jsonify
import requests
import re
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure logging to show all messages
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all messages
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Also configure Flask's logger
app.logger.setLevel(logging.DEBUG)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
app.logger.debug(f"Loaded DeepSeek API Key: {'Present' if DEEPSEEK_API_KEY else 'Missing'}")

if not DEEPSEEK_API_KEY:
    app.logger.error("DeepSeek API key is missing! Please check your .env file")

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

    app.logger.debug(f"Fetching text from URL: https://www.sefaria.org/api/v3/texts/{url_today}")

    # Construct the URL dynamically
    if title_en == "Tanya Yomi":
        range_url = f"https://www.sefaria.org/api/v3/texts/{url_today} - {url_tomorrow}"
    else:
        range_url = f"https://www.sefaria.org/api/v3/texts/{url_today}"

    app.logger.debug(f"Fetching text from range URL: {range_url}")
    text_response_today = requests.get(range_url, params={"version": "english"})

    if text_response_today.status_code != 200:
        return None, f"Error fetching text for {title_en}: {text_response_today.status_code}"

    # Directly access the text field from the JSON response
    text_data_today = text_response_today.json().get('versions', [{}])[0].get('text', [])
    if not isinstance(text_data_today, list):
        text_data_today = []
    
    # Handle nested lists by flattening them
    def flatten_list(lst):
        result = []
        for item in lst:
            if isinstance(item, list):
                result.extend(flatten_list(item))
            else:
                result.append(str(item))
        return result
    
    text_data_today = flatten_list(text_data_today)
    text_data_today = ' '.join(text_data_today)

    # Print the extracted text before cleaning
    app.logger.debug(f"Extracted text for {title_en} (before cleaning): {text_data_today}")

    # Clean HTML and parentheses
    cleaned = re.sub(r'<.*?>', '', text_data_today)
    cleaned = re.sub(r'\(.*?\)', '', cleaned)

    # Print the cleaned text
    app.logger.debug(f"Cleaned text for {title_en}: {cleaned}")

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

    app.logger.debug(f"Sending request to DeepSeek API for {label}")
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json=payload
    )

    if response.status_code != 200:
        return None, f"{label} summarization error: {response.status_code}"

    data = response.json()
    app.logger.debug(f"📦 Raw DeepSeek response for {label}:")
    app.logger.debug(data)
    summary = data['choices'][0].get('text') or data['choices'][0].get('message', {}).get('content', "No content returned")
    return summary.strip(), None

# def fetch_rambam():
#     response = requests.get(CALENDAR_URL)

#     if response.status_code != 200:
#         return None, f"Error fetching calendar: {response.status_code}"

#     data = response.json()
#     url = next((item['url'] for item in data['calendar_items'] if item['title']['en'] == "Daily Rambam (3 Chapters)"), None)

#     if not url:
#         return None, "Rambam not found"

#     app.logger.debug(f"Fetching Rambam text from URL: https://www.sefaria.org/api/v3/texts/{url}")
#     text_response = requests.get(f"https://www.sefaria.org/api/v3/texts/{url}", params={"version": "english"})

#     if text_response.status_code != 200:
#         return None, f"Error fetching text for Rambam: {text_response.status_code}"

#     text_data = text_response.json().get('versions', [{}])[0].get('text', [])
#     app.logger.debug("Rambam text data received")
#     text_data = ' '.join(item for sublist in text_data for item in (sublist if isinstance(sublist, list) else [sublist]))

#     return text_data.strip(), None

@app.route("/summarize", methods=["POST"])
def summarize_tanya_and_rambam():
    # --- Fetch Tanya ---
    app.logger.debug("fetching tanya")
    tanya_text, error = fetch_calendar_text("Tanya Yomi")
    if error:
        return jsonify({"error": f"Tanya: {error}"}), 500

    app.logger.debug(f"Tanya text fetched: {tanya_text}")

    # --- Fetch Rambam ---
    app.logger.debug("fetching Rambam")
    rambam_text, error = fetch_calendar_text("Daily Rambam (3 Chapters)")
    if error:
        return jsonify({"error": f"Rambam: {error}"}), 500

    app.logger.debug(f"Rambam text fetched: {rambam_text}")

    # --- Fetch Daf Yomi ---
    app.logger.debug("fetching Daf Yomi")
    daf_yomi_text, error = fetch_calendar_text("Daf Yomi")
    if error:
        return jsonify({"error": f"Daf Yomi: {error}"}), 500

    app.logger.debug(f"Daf Yomi text fetched: {daf_yomi_text}")

    # --- Fetch Halakhah Yomit ---
    app.logger.debug("fetching Halakhah Yomit")
    halakhah_text, error = fetch_calendar_text("Halakhah Yomit")
    if error:
        return jsonify({"error": f"Halakhah Yomit: {error}"}), 500

    app.logger.debug(f"Halakhah Yomit text fetched: {halakhah_text}")

    # --- Summarize Tanya ---
    app.logger.debug("summarizing Tanya")
    tanya_summary, error = summarize_text(tanya_text, "Tanya")
    if error:
        return jsonify({"error": f"Tanya summary: {error}"}), 500

    # --- Summarize Rambam ---
    app.logger.debug("summarizing Rambam")
    rambam_summary, error = summarize_text(rambam_text, "Rambam")
    if error:
        return jsonify({"error": f"Rambam summary: {error}"}), 500

    # --- Summarize Daf Yomi ---
    app.logger.debug("summarizing Daf Yomi")
    daf_yomi_summary, error = summarize_text(daf_yomi_text, "Daf Yomi")
    if error:
        return jsonify({"error": f"Daf Yomi summary: {error}"}), 500

    # --- Summarize Halakhah Yomit ---
    app.logger.debug("summarizing Halakhah Yomit")
    halakhah_summary, error = summarize_text(halakhah_text, "Halakhah Yomit")
    if error:
        return jsonify({"error": f"Halakhah Yomit summary: {error}"}), 500

    return jsonify({
        "tanya_summary": tanya_summary,
        "rambam_summary": rambam_summary,
        "daf_yomi_summary": daf_yomi_summary,
        "halakhah_yomit_summary": halakhah_summary
    })


@app.route("/ping", methods=["GET"])
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(port=5001, debug=True)
