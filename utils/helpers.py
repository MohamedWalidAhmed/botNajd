# utils/helpers.py
import json
import os
from typing import Dict, Any, Optional, List
from thefuzz import fuzz
import logging # <--- ضيف دي لو مش موجودة

# --- إعداد الـ Logger (مهم!) ---
# لو انت عامل إعدادات logging في app.py والـ logger بتاع الـ app متاح هنا، استخدمه
# لو لأ، ممكن نعمل لوجر بسيط هنا
logger = logging.getLogger(__name__) # اسم الموديول كاسم للوجر
if not logger.handlers: # عشان نتجنب إضافة handlers كذا مرة
    # هنا ممكن تضيف handler بسيط لو مفيش إعدادات لوجينج عامة، بس الأفضل تكون في app.py
    # للتسهيل دلوقتي، هنفترض إن فيه إعدادات لوجينج عامة في app.py واللوجر هيشتغل
    # لو لقيت اللوجات دي مش بتظهر، يبقى لازم تظبط إعدادات اللوجينج في app.py
    # أو تضيف handler هنا زي ما عملنا في send_meta.py
    logger.setLevel(logging.INFO) # أو DEBUG لو عايز تفاصيل أكتر

# --- تحديد مسارات الملفات (زي ما هي بس هنطبعها) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")
CUSTOMERS_PATH = os.path.join(BASE_DIR, "customers")
CONVERSATION_HISTORY_PATH = os.path.join(BASE_DIR, "conversation_hist")

os.makedirs(CONFIG_DATA_PATH, exist_ok=True)
os.makedirs(CUSTOMERS_PATH, exist_ok=True)
os.makedirs(CONVERSATION_HISTORY_PATH, exist_ok=True)

REPLIES_FILE = os.path.join(CONFIG_DATA_PATH, "replies.json")
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_PATH, "customer_data.json")
FAQ_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "faq_data.json")

# --- نطبع المسارات دي عشان نتأكد منها على Render ---
logger.info(f"HELPERS.PY: BASE_DIR determined as: {BASE_DIR}")
logger.info(f"HELPERS.PY: CUSTOMER_DATA_FILE path: {CUSTOMER_DATA_FILE}")
logger.info(f"HELPERS.PY: CONVERSATION_HISTORY_PATH path: {CONVERSATION_HISTORY_PATH}")
# --- نهاية طباعة المسارات ---


def _load_json_data(file_path: str) -> Dict:
    logger.info(f"HELPERS.PY: Attempting to LOAD JSON from: {file_path}")
    try:
        if not os.path.exists(file_path):
            logger.warning(f"HELPERS.PY: File NOT FOUND for loading: {file_path}. Returning empty dict.")
            # لو الملف مش موجود، ممكن ننشئه فاضي هنا عشان نتجنب مشاكل بعدين
            if file_path.endswith(".json"): # تأكد إنه ملف جيسون
                 with open(file_path, 'w', encoding='utf-8') as f_create:
                    json.dump({}, f_create)
                 logger.info(f"HELPERS.PY: Created empty JSON file at: {file_path}")
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"HELPERS.PY: File is EMPTY: {file_path}. Returning empty dict.")
                return {}
            data = json.loads(content)
            logger.info(f"HELPERS.PY: Successfully LOADED JSON from: {file_path}. Data keys (sample): {list(data.keys())[:5]}") # نطبع أول 5 مفاتيح كعينة
            return data
    except json.JSONDecodeError as e:
        logger.error(f"HELPERS.PY: JSONDecodeError while loading {file_path}: {e}. File content might be corrupted.", exc_info=True)
        return {} # مهم نرجع حاجة عشان الكود ميكسرش
    except Exception as e:
        logger.error(f"HELPERS.PY: UNEXPECTED ERROR loading JSON from {file_path}: {e}", exc_info=True)
        return {}

def _save_json_data(data: Dict, file_path: str):
    logger.info(f"HELPERS.PY: Attempting to SAVE JSON data to: {file_path}")
    logger.debug(f"HELPERS.PY: Data to save in {file_path} (first 2 items if dict, or first 5 if list): "
                 f"{dict(list(data.items())[:2]) if isinstance(data, dict) else data[:5]}") # نطبع عينة من الداتا
    try:
        # os.makedirs(os.path.dirname(file_path), exist_ok=True) # عملناها فوق عند تعريف المسارات
        with open(file_path, 'w', encoding='utf-8') as f: # تصحيح: utf-8 مش utf-utf-8
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"HELPERS.PY: Successfully SAVED JSON data to: {file_path}")
    except PermissionError as e:
        logger.error(f"HELPERS.PY: PERMISSION ERROR saving JSON to {file_path}: {e}. Check filesystem permissions on Render!", exc_info=True)
    except IOError as e:
        logger.error(f"HELPERS.PY: IO ERROR saving JSON to {file_path}: {e}. Disk full or other issue?", exc_info=True)
    except Exception as e:
        logger.error(f"HELPERS.PY: UNEXPECTED ERROR saving JSON to {file_path}: {e}", exc_info=True)

