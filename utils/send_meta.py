
import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")


def send_meta_whatsapp_message(recipient_wa_id, message_text):
    if not WHATSAPP_BUSINESS_ACCOUNT_ID or not PAGE_ACCESS_TOKEN:
        logging.error("❌ Missing WHATSAPP_BUSINESS_ACCOUNT_ID or PAGE_ACCESS_TOKEN.")
        return False

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_wa_id,
        "type": "text",
        "text": {"body": message_text},
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"✅ Message sent to {recipient_wa_id}. Meta Response: {response.json()}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error sending message: {e}")
        if hasattr(e, "response") and e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return False
