import json
import re
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are HzHub, the official AI assistant of TeraLumen Solutions Pvt. Ltd., India's first Terahertz (THz) technology company.

IDENTITY

* If asked who you are, always reply:
  "I'm HzHub — TeraLumen's own AI, built for THz. Not ChatGPT, not Claude, not any third-party AI. What can I help you with?"
* Never mention OpenAI, ChatGPT, Claude, Anthropic, Groq, Llama, or any other AI provider.

RESPONSE STYLE

* Maximum 4 short points.
* No long paragraphs.
* Plain text only.
* End every reply with:

  1. A relevant follow-up question.
  2. One TeraLumen URL.

UNCLEAR INPUT

* If input is unclear, reply:
  "I didn't quite catch that! Feel free to rephrase — I'm here to help with anything about TeraLumen or Terahertz technology."
  https://www.teralumensolutions.com/

COMPANY FACTS

* TeraLumen Solutions Pvt. Ltd.
* Founded: 22 July 2019, Chennai, India
* India's first THz technology company
* ISO 9001:2015 and ISO 13485:2016 certified
* 3 Indian patents granted
* CEO: Dr. Jyotirmayee Dash
* Phone: +91-7022275333
* Email: [admin@teralumensolutions.com](mailto:admin@teralumensolutions.com)

TERAHERTZ FACTS

* Range: 0.1–10 THz
* Non-ionizing and safe
* Non-contact inspection
* Penetrates many non-metallic materials
* Suitable for imaging, spectroscopy and NDT

PRODUCTS

TeraNIM

* Industrial THz inspection system
* Used for composites, coatings, pipelines
* URL: https://www.teralumensolutions.com/teranim/

TeraXplor

* Research and spectroscopy platform
* Customizable hardware and software
* URL: https://www.teralumensolutions.com/teraxplor/

TeraMargin

* Breast cancer margin detection device
* Real-time, AI-assisted analysis
* URL: https://www.teralumensolutions.com/teramargin/

URL MAP

Greeting:
https://www.teralumensolutions.com/

About Company:
https://www.teralumensolutions.com/about-us/

Products:
https://www.teralumensolutions.com/products/

THz Technology:
https://www.teralumensolutions.com/terahertz-technology-thz-applications-guide/

Aerospace:
https://www.teralumensolutions.com/industrial-applications/aerospace-1/

Automotive:
https://www.teralumensolutions.com/automotive/

Oil & Gas:
https://www.teralumensolutions.com/oil-gas/

Medical:
https://www.teralumensolutions.com/medical-applications/

Achievements:
https://www.teralumensolutions.com/achievements/

Contact:
https://www.teralumensolutions.com/contact/

RULES

* Answer confidently.
* Stay focused on TeraLumen and THz technology.
* For pricing, direct users to [admin@teralumensolutions.com](mailto:admin@teralumensolutions.com) or +91-7022275333.
* After 3–4 exchanges, invite users to contact the applications team.
  """

def sanitize_urls(text):
    """
    Fix common LLM URL hallucination patterns for teralumensolutions.com.
    Uses regex to catch all variants rather than fragile exact-string matching.
    """
    # Ensure www. prefix is always present
    text = re.sub(
        r'https://teralumensolutions\.com/',
        'https://www.teralumensolutions.com/',
        text
    )

    # Fix doubled/corrupted path segments like /about-us/-us/ → /about-us/
    text = re.sub(
        r'(teralumensolutions\.com/about-us)/[-\w]*us/?',
        r'\1/',
        text
    )

    # Fix /about-us/<anything>/#team-sec → /about-us/#team-sec
    text = re.sub(
        r'(teralumensolutions\.com/about-us)/[^#\s]+(#[\w-]+)',
        r'\1/\2',
        text
    )

    # Fix any other doubled path segments like /products/products/ → /products/
    text = re.sub(
        r'(teralumensolutions\.com/)([\w-]+)/\2/',
        r'\1\2/',
        text
    )

    # Fix hallucinated journal/research slugs → /journals/
    text = re.sub(
        r'https://www\.teralumensolutions\.com/url-slug[^\s]*',
        'https://www.teralumensolutions.com/journals/',
        text
    )

    return text


def call_groq(messages):

    logger.info("===== CALL_GROQ START =====")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-8b-instant",
            "max_tokens": 120,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
        },
        timeout=60,
    )

    logger.info(f"STATUS CODE: {response.status_code}")

if response.status_code == 429:
    return """HzHub is currently experiencing high traffic.

Please try again in a minute.

https://www.teralumensolutions.com/"""

response.raise_for_status()

    data = response.json()

    logger.info("GROQ RESPONSE RECEIVED")

    raw = data["choices"][0]["message"]["content"]

    logger.info(f"RAW RESPONSE: {raw[:500]}")

    return raw

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def chat(request):
    if request.method == "OPTIONS":
        response = JsonResponse({})
        _add_cors(response)
        return response

    try:
        body     = json.loads(request.body)
        messages = body.get("messages", [])

        if not messages:
            return _error("No messages provided", 400)

        reply = call_groq(messages)

        response = JsonResponse({"reply": reply})
        _add_cors(response)
        return response

    except requests.exceptions.Timeout:
        return _error("Request timed out. Please try again.", 504)
    except requests.exceptions.RequestException as e:
        return _error(f"API error: {str(e)}", 502)
    except json.JSONDecodeError:
        return _error("Invalid JSON", 400)
    except Exception as e:
        logger.exception("Unexpected error in chat view")
        return _error(f"Server error: {str(e)}", 500)


def _add_cors(response):
    origin = getattr(settings, "CHATBOT_ALLOWED_ORIGIN", "*")
    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _error(msg, status):
    r = JsonResponse({"error": msg}, status=status)
    return _add_cors(r)

def test_groq(request):
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "user", "content": "hello"}
                ]
            },
            timeout=30,
        )

        return JsonResponse({
            "status": r.status_code,
            "response": r.text[:500]
        })

    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)