# --- Customer Information (دوال العملاء زي ما هي بس هتستخدم الدوال اللي فوق باللوجات) ---
def store_user_info(phone_number: str, key: str, value: Any):
    logger.info(f"HELPERS.PY: Storing user info for {phone_number}. Key: {key}, Value: {value}")
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    if phone_number not in all_customers:
        all_customers[phone_number] = {"onboarding_step": "awaiting_language"} # القيمة الافتراضية
        logger.info(f"HELPERS.PY: New customer {phone_number}, initialized with onboarding_step.")
    all_customers[phone_number][key] = value
    _save_json_data(all_customers, CUSTOMER_DATA_FILE)
    logger.info(f"HELPERS.PY: User info for {phone_number} after update (Key: {key}): {all_customers.get(phone_number)}")


def get_user_info(phone_number: str) -> Dict[str, Any]:
    logger.info(f"HELPERS.PY: Getting user info for {phone_number}")
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    user_data = all_customers.get(phone_number, {"onboarding_step": "awaiting_language"})
    logger.info(f"HELPERS.PY: Retrieved user info for {phone_number}: {user_data}")
    return user_data

# ... باقي دوال الـ helpers زي get_user_language, get_reply_from_json, get_static_reply ...

# --- Conversation History (هنضيف لوجات مشابهة) ---
def load_conversation_history(user_id: str) -> List[Dict[str, str]]:
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{user_id}.json")
    logger.info(f"HELPERS.PY: Loading conversation history for user {user_id} from {file_path}")
    # _load_json_data هترجع dict, لازم نتأكد إنها list
    data = _load_json_data(file_path)
    if isinstance(data, list):
        logger.info(f"HELPERS.PY: Loaded {len(data)} messages for user {user_id}.")
        return data
    elif isinstance(data, dict) and not data: # لو رجعت dict فاضي
        logger.info(f"HELPERS.PY: No history found or file was empty for user {user_id}, returning empty list.")
        return []
    else:
        logger.warning(f"HELPERS.PY: Conversation history for user {user_id} is not a list or empty dict. Data: {data}. Returning empty list.")
        return []


def save_conversation_history(user_id: str, history: List[Dict[str, str]]):
    # هنا كان فيه خطأ في استدعاء _save_json_data في رد سابق، الداتا أولاً ثم المسار
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{user_id}.json")
    logger.info(f"HELPERS.PY: Saving conversation history for user {user_id} to {file_path}. History length: {len(history)}")
    _save_json_data(history, file_path) # <--- الداتا (history) الأول، بعدين المسار


def add_to_conversation_history(user_id: str, role: str, content: str, max_history_length: int = 20):
    logger.info(f"HELPERS.PY: Adding to conversation history for user {user_id}. Role: {role}")
    history_data = load_conversation_history(user_id) # دي المفروض ترجع list

    # تأكيد إنها قائمة
    if not isinstance(history_data, list):
        logger.warning(f"HELPERS.PY: History data for {user_id} was not a list, re-initializing. Was: {type(history_data)}")
        history_data = []

    history_data.append({"role": role, "content": content})
    history_data = history_data[-max_history_length:]
    save_conversation_history(user_id, history_data)
    logger.info(f"HELPERS.PY: Conversation history for {user_id} updated. New length: {len(history_data)}")



def get_reply_from_json(reply_key: str, lang: str, **kwargs) -> str:
    """
    Fetches a reply from replies.json based on key and language.
    kwargs are used for formatting placeholders in the reply string.
    """
    replies_content = _load_json_data(REPLIES_FILE)
    message_template = replies_content.get(reply_key, {}).get(lang)
    if not message_template:
        # Fallback to English if specific language or key is missing
        message_template = replies_content.get(reply_key, {}).get("en", f"Error: Reply key '{reply_key}' not found for lang '{lang}'.")
        logger.warning(f"HELPERS.PY: Reply key '{reply_key}' not found for lang '{lang}'. Fallback to EN or error msg.")
    try:
        return message_template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"HELPERS.PY: Missing placeholder {e} for reply key '{reply_key}' (lang: {lang}).")
        return message_template  # Return unformatted if placeholder is missing


def get_user_language(phone_number: str) -> str:
    """
    Retrieves the user's preferred language. Defaults to 'en' if not set.
    """
    user_data = get_user_info(phone_number)
    return user_data.get("language", "en")




# باقي الدوال في helpers.py (get_reply_from_json, get_static_reply, get_user_language) مش محتاجة تعديل كبير في اللوجات للتشخيص ده
# بس اتأكد إن get_user_language بتستخدم get_user_info اللي باللوجات الجديدة.
