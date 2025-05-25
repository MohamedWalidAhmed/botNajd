# استكمال محتويات ملف utils/helpers.py

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

CONVERSATION_HISTORY_DIR = "conversation_history/"
CUSTOMER_DATA_FILE = "customers/customer_data.json" # تأكد إن الفولدر ده موجود أو هيتعمل

# --- الدوال اللي ضفناها قبل كده ---
def load_conversation_history(phone_number_id: str):
    # ... (الكود بتاعها)
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history_file_path = os.path.join(CONVERSATION_HISTORY_DIR, f"{clean_phone_number_id}.json")
    if not os.path.exists(CONVERSATION_HISTORY_DIR):
        try:
            os.makedirs(CONVERSATION_HISTORY_DIR)
        except OSError as e:
            logger.error(f"Error creating conversation history directory {CONVERSATION_HISTORY_DIR}: {e}")
            return []
    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                return history if isinstance(history, list) else []
        except Exception as e:
            logger.error(f"Error loading conversation history from {history_file_path}: {e}")
            return []
    else:
        return []

def save_conversation_history(phone_number_id: str, messages: list):
    # ... (الكود بتاعها)
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history_file_path = os.path.join(CONVERSATION_HISTORY_DIR, f"{clean_phone_number_id}.json")
    if not os.path.exists(CONVERSATION_HISTORY_DIR):
        try:
            os.makedirs(CONVERSATION_HISTORY_DIR)
        except OSError as e:
            logger.error(f"Error creating conversation history directory {CONVERSATION_HISTORY_DIR} for saving: {e}")
            return
    try:
        with open(history_file_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving conversation history to {history_file_path}: {e}")

def add_to_conversation_history(phone_number_id: str, user_message: str = None, ai_message: str = None, role_user: str = "user", role_assistant: str = "assistant"):
    # ... (الكود بتاعها)
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    history = load_conversation_history(clean_phone_number_id)
    timestamp = datetime.now().isoformat()
    if user_message is not None:
        history.append({"role": role_user, "content": user_message, "timestamp": timestamp})
    if ai_message is not None:
        history.append({"role": role_assistant, "content": ai_message, "timestamp": timestamp})
    save_conversation_history(clean_phone_number_id, history)

def load_customer_data():
    # ... (الكود بتاعها)
    customer_dir = os.path.dirname(CUSTOMER_DATA_FILE)
    if not os.path.exists(customer_dir):
        try:
            os.makedirs(customer_dir)
            logger.info(f"Created customer data directory: {customer_dir}")
        except OSError as e:
            logger.error(f"Error creating customer data directory {customer_dir}: {e}")
            return {} # رجع قاموس فاضي لو مش قادر تعمل الفولدر
    if os.path.exists(CUSTOMER_DATA_FILE):
        try:
            with open(CUSTOMER_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from customer data file: {CUSTOMER_DATA_FILE}")
            return {}
        except Exception as e:
            logger.error(f"Error loading customer data from {CUSTOMER_DATA_FILE}: {e}")
            return {}
    else:
        logger.info(f"No customer data file found at {CUSTOMER_DATA_FILE}. Returning empty dict.")
        return {}

def save_customer_data(data_to_save):
    # ... (الكود بتاعها)
    customer_dir = os.path.dirname(CUSTOMER_DATA_FILE)
    if not os.path.exists(customer_dir):
        try:
            os.makedirs(customer_dir)
            logger.info(f"Created customer data directory: {customer_dir}")
        except OSError as e:
            logger.error(f"Error creating customer data directory {customer_dir} for saving: {e}")
            return
    try:
        with open(CUSTOMER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        logger.info(f"Customer data saved to {CUSTOMER_DATA_FILE}")
    except Exception as e:
        logger.error(f"Error saving customer data to {CUSTOMER_DATA_FILE}: {e}")

# --- الدالة الجديدة اللي البرنامج بيدور عليها ---
def update_customer_name(phone_number_id: str, new_name: str):
    """
    Updates the customer's name in the customer data file.
    Creates a new entry if the customer doesn't exist.
    """
    clean_phone_number_id = phone_number_id.replace("whatsapp:", "")
    all_customers = load_customer_data() # استخدم الدالة اللي عملناها عشان تجيب كل العملاء

    if clean_phone_number_id in all_customers:
        if all_customers[clean_phone_number_id].get("name") != new_name:
            all_customers[clean_phone_number_id]["name"] = new_name
            all_customers[clean_phone_number_id]["last_seen"] = datetime.now().isoformat()
            logger.info(f"Updated name for customer {clean_phone_number_id} to '{new_name}'.")
        else:
            # الاسم متغيرش، ممكن تحدث وقت آخر ظهور بس
            all_customers[clean_phone_number_id]["last_seen"] = datetime.now().isoformat()
            logger.debug(f"Customer {clean_phone_number_id} name ('{new_name}') is the same. Updated last_seen.")
    else:
        # عميل جديد، ضيفه
        all_customers[clean_phone_number_id] = {
            "name": new_name,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
            # ممكن تضيف أي بيانات تانية عايز تجمعها عن العميل الجديد
        }
        logger.info(f"New customer {clean_phone_number_id} added with name '{new_name}'.")

    save_customer_data(all_customers) # استخدم الدالة اللي عملناها عشان تحفظ بيانات العملاء المحدثة
# --- نهاية الدالة الجديدة ---

# logger.info("helpers.py should now contain update_customer_name.")
