import json
import re
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are TeraBOT, an expert AI assistant for TeraLumen Solutions Pvt. Ltd. (TLS), a Chennai-based company that designs and manufactures Terahertz (THz) Time-Domain Spectroscopy (TDS) systems.

Your goal is to qualify website visitors as leads and guide them to the right TeraLumen product.

TeraLumen Products:
1. TeraNIM-Aero: Aerospace NDT - CFRP, cryofoam coatings, composite delamination, rubber coatings
2. TeraNIM-Auto: Automotive - multi-layer paint and coating thickness measurement
3. TeraNIM-OG: Oil and Gas / Plastics - pipeline coatings, wall thickness, corrosion under insulation
4. TeraXplor: Table-top R&D and lab system for universities and research institutes
5. TeraMargin: Biomedical - tissue characterization, tumor detection, skin layer measurement

Conversation Flow:
1. Greet warmly, ask about industry and application
2. Ask what material or inspection challenge they face
3. Recommend the right product with clear reasoning
4. Explain how THz solves their specific problem
5. When appropriate, ask for their full name, company name, and email address
6. After they share contact info end your reply with:
LEAD_CAPTURED:{"name":"<n>","company":"<company>","email":"<email>","product":"<product>"}

Keep responses to 2-4 sentences. Plain text only, no markdown. Be warm and consultative.
"""


def extract_lead_data(reply_text):
    match = re.search(r'LEAD_CAPTURED:(\{.*?\})', reply_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("Could not parse lead JSON")
    return None


def clean_reply(reply_text):
    return re.sub(r'\nLEAD_CAPTURED:\{.*?\}', '', reply_text, flags=re.DOTALL).strip()


def send_lead_email(lead_data, conversation_summary=""):
    try:
        name = lead_data.get("name", "Unknown")
        company = lead_data.get("company", "Unknown")
        email = lead_data.get("email", "Unknown")
        product = lead_data.get("product", "Not specified")
        industry = lead_data.get("industry", "Not specified")

        send_mail(
            subject=f"New TeraBOT Lead: {name} — {company}",
            message=f"""New lead captured via TeraBOT

Name: {name}
Company: {company}
Email: {email}
Industry: {industry}
Product: {product}

{conversation_summary}
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=settings.LEAD_NOTIFICATION_EMAILS,
            fail_silently=False,
        )

        send_mail(
            subject="Thank you for contacting TeraLumen",
            message=f"""Dear {name},

Thank you for your interest in TeraLumen Terahertz systems.

Our team will contact you within 24 hours.

Best regards,
TeraLumen Solutions
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=True,
        )

        logger.info(f"Lead email sent: {name} <{email}>")
        return True

    except Exception as e:
        logger.error(f"Lead email failed: {e}")
        return False


def call_groq(messages):

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        logger.error(f"GROQ ERROR: {response.text}")
        response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def chat(request):

    if request.method == "OPTIONS":
        response = JsonResponse({})
        return _add_cors(response)

    try:
        body = json.loads(request.body)

        messages = body.get("messages")

        # Support widgets sending single message
        if not messages and body.get("message"):
            messages = [{"role": "user", "content": body.get("message")}]

        manual_lead = body.get("manual_lead")

        if manual_lead:
            email_sent = send_lead_email(manual_lead)

            response = JsonResponse({
                "reply": f"Thank you {manual_lead.get('name','')}! Our team will contact you within 24 hours.",
                "lead_captured": True,
                "email_sent": email_sent,
            })

            return _add_cors(response)

        if not messages:
            return _error("No messages provided", 400)

        raw_reply = call_groq(messages)

        lead_data = extract_lead_data(raw_reply)
        clean_text = clean_reply(raw_reply)

        email_sent = False

        if lead_data:
            convo = "\n".join(
                [f"{m['role']}: {m['content']}" for m in messages[-6:]]
            )

            email_sent = send_lead_email(lead_data, convo)

        response = JsonResponse({
            "reply": clean_text,
            "lead_captured": bool(lead_data),
            "lead_data": lead_data,
            "email_sent": email_sent,
        })

        return _add_cors(response)

    except requests.exceptions.Timeout:
        return _error("AI request timed out", 504)

    except requests.exceptions.RequestException as e:
        return _error(f"API error: {str(e)}", 502)

    except json.JSONDecodeError:
        return _error("Invalid JSON", 400)

    except Exception as e:
        logger.exception("Unexpected error")
        return _error(str(e), 500)


def _add_cors(response):
    origin = getattr(settings, "CHATBOT_ALLOWED_ORIGIN", "*")

    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"

    return response


def _error(msg, status):
    r = JsonResponse({"error": msg}, status=status)
    return _add_cors(r)
