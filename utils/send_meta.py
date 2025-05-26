# utils/send_meta.py
import requests
import os
import json
import logging

# --- إعداد الـ Logger ---
# الأفضل إن الـ logger يتجاب من الـ app الرئيسي لو أمكن (عشان يكون مركزي)
# بس لو هنعرفه هنا بشكل مستقل:
logger = logging.getLogger(__name__) # اسم الموديول الحالي كاسم للوجر
# مستوى اللوجينج المفروض يتحدد في app.py بشكل عام
# لو مفيش إعدادات لوجينج عامة، ممكن نضيف هنا:
if not logger.hasHandlers(): # عشان نتجنب إضافة handlers كذا مرة لو الموديول اتعمله import كذا مرة
    handler = logging.StreamHandler() # يطبع على الـ console
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # أو DEBUG لو عايز تفاصيل أكتر

# --- تحميل متغيرات البيئة المطلوبة ---
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# --- التحقق من وجود متغيرات البيئة عند تحميل الموديول ---
if not WHATSAPP_ACCESS_TOKEN:
    logger.critical("CRITICAL ERROR in send_meta: WHATSAPP_ACCESS_TOKEN is not set in environment variables!")
if not WHATSAPP_PHONE_NUMBER_ID:
    logger.critical("CRITICAL ERROR in send_meta: WHATSAPP_PHONE_NUMBER_ID is not set in environment variables!")

def send_whatsapp_message_real(recipient_wa_id: str, message_text: str) -> bool:
    """
    Sends a text message to a WhatsApp user via the WhatsApp Cloud API (Meta Graph API).

    Args:
        recipient_wa_id (str): The WhatsApp ID of the recipient (e.g., "201001234567").
        message_text (str): The text content of the message to send.

    Returns:
        bool: True if the message was likely sent successfully (API returned 2xx), False otherwise.
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.error(
            f"Cannot send message to {recipient_wa_id}: WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID is missing."
        )
        return False

    api_version = os.getenv("WHATSAPP_API_VERSION", "v19.0") # ممكن تخلي نسخة الـ API في .env
    url = f"https://graph.facebook.com/{api_version}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_wa_id,
        "type": "text",
        "text": {"body": message_text},
    }

    logger.info(f"Attempting to send WhatsApp message to: {recipient_wa_id}")
    logger.debug(f"Payload for {recipient_wa_id}: {json.dumps(payload, ensure_ascii=False)}") # debug level للتفاصيل

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15) # زودت الـ timeout شوية
        
        # التحقق من الـ status code
        if 200 <= response.status_code < 300:
            logger.info(
                f"Message successfully sent to {recipient_wa_id}. "
                f"API Response Status: {response.status_code}, "
                f"Response Body: {response.text}" # ممكن يكون فيه message_id مفيد
            )
            return True
        else:
            logger.error(
                f"Failed to send message to {recipient_wa_id}. "
                f"API Response Status: {response.status_code}, "
                f"Response Body: {response.text}"
            )
            # تحليل إضافي لبعض الأخطاء الشائعة
            if response.status_code == 401:
                logger.critical(
                    "Authorization error (401) sending WhatsApp message. "
                    "The WHATSAPP_ACCESS_TOKEN may be invalid, expired, or missing required permissions."
                )
            elif response.status_code == 400:
                try:
                    error_data = response.json().get("error", {})
                    error_message = error_data.get("message", "No error message provided.")
                    error_code = error_data.get("code")
                    error_subcode = error_data.get("error_subcode")
                    logger.warning(
                        f"Bad Request (400) details: Code={error_code}, Subcode={error_subcode}, Message='{error_message}'"
                    )
                except ValueError: # لو الـ response مش JSON
                    logger.warning("Bad Request (400) but response body was not valid JSON.")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"Timeout error while trying to send message to {recipient_wa_id}.")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while trying to send message to {recipient_wa_id}.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"An unexpected requests library error occurred for {recipient_wa_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"A general unexpected error occurred in send_whatsapp_message_real for {recipient_wa_id}: {e}", exc_info=True)
        return False
