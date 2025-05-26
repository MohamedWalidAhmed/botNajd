import openai
import os
import logging

# نفس تعريف BASE_DIR و CONFIG_DATA_PATH زي اللي في helpers.py
# عشان نوصل لـ system_prompt.txt و reference_data.txt
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")

SYSTEM_PROMPT_FILE = os.path.join(CONFIG_DATA_PATH, "system_prompt.txt")
REFERENCE_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "reference_data.txt")


def get_system_prompt_content() -> str:
    try:
        with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            base_prompt = f.read().strip()
            return f"{base_prompt} You are NajdAIgent..." # باقي البرومبت
    except FileNotFoundError:
        logging.warning(f"System prompt file not found: {SYSTEM_PROMPT_FILE}")
        return "You are NajdAIgent, a helpful, professional, and confident AI assistant..." # برومبت افتراضي

def get_reference_data_content() -> str:
    try:
        with open(REFERENCE_DATA_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.warning(f"Reference data file not found: {REFERENCE_DATA_FILE}")
        return ""

# ... (باقي دالة generate_openai_response زي ما هي تقريبًا) ...
def generate_openai_response(user_id: str, user_message: str, lang: str, conversation_history: list) -> str:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OPENAI_API_KEY not configured.")
        return "I am currently unable to process this request due to a configuration issue." if lang == "en" else "أنا غير قادر حاليًا على معالجة هذا الطلب بسبب مشكلة في الإعدادات."
    openai.api_key = openai_api_key

    system_prompt = get_system_prompt_content()
    if lang == "ar":
        system_prompt += " Please respond in Arabic."
    else:
        system_prompt += " Please respond in English."

    messages = [{"role": "system", "content": system_prompt}]
    
    reference_text = get_reference_data_content()
    if reference_text:
        messages.append({"role": "system", "content": f"Reference Information: {reference_text}"})

    for entry in conversation_history: # conversation_history should be a list of dicts
        if isinstance(entry, dict) and "role" in entry and "content" in entry:
             messages.append(entry)
        else:
            logging.warning(f"Skipping invalid history entry for user {user_id}: {entry}")
    
    messages.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        ai_response = response.choices[0].message.content.strip()
    except openai.error.OpenAIError as e:
        logging.error(f"OpenAI API Error for user {user_id}: {e}")
        ai_response = "I encountered an issue while trying to generate a response. Please try again."
        if lang == "ar":
            ai_response = "واجهت مشكلة أثناء محاولة إنشاء رد. يرجى المحاولة مرة أخرى."
    except Exception as e:
        logging.error(f"An unexpected error occurred in generate_openai_response for user {user_id}: {e}", exc_info=True)
        ai_response = "An unexpected error occurred. Our team has been notified."
        if lang == "ar":
            ai_response = "حدث خطأ غير متوقع. تم إخطار فريقنا."
            
    return ai_response
