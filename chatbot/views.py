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

Keep responses to 2-4 sentences. Plain text only, no markdown. Be warm and consultative."""


def extract_lead_data(reply_text):
    match = re.search(r'LEAD_CAPTURED:(\{.*?\})', reply_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("Could not parse lead JSON from reply")
    return None


def clean_reply(reply_text):
    return re.sub(r'\nLEAD_CAPTURED:\{.*?\}', '', reply_text, flags=re.DOTALL).strip()


def send_lead_email(lead_data, conversation_summary=""):
    try:
        name     = lead_data.get("name", "Unknown")
        company  = lead_data.get("company", "Unknown")
        email    = lead_data.get("email", "Unknown")
        product  = lead_data.get("product", "Not specified")
        industry = lead_data.get("industry", "Not specified")

        send_mail(
            subject=f"New TeraBOT Lead: {name} — {company}",
            message=f"""New lead captured via TeraBOT on TeraLumen website.

LEAD DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━
Name      : {name}
Company   : {company}
Email     : {email}
Industry  : {industry}
Product   : {product}
━━━━━━━━━━━━━━━━━━━━━━━━

{f"CONVERSATION:{chr(10)}{conversation_summary}" if conversation_summary else ""}

Action: Follow up within 24 hours.

— TeraBOT Automated Alert
TeraLumen Solutions Pvt. Ltd., Chennai""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=settings.LEAD_NOTIFICATION_EMAILS,
            fail_silently=False,
        )

        send_mail(
            subject="Thank you for your interest in TeraLumen THz Systems",
            message=f"""Dear {name},

Thank you for your interest in TeraLumen's Terahertz solutions!

Our applications team has received your enquiry and will reach out within 24 hours.

Enquiry Summary:
  Name     : {name}
  Company  : {company}
  Industry : {industry}
  Product  : {product}

Explore our products: https://www.teralumen.com

Best regards,
Applications Team
TeraLumen Solutions Pvt. Ltd., Chennai""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=True,
        )

        logger.info(f"Lead email sent: {name} <{email}>")
        return True

    except Exception as e:
        logger.error(f"Failed to send lead email: {e}")
        return False


def call_groq(messages):
    """Call Groq API — free, fast, no credit card needed."""
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama3-8b-8192",   # free model on Groq
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def chat(request):
    if request.method == "OPTIONS":
        response = JsonResponse({})
        _add_cors(response)
        return response

    try:
        body        = json.loads(request.body)
        messages    = body.get("messages", [])
        manual_lead = body.get("manual_lead", None)

        # Manual Submit button trigger
        if manual_lead:
            email_sent = send_lead_email(manual_lead)
            response = JsonResponse({
                "reply": f"Thank you {manual_lead.get('name', '')}! Your details have been submitted. Our team will contact you within 24 hours.",
                "lead_captured": True,
                "email_sent": email_sent,
            })
            _add_cors(response)
            return response

        if not messages:
            return _error("No messages provided", 400)

        # Call Groq AI
        raw_reply  = call_groq(messages)
        lead_data  = extract_lead_data(raw_reply)
        clean_text = clean_reply(raw_reply)
        email_sent = False

        if lead_data:
            convo = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages[-6:]])
            email_sent = send_lead_email(lead_data, convo)

        response = JsonResponse({
            "reply": clean_text,
            "lead_captured": bool(lead_data),
            "lead_data": lead_data,
            "email_sent": email_sent,
        })
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