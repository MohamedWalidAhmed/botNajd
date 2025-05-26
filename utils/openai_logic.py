import openai
import os
import logging

# --- تهيئة الـ client الجديد لمكتبة OpenAI ---
# سيفترض أن متغير البيئة OPENAI_API_KEY موجود وسيتم استخدامه تلقائيًا.
# إذا لم يكن موجودًا، ستحدث مشكلة عند محاولة استدعاء الـ API.
# يمكنك إضافة check لوجود الـ key هنا أو تركه للدالة.
try:
    client = openai.OpenAI()
    # يمكنك اختبار الاتصال هنا إذا أردت، مثلاً بمحاولة list models
    # client.models.list()
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {e}. Ensure OPENAI_API_KEY is set.", exc_info=True)
    client = None # أو ارفع exception لوجود مشكلة حرجة

# --- تعريف المسارات للملفات ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # يفترض أن utils هو مجلد ابن لـ src
CONFIG_DATA_PATH = os.path.join(BASE_DIR, "config_data")

SYSTEM_PROMPT_FILE = os.path.join(CONFIG_DATA_PATH, "system_prompt.txt")
REFERENCE_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "reference_data.txt")


def get_system_prompt_content() -> str:
    try:
        with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            base_prompt = f.read().strip()
            # يمكنك تعديل البرومبت هنا مباشرة أو إبقائه كما هو
            return f"{base_prompt}" # مثال: "You are NajdAIgent, a helpful AI for Najd Company."
    except FileNotFoundError:
        logging.warning(f"System prompt file not found: {SYSTEM_PROMPT_FILE}")
        return "You are a helpful AI assistant." # برومبت افتراضي بسيط جداً

def get_reference_data_content() -> str:
    try:
        with open(REFERENCE_DATA_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.warning(f"Reference data file not found: {REFERENCE_DATA_FILE}")
        return ""

def generate_openai_response(user_id: str, user_message: str, lang: str, conversation_history: list) -> str:
    if not client:
        logging.error("OpenAI client not initialized. OPENAI_API_KEY might be missing or invalid.")
        return "I am currently unable to process this request due to a configuration issue." if lang == "en" else "أنا غير قادر حاليًا على معالجة هذا الطلب بسبب مشكلة في الإعدادات."

    # التحقق من OPENAI_API_KEY (ممكن يكون الـ client اتعمله initialize بس الـ key فاضي أو غلط)
    # المكتبة الجديدة قد لا تحتاج لـ openai.api_key = ... إذا كان OPENAI_API_KEY مضبوط في البيئة
    # لكن لو عايز تتأكد أو لو الـ client بيقبل api_key كباراميتر عند الإنشاء:
    openai_api_key_env = os.getenv("OPENAI_API_KEY")
    if not openai_api_key_env:
        logging.error("OPENAI_API_KEY environment variable not found.")
        return "I am currently unable to process this request due to a configuration issue." if lang == "en" else "أنا غير قادر حاليًا على معالجة هذا الطلب بسبب مشكلة في الإعدادات."
    # client.api_key = openai_api_key_env # ليس ضروريًا لو OPENAI_API_KEY مضبوط في البيئة عند إنشاء الـ client

    system_prompt_base = get_system_prompt_content()
    # تعديل البرومبت بناءً على اللغة هنا
    if lang == "ar":
        system_prompt = f"{system_prompt_base} Please ensure all your responses are in Arabic."
    else:
        system_prompt = f"{system_prompt_base} Please ensure all your responses are in English."

    messages = [{"role": "system", "content": system_prompt}]
    
    reference_text = get_reference_data_content()
    if reference_text:
        # إضافة البيانات المرجعية كجزء من رسالة الـ system أو رسالة system منفصلة
        messages.append({"role": "system", "content": f"Use the following reference information if relevant to the user's query:\n{reference_text}"})

    # إضافة تاريخ المحادثة
    for entry in conversation_history:
        if isinstance(entry, dict) and "role" in entry and "content" in entry:
             messages.append({"role": entry["role"], "content": entry["content"]})
        else:
            logging.warning(f"Skipping invalid history entry for user {user_id}: {entry}")
    
    # إضافة رسالة المستخدم الحالية
    messages.append({"role": "user", "content": user_message})

    try:
        logging.info(f"Sending request to OpenAI for user {user_id} with {len(messages)} messages.")
        # استدعاء الـ API بالطريقة الجديدة
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"), # تأكد أن هذا الموديل متاح لحسابك
            messages=messages,
            temperature=float(os.getenv("OPENAI_TEMPERATURE", 0.7)), # تحويل لـ float
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", 300)) # تحويل لـ int
        )
        # الوصول للرد بالطريقة الجديدة
        ai_response = response.choices[0].message.content.strip()
        logging.info(f"Received response from OpenAI for user {user_id}.")

    # التعامل مع الأخطاء بالطريقة الجديدة
    except openai.APIConnectionError as e:
        logging.error(f"OpenAI API Connection Error for user {user_id}: {e}", exc_info=True)
        ai_response = "I'm having trouble connecting to my brain right now. Please try again in a moment."
        if lang == "ar":
            ai_response = "أواجه مشكلة في الاتصال بالشبكة حاليًا. يرجى المحاولة مرة أخرى بعد لحظات."
    except openai.RateLimitError as e:
        logging.error(f"OpenAI API Rate Limit Error for user {user_id}: {e}", exc_info=True)
        ai_response = "I'm experiencing high demand right now. Please try again in a little while."
        if lang == "ar":
            ai_response = "أواجه ضغطًا كبيرًا في الطلبات حاليًا. يرجى المحاولة مرة أخرى بعد قليل."
    except openai.AuthenticationError as e:
        logging.error(f"OpenAI API Authentication Error for user {user_id}: {e}. Check your API key.", exc_info=True)
        ai_response = "There's an issue with my configuration. Please contact support if this persists."
        if lang == "ar":
            ai_response = "هناك مشكلة في إعداداتي. يرجى التواصل مع الدعم إذا استمرت المشكلة."
    except openai.APIError as e: # يمسك أي خطأ آخر من الـ API
        logging.error(f"OpenAI API Error for user {user_id}: {e}", exc_info=True)
        ai_response = "I encountered an issue while trying to generate a response. Please try again."
        if lang == "ar":
            ai_response = "واجهت مشكلة أثناء محاولة إنشاء رد. يرجى المحاولة مرة أخرى."
    except Exception as e: # يمسك أي أخطاء غير متوقعة أخرى
        logging.error(f"An unexpected error occurred in generate_openai_response for user {user_id}: {e}", exc_info=True)
        ai_response = "An unexpected error occurred. Our team has been notified."
        if lang == "ar":
            ai_response = "حدث خطأ غير متوقع. تم إخطار فريقنا."
            
    return ai_response
