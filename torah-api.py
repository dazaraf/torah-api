from flask import Flask, jsonify
import requests
import re
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CALENDAR_URL = "https://www.sefaria.org/api/calendars"

def fetch_calendar_text(title_en):
    response = requests.get(CALENDAR_URL)
    print(f"Response from Sefaria for calendar: {response.json()}")
    if response.status_code != 200:
        return None, f"Error fetching calendar: {response.status_code}"

    data = response.json()
    url = next((item['url'] for item in data['calendar_items'] if item['title']['en'] == title_en), None)

    if not url:
        return None, f"{title_en} not found"

    text_response = requests.get(f"https://www.sefaria.org/api/v3/texts/{url}")
    print(f"Response from Sefaria for {title_en}: {text_response.json()}")
    if text_response.status_code != 200:
        return None, f"Error fetching text for {title_en}: {text_response.status_code}"

    text_data = text_response.json().get('text', [])
    if isinstance(text_data, list):
        # Flatten if list of lists
        text_data = ' '.join(item for sublist in text_data for item in (sublist if isinstance(sublist, list) else [sublist]))

    # Clean HTML and parentheses
    cleaned = re.sub(r'<.*?>', '', text_data)
    cleaned = re.sub(r'\(.*?\)', '', cleaned)

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
                "content": "You are a powerful and exciting Jewish content summarizer. Your job is to create compelling, accurate summaries for Tanya and Rambam in under 150 words."
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

@app.route("/summarize", methods=["POST"])
def summarize_tanya_and_rambam():
    # --- Fetch Tanya ---
    print("fetching tanya")
    tanya_text, error = fetch_calendar_text("Tanya Yomi")
    if error:
        return jsonify({"error": f"Tanya: {error}"}), 500

    print(f"Tanya text fetched: {tanya_text}")

    # --- Fetch Rambam ---
    print("fetching Rambam")
    rambam_text, error = fetch_calendar_text("Daily Rambam (3 Chapters)")
    if error:
        return jsonify({"error": f"Rambam: {error}"}), 500

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
