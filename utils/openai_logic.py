# utils/openai_logic.py

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import openai
from utils.helpers import load_conversation_history, save_conversation_history, add_to_conversation_history
from utils.helpers import load_customer_data, update_customer_name

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT_FILE_PATH = "config_data/system_prompt.txt"
REFERENCE_FILE_PATH = "config_data/reference_data.txt"

SYSTEM_PROMPT = ""
REFERENCE = ""

try:
    with open(SYSTEM_PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    with open(REFERENCE_FILE_PATH, "r", encoding="utf-8") as f:
        REFERENCE = f.read().strip()
except Exception as e:
    logging.error(f"Error loading prompt or reference: {e}")

client = None
if OPENAI_API_KEY:
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        logging.error(f"Error initializing OpenAI: {e}")


def get_openai_reply_and_extract_booking_info(user_msg, sender_number_clean):
    user_msg_lower = user_msg.lower()
    if not client:
        return "عذرًا، لا يمكن الوصول إلى الذكاء الاصطناعي الآن.", None

    known_customer_name = None
    customer_profile = load_customer_data().get(sender_number_clean)
    if customer_profile:
        known_customer_name = customer_profile.get("name")

    effective_prompt = SYSTEM_PROMPT
    if known_customer_name:
        effective_prompt = f"العميل: {known_customer_name}\n{SYSTEM_PROMPT}"

    now = datetime.now()
    hour = now.hour
    shift = "الصباحي" if hour < 16 else "المسائي" if hour < 24 else "الليلي"

    messages = [
        {"role": "system", "content": f"{effective_prompt}\nالوقت الحالي: {hour}:00 - الشفت: {shift}\n\n{REFERENCE}"},
        *load_conversation_history(sender_number_clean),
        {"role": "user", "content": user_msg}
    ]

    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.5,
            max_tokens=450
        )
        reply = completion.choices[0].message.content.strip()
        add_to_conversation_history(sender_number_clean, "user", user_msg)
        add_to_conversation_history(sender_number_clean, "assistant", reply)

        if "##بيانات_الحجز##" in reply:
            extracted_info = {}
            for line in reply.split("##بيانات_الحجز##")[-1].split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    extracted_info[key.strip()] = val.strip()
            return reply, extracted_info

        return reply, None
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "عذرًا، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي.", None
