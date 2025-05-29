import os
import json
from typing import Optional
from thefuzz import fuzz
import logging

# إعداد الـ Logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

# كشف اللغة (بسيط)
def detect_language(text):
    if any(word in text for word in ['السلام', 'عليكم', 'مرحبا', 'اهلاً', 'أهلاً', 'عربي']):
        return "ar"
    elif any(word in text.lower() for word in ['hello', 'hi', 'english']):
        return "en"
    else:
        return "ar"  # الديفولت عربي

# مسارات الملفات
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")
REPLIES_FILE = os.path.join(CONFIG_DATA_PATH, "replies.json")
FAQ_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "faq_data.json")

# تحميل JSON لأي ملف
def _load_json_data(file_path: str):
    try:
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"File is empty: {file_path}")
                return {}
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading JSON from {file_path}: {e}", exc_info=True)
        return {}

# جلب الرد من replies.json
def get_reply_from_json(reply_key: str, lang: str = "ar", **kwargs) -> str:
    replies_content = _load_json_data(REPLIES_FILE)
    key_obj = replies_content.get(reply_key)
    if not key_obj:
        logger.warning(f"Reply key '{reply_key}' not found in replies.json.")
        return f"Error: Reply key '{reply_key}' not found."
    # يدور على اللغة المطلوبة
    message_template = key_obj.get(lang)
    if not message_template:
        # جرب الإنجليزي كـ fallback
        message_template = key_obj.get("en", f"Error: No message for key '{reply_key}' and lang '{lang}'.")
    try:
        return message_template.format(**kwargs)
    except Exception as e:
        logger.warning(f"Error formatting message for key '{reply_key}' and lang '{lang}': {e}")
        return message_template

# جلب الردود الثابتة (FAQ) من faq_data.json
def get_static_reply(user_message: str, lang: str, threshold: int = 75) -> Optional[str]:
    faq_content = _load_json_data(FAQ_DATA_FILE)
    user_message_lower = user_message.lower().strip()
    best_score = 0
    best_answer = None
    for _, faq_item in faq_content.items():
        keywords_key = f"keywords_{lang}"
        answer_key = f"answer_{lang}"
        if keywords_key not in faq_item or answer_key not in faq_item:
            continue
        for keyword in faq_item[keywords_key]:
            score = fuzz.token_set_ratio(user_message_lower, keyword.lower())
            if score >= threshold and score > best_score:
                best_score = score
                best_answer = faq_item[answer_key]
    return best_answer

# دوال قاعدة البيانات (استخدمها لو عايز تربط بسرعة من أي مكان)
from utils.db_helpers import (
    get_customer,
    add_or_update_customer,
    add_message,
    get_conversation,
)

def get_user_language(phone_number: str) -> str:
    """استرجاع لغة العميل (من قاعدة البيانات)، يرجع 'en' افتراضي إذا غير موجود."""
    user_obj = get_customer(phone_number)
    return user_obj.language if user_obj and user_obj.language else "en"
