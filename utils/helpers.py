import os
import json
from typing import Dict, Any, Optional, List
from thefuzz import fuzz
import logging

# --- إعداد الـ Logger ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

# --- تحديد المسارات ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")
CUSTOMERS_PATH = os.path.join(BASE_DIR, "customers")
CONVERSATION_HISTORY_PATH = os.path.join(BASE_DIR, "conversation_history")

os.makedirs(CONFIG_DATA_PATH, exist_ok=True)
os.makedirs(CUSTOMERS_PATH, exist_ok=True)
os.makedirs(CONVERSATION_HISTORY_PATH, exist_ok=True)

REPLIES_FILE = os.path.join(CONFIG_DATA_PATH, "replies.json")
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_PATH, "customer_data.json")
FAQ_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "faq_data.json")

# --- دوال تحميل/حفظ JSON موحدة ---
def _load_json_data(file_path: str):
    try:
        if not os.path.exists(file_path):
            if file_path.endswith(".json"):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading JSON from {file_path}: {e}", exc_info=True)
        return {}

def _save_json_data(data, file_path: str):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving JSON to {file_path}: {e}", exc_info=True)

# --- إدارة بيانات العميل ---
def get_user_info(phone_number: str) -> Dict[str, Any]:
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    return all_customers.get(phone_number, {"onboarding_step": "awaiting_language"})

def store_user_info(phone_number: str, key: str, value: Any):
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    if phone_number not in all_customers:
        all_customers[phone_number] = {"onboarding_step": "awaiting_language"}
    all_customers[phone_number][key] = value
    _save_json_data(all_customers, CUSTOMER_DATA_FILE)

def add_new_customer(phone: str, name: str, lang: str):
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    if phone not in all_customers:
        all_customers[phone] = {
            "name": name,
            "language": lang,
            "onboarding_step": "done"
        }
        _save_json_data(all_customers, CUSTOMER_DATA_FILE)

def get_customer_name(phone: str) -> str:
    info = get_user_info(phone)
    return info.get("name", "")

def get_user_language(phone_number: str) -> str:
    info = get_user_info(phone_number)
    return info.get("language", "en")

# --- إدارة سجل المحادثة ---
def load_conversation_history(phone: str) -> List[Dict[str, Any]]:
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{phone}_history.json")
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error loading conversation history for {phone}: {e}", exc_info=True)
        return []

def save_conversation_history(phone: str, history: List[Dict[str, Any]]):
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{phone}_history.json")
    _save_json_data(history, file_path)

def add_to_conversation_history(phone: str, sender: str, message: str, max_history_length: int = 30):
    history = load_conversation_history(phone)
    history.append({"sender": sender, "message": message})
    history = history[-max_history_length:]
    save_conversation_history(phone, history)

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

# --- util ready for import in app.py ---
