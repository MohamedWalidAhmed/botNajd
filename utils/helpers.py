import os
import json
from typing import Dict, Any, Optional, List
from thefuzz import fuzz
import logging

# --- إعداد الـ Logger ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

# --- تحديد المسارات (للملفات الثابتة فقط مثل replies, faq) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")
REPLIES_FILE = os.path.join(CONFIG_DATA_PATH, "replies.json")
FAQ_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "faq_data.json")

# --- دوال تحميل JSON للردود والـ FAQ فقط ---
def _load_json_data(file_path: str):
    try:
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading JSON from {file_path}: {e}", exc_info=True)
        return {}

# --- الردود الجاهزة والـ FAQ ---
def get_reply_from_json(reply_key: str, lang: str, **kwargs) -> str:
    replies_content = _load_json_data(REPLIES_FILE)
    message_template = replies_content.get(reply_key, {}).get(lang)
    if not message_template:
        message_template = replies_content.get(reply_key, {}).get("en", f"Error: Reply key '{reply_key}' not found.")
    try:
        return message_template.format(**kwargs)
    except Exception:
        return message_template

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

# --- استيراد الدوال من db_helpers لبيانات العميل والمحادثة ---
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

# (ممكن تضيف دوال مختصرة لو محتاجها، لكنها مجرد واجهة للدوال الأساسية من db_helpers)
