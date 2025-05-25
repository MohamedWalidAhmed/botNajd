# استكمال محتويات ملف utils/helpers.py

import os
import json
import logging
from datetime import datetime # هنحتاجها عشان نسجل وقت الرسالة

logger = logging.getLogger(__name__)

CONVERSATION_HISTORY_DIR = "conversation_history/"
CUSTOMER_DATA_FILE = "customers/customer_data.json"

# ... (الدوال اللي ضفناها قبل كده زي load_conversation_history, save_conversation_history, load_customer_data, save_customer_data) ...
# خلي الدوال اللي ضفتها في المرة اللي فاتت موجودة زي ما هي فوق السطر ده

def load_conversation_history(phone_number_id: str):
    # ... (الكود بتاعها اللي ضفناه قبل كده)
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history_file_path = os.path.join(CONVERSATION_HISTORY_DIR, f"{clean_phone_number_id}.json")
    if not os.path.exists(CONVERSATION_HISTORY_DIR):
        try:
            os.makedirs(CONVERSATION_HISTORY_DIR)
            logger.info(f"Created conversation history directory: {CONVERSATION_HISTORY_DIR}")
        except OSError as e:
            logger.error(f"Error creating conversation history directory {CONVERSATION_HISTORY_DIR}: {e}")
            return []
    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                return history if isinstance(history, list) else []
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from history file: {history_file_path}")
            return []
        except Exception as e:
            logger.error(f"Error loading conversation history from {history_file_path}: {e}")
            return []
    else:
        # logger.info(f"No conversation history file found for {clean_phone_number_id}. Returning empty list.")
        return []

def save_conversation_history(phone_number_id: str, messages: list):
    # ... (الكود بتاعها اللي ضفناه قبل كده)
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
            json.dump(messages, f, indent=2, ensure_ascii=False)
        # logger.info(f"Conversation history saved for {clean_phone_number_id}")
    except Exception as e:
        logger.error(f"Error saving conversation history to {history_file_path}: {e}")


# --- الدالة الجديدة اللي البرنامج بيدور عليها ---
def add_to_conversation_history(phone_number_id: str, user_message: str = None, ai_message: str = None, role_user: str = "user", role_assistant: str = "assistant"):
    """
    Adds messages to the conversation history for a given phone number ID.
    Manages user and AI messages separately if provided.
    """
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history = load_conversation_history(clean_phone_number_id) # استخدم الدالة اللي عملناها عشان تجيب الهيستوري القديم

    timestamp = datetime.now().isoformat() # وقت الرسالة

    if user_message is not None:
        history.append({"role": role_user, "content": user_message, "timestamp": timestamp})
        logger.debug(f"Added user message to history for {clean_phone_number_id}: {user_message}")

    if ai_message is not None:
        # ممكن تضيف تأخير بسيط لو الـ AI بيرد بسرعة عشان الـ timestamp بتاع الـ AI يبقى بعد المستخدم
        # from time import sleep
        # sleep(0.01)
        # timestamp_ai = datetime.now().isoformat()
        history.append({"role": role_assistant, "content": ai_message, "timestamp": timestamp}) # أو timestamp_ai
        logger.debug(f"Added AI message to history for {clean_phone_number_id}: {ai_message}")

    # ممكن تحدد عدد أقصى للرسايل في الهيستوري عشان الملف ميكبرش أوي
    # MAX_HISTORY_LENGTH = 50 # مثلاً آخر 50 رسالة (25 سؤال وجواب)
    # if len(history) > MAX_HISTORY_LENGTH:
    #     history = history[-MAX_HISTORY_LENGTH:]

    save_conversation_history(clean_phone_number_id, history) # استخدم الدالة اللي عملناها عشان تحفظ الهيستوري الجديد
# --- نهاية الدالة الجديدة ---


def load_customer_data():
    # ... (الكود بتاعها اللي ضفناه قبل كده)
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
    # ... (الكود بتاعها اللي ضفناه قبل كده)
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

# logger.info("helpers.py has been fully loaded with all required functions.")
