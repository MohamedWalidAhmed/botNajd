# محتويات ملف utils/helpers.py

import os
import json
import logging

logger = logging.getLogger(__name__)

CONVERSATION_HISTORY_DIR = "conversation_history/" # تأكد إن الفولدر ده موجود أو هيتعمل

def load_conversation_history(phone_number_id: str):
    """
    Loads conversation history for a given phone number ID.
    Returns a list of messages or an empty list if no history or error.
    """
    # شيل أي "whatsapp:" ممكن تكون جاية من الـ ID
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history_file_path = os.path.join(CONVERSATION_HISTORY_DIR, f"{clean_phone_number_id}.json")

    if not os.path.exists(CONVERSATION_HISTORY_DIR):
        try:
            os.makedirs(CONVERSATION_HISTORY_DIR)
            logger.info(f"Created conversation history directory: {CONVERSATION_HISTORY_DIR}")
        except OSError as e:
            logger.error(f"Error creating conversation history directory {CONVERSATION_HISTORY_DIR}: {e}")
            return [] # رجع قايمة فاضية لو مش قادر تعمل الفولدر

    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                # تأكد إنها قايمة، لو مش قايمة رجع قايمة فاضية أو حاول تصلحها
                return history if isinstance(history, list) else []
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from history file: {history_file_path}")
            return [] # رجع قايمة فاضية لو الملف بايظ
        except Exception as e:
            logger.error(f"Error loading conversation history from {history_file_path}: {e}")
            return []
    else:
        logger.info(f"No conversation history file found for {clean_phone_number_id} at {history_file_path}. Returning empty list.")
        return [] # رجع قايمة فاضية لو مفيش ملف هيستوري

# ممكن تحتاج دوال تانية زي save_conversation_history لو بتستخدمها
def save_conversation_history(phone_number_id: str, messages: list):
    """
    Saves conversation history for a given phone number ID.
    """
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history_file_path = os.path.join(CONVERSATION_HISTORY_DIR, f"{clean_phone_number_id}.json")

    if not os.path.exists(CONVERSATION_HISTORY_DIR):
        try:
            os.makedirs(CONVERSATION_HISTORY_DIR)
            logger.info(f"Created conversation history directory: {CONVERSATION_HISTORY_DIR}")
        except OSError as e:
            logger.error(f"Error creating conversation history directory {CONVERSATION_HISTORY_DIR} for saving: {e}")
            return

    try:
        with open(history_file_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False) # ensure_ascii=False عشان العربي
        logger.info(f"Conversation history saved for {clean_phone_number_id} to {history_file_path}")
    except Exception as e:
        logger.error(f"Error saving conversation history to {history_file_path}: {e}")

# لو بتستخدم دوال تانية زي load_customer_data أو save_customer_data
# ضيفها هنا برضه بشكل مبدئي لو لسه بتظهر أخطاء بسببها
CUSTOMER_DATA_FILE = "customers/customer_data.json" # تأكد إن الفولدر ده موجود

def load_customer_data():
    if not os.path.exists(os.path.dirname(CUSTOMER_DATA_FILE)):
        try:
            os.makedirs(os.path.dirname(CUSTOMER_DATA_FILE))
        except OSError as e:
            logger.error(f"Error creating customer data directory {os.path.dirname(CUSTOMER_DATA_FILE)}: {e}")
            return {}
    
    if os.path.exists(CUSTOMER_DATA_FILE):
        try:
            with open(CUSTOMER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading customer data: {e}")
            return {}
    return {}

def save_customer_data(data):
    if not os.path.exists(os.path.dirname(CUSTOMER_DATA_FILE)):
        try:
            os.makedirs(os.path.dirname(CUSTOMER_DATA_FILE))
        except OSError as e:
            logger.error(f"Error creating customer data directory {os.path.dirname(CUSTOMER_DATA_FILE)} for saving: {e}")
            return

    try:
        with open(CUSTOMER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving customer data: {e}")

print("helpers.py has been fully loaded with placeholder functions.")
