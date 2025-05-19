import os
import json
import openai
from flask import Flask, request, Response, jsonify, render_template
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from datetime import datetime # <-- تم استيراد datetime

# --- 1. Load Environment Variables ---
# ... (كما هو) ...
try:
    load_dotenv()
    print("Environment variables loaded from .env file.")
except ImportError:
    print("Warning: python-dotenv library is not installed. .env file will not be loaded.")
except FileNotFoundError:
    print("Warning: .env file not found.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("!!! CRITICAL WARNING: OPENAI_API_KEY not found in environment variables. !!!")
    OPENAI_API_KEY = "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV" 

client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized successfully.")
    except Exception as e:
        print(f"!!! CRITICAL ERROR initializing OpenAI client: {e} !!!")
else:
    print("!!! OpenAI client NOT initialized due to missing or placeholder API key. !!!")

# --- 2. Define Paths for External Config Files ---
# ... (كما هو) ...
CONFIG_DATA_FOLDER = "config_data"
SYSTEM_PROMPT_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "system_prompt.txt")
REFERENCE_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "reference_data.txt")
REPLIES_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "replies.json")

# --- 3. Load SYSTEM_PROMPT, REFERENCE, and REPLIES ---
# ... (كما هو، مع التأكد من تحميل الملفات بشكل صحيح) ...
SYSTEM_PROMPT = ""
try:
    if not os.path.exists(SYSTEM_PROMPT_FILE_PATH): print(f"!!! ERROR: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' not found. Using empty prompt. !!!")
    else:
        with open(SYSTEM_PROMPT_FILE_PATH, "r", encoding="utf-8") as f: SYSTEM_PROMPT = f.read().strip()
        if SYSTEM_PROMPT: print(f"System prompt loaded from: '{SYSTEM_PROMPT_FILE_PATH}'")
        else: print(f"!!! WARNING: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' is empty. !!!")
except Exception as e: print(f"!!! ERROR reading system prompt: {e} !!!")

REFERENCE = ""
try:
    if not os.path.exists(REFERENCE_FILE_PATH): print(f"!!! WARNING: Reference file '{REFERENCE_FILE_PATH}' not found. No reference data will be used. !!!")
    else:
        with open(REFERENCE_FILE_PATH, "r", encoding="utf-8") as f: REFERENCE = f.read().strip()
        if REFERENCE: print(f"Reference data loaded from: '{REFERENCE_FILE_PATH}'")
        else: print(f"Warning: Reference file '{REFERENCE_FILE_PATH}' is empty.")
except Exception as e: print(f"!!! ERROR reading reference data: {e} !!!")

REPLIES = {}
try:
    if not os.path.exists(REPLIES_FILE_PATH): print(f"!!! WARNING: Replies file '{REPLIES_FILE_PATH}' not found. Using default/inline error replies. !!!")
    else:
        with open(REPLIES_FILE_PATH, "r", encoding="utf-8") as f: REPLIES = json.load(f)
        print(f"Replies loaded successfully from '{REPLIES_FILE_PATH}'.")
except Exception as e: print(f"Error loading replies from '{REPLIES_FILE_PATH}': {e}")

def get_reply_from_file(key, default_reply="عذرًا، حدث خطأ ما.", **kwargs):
    # ... (كما هي) ...
    message_template = REPLIES.get(key, default_reply)
    try:
        return message_template.format(**kwargs) if kwargs else message_template
    except KeyError as e:
        print(f"Warning: Missing key '{e}' for reply template '{key}'.")
        return message_template 
    except Exception as e:
        print(f"Error formatting reply for key '{key}': {e}")
        return default_reply
        
# --- 4. Flask App Setup & Data Folders ---
# ... (كما هو) ...
app = Flask(__name__)
CUSTOMERS_FOLDER = "customers"
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_FOLDER, "customer_data.json")
CONVERSATION_HISTORY_FOLDER = "conversation_history"
if not os.path.exists(CUSTOMERS_FOLDER): os.makedirs(CUSTOMERS_FOLDER)
if not os.path.exists(CONVERSATION_HISTORY_FOLDER): os.makedirs(CONVERSATION_HISTORY_FOLDER)

# --- 5. Helper Functions for Customer Data & Conversation History ---
# ... (دوال load_customer_data, save_customer_data, update_customer_name, 
#      add_or_update_customer_booking, get_conversation_history_path, 
#      load_conversation_history, save_conversation_history, add_to_conversation_history
#      تبقى كما هي تمامًا من الكود السابق) ...
def load_customer_data():
    if not os.path.exists(CUSTOMER_DATA_FILE): return {}
    try:
        with open(CUSTOMER_DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read(); return json.loads(content) if content.strip() else {}
    except (json.JSONDecodeError, FileNotFoundError): return {}
    except Exception as e: print(f"Error loading customer data: {e}"); return {}

def save_customer_data(data):
    try:
        with open(CUSTOMER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Error saving customer data: {e}")

def update_customer_name(phone_number, name):
    all_customers = load_customer_data(); clean_phone = phone_number.replace("whatsapp:", "")
    if not name or name == "غير محدد": return
    if clean_phone not in all_customers: all_customers[clean_phone] = {"name": name, "bookings": []}; print(f"New customer profile for {clean_phone} with name: {name}")
    elif all_customers[clean_phone].get("name") != name : all_customers[clean_phone]["name"] = name; print(f"Customer name updated for {clean_phone} to: {name}")
    save_customer_data(all_customers)

def add_or_update_customer_booking(phone_number, booking_info):
    all_customers = load_customer_data(); clean_phone = phone_number.replace("whatsapp:", "")
    customer_name_in_booking = booking_info.get("name")
    if clean_phone not in all_customers:
        default_name = f"عميل {clean_phone[-4:]}"
        all_customers[clean_phone] = {"name": customer_name_in_booking if customer_name_in_booking and customer_name_in_booking != "غير محدد" else default_name, "bookings": []}
    cust = all_customers[clean_phone]
    if customer_name_in_booking and customer_name_in_booking != "غير محدد" and cust.get("name", "") != customer_name_in_booking: cust["name"] = customer_name_in_booking
    new_booking = {k: booking_info.get(k, "غير محدد") for k in ["specialty", "service_type", "doctor_name", "datetime", "notes"]}
    cust["bookings"].append(new_booking); save_customer_data(all_customers)
    print(f"New booking added for {clean_phone} (Name: {cust['name']})")

def get_conversation_history_path(sender_id): return os.path.join(CONVERSATION_HISTORY_FOLDER, f"{sender_id}_history.json")
def load_conversation_history(sender_id):
    history_path = get_conversation_history_path(sender_id)
    if not os.path.exists(history_path): return []
    try:
        with open(history_path, "r", encoding="utf-8") as f: content = f.read(); return json.loads(content) if content.strip() else []
    except (json.JSONDecodeError, FileNotFoundError): return []
    except Exception as e: print(f"Error loading conv history for {sender_id}: {e}"); return []

def save_conversation_history(sender_id, history):
    history_path = get_conversation_history_path(sender_id); max_history_turns = 5; max_history_items = max_history_turns * 2
    if len(history) > max_history_items: history = history[-max_history_items:]
    try:
        with open(history_path, "w", encoding="utf-8") as f: json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving conversation history for {sender_id}: {e}")

def add_to_conversation_history(sender_id, role, text):
    history = load_conversation_history(sender_id); history.append({"role": role, "content": text}); save_conversation_history(sender_id, history)


# --- 6. Function to Interact with OpenAI & Extract Booking Info (MODIFIED with Time Hint) ---
def get_openai_reply_and_extract_booking_info(user_msg, sender_number_clean):
    print(f"Processing message for OpenAI from {sender_number_clean}: '{user_msg}'")
    user_msg_lower = user_msg.lower()

    # --- Simple keyword-based pre-defined replies (can be kept or removed based on preference) ---
    if any(keyword in user_msg_lower for keyword in ["العيون", "عين", "رمد"]):
        print("Keyword for 'eye_department_info' detected."); add_to_conversation_history(sender_number_clean, "user", user_msg)
        return get_reply_from_file("eye_department_info"), None
    if any(keyword in user_msg_lower for keyword in ["الأسنان", "اسنان", "سني", "سنان"]):
        print("Keyword for 'dental_department_info' detected."); add_to_conversation_history(sender_number_clean, "user", user_msg)
        return get_reply_from_file("dental_department_info"), None
    # --- (Keep other keyword checks if desired) ---
    print("No simple keywords matched or proceeding to OpenAI.")
    
    if not client: return get_reply_from_file("error_openai_client_not_init"), None
    if not SYSTEM_PROMPT: return get_reply_from_file("error_system_prompt_empty"), None

    customer_profile = load_customer_data().get(sender_number_clean)
    known_customer_name = customer_profile.get("name") if customer_profile and customer_profile.get("name") != "غير محدد" else None
    
    effective_system_prompt = SYSTEM_PROMPT
    if known_customer_name:
        effective_system_prompt = (
            f"أنت تتحدث الآن مع العميل: الأستاذ/الأستاذة {known_customer_name} (معرفه: {sender_number_clean}). خاطبه بهذا الاسم ولا تطلب اسمه مرة أخرى إلا إذا طلب هو تغييره.\n\n"
            f"{SYSTEM_PROMPT}"
        )
    
    # --- بداية إضافة منطق الوقت والشفت الحالي ---
    now = datetime.now()
    hour = now.hour
    current_shift = ""
    if 8 <= hour < 16:
        current_shift = "الصباحي"
    elif 16 <= hour < 24: # أو hour == 0 لأن 24 هو 00 في اليوم التالي
        current_shift = "المسائي"
    else: #  0 <= hour < 8
        current_shift = "الليلي"

    # ملاحظة: توقيت السعودية هو UTC+3. إذا كان الخادم الذي يشغل البوت مضبوطًا على UTC،
    # قد تحتاج لتعديل `now` ليعكس توقيت السعودية. مثال:
    # from datetime import timezone, timedelta
    # saudi_time = now.astimezone(timezone(timedelta(hours=3)))
    # hour = saudi_time.hour
    # ولكن إذا كان الخادم مضبوطًا على توقيت محلي صحيح، `now.hour` سيكون كافيًا.

    time_hint = f"توجيه إضافي لك: الوقت الحالي الآن هو حوالي الساعة {hour}:00 بتوقيت العميل (السعودية)، مما يعني أن الشفت الحالي هو '{current_shift}'. عند اقتراح أقرب موعد لدكتور في أي تخصص بناءً على طلب العميل، يرجى الرجوع للمعلومات المرجعية ومحاولة اختيار طبيب يعمل في هذا الشفت الحالي أو الشفت التالي مباشرة إذا لم يتوفر في الحالي، مع ذكر اسم الطبيب المقترح."
    # --- نهاية إضافة منطق الوقت والشفت الحالي ---

    conversation_history = load_conversation_history(sender_number_clean)
    messages_for_openai = []
    
    # --- تعديل: دمج time_hint مع الـ system_message_content ---
    system_message_content = f"{effective_system_prompt}\n\n{time_hint}\n\nالمعلومات المرجعية (استخدم هذه للإجابة إذا كانت ذات صلة):\n{REFERENCE}"
    # --- نهاية التعديل ---

    messages_for_openai.append({"role": "system", "content": system_message_content})
    messages_for_openai.extend(conversation_history)
    messages_for_openai.append({"role": "user", "content": user_msg})

    ai_model_reply_text = get_reply_from_file("error_generic_ai")
    extracted_info = None
    name_extracted_this_turn = None # To capture name if AI extracts it

    try:
        print(f"Sending to OpenAI for {sender_number_clean}: ... Total messages: {len(messages_for_openai)}")
        # يمكنك طباعة system_message_content هنا للتحقق من دمج time_hint
        # print(f"System Message sent to OpenAI:\n{system_message_content}\n--------------------")

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages_for_openai,
            temperature=0.5, # تقليل الحرارة قليلاً لجعله أكثر اتباعًا للمرجعية والوقت
            max_tokens=450  # زيادة قليلاً لإتاحة ردود أكثر تفصيلاً إذا لزم الأمر
        )
        
        if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
            ai_model_reply_text = completion.choices[0].message.content.strip()
            print(f"OpenAI Generated Reply for {sender_number_clean}: {ai_model_reply_text[:150]}...") # طباعة جزء أطول قليلاً
            
            add_to_conversation_history(sender_number_clean, "user", user_msg)
            add_to_conversation_history(sender_number_clean, "assistant", ai_model_reply_text)
        else:
            print("OpenAI response was empty or malformed.")
            return get_reply_from_file("error_openai_empty_response"), None

        # ... (منطق استخلاص ##بيانات_الحجز## وتحديث الاسم كما هو) ...
        if "##بيانات_الحجز##" in ai_model_reply_text:
            try:
                _, details_part_with_tag = ai_model_reply_text.split("##بيانات_الحجز##", 1)
                details_part = details_part_with_tag.strip()
                extracted_info = {}
                for line in details_part.split('\n'):
                    if ':' in line:
                        key_val = line.split(':', 1); key = key_val[0].strip(); value = key_val[1].strip() if len(key_val) > 1 else ""
                        key_map = {
                            "الاسم": "name", "اسم المريض": "name", "الاسم الكريم": "name",
                            "التخصص": "specialty", "نوع الخدمة": "service_type", "الخدمة": "service_type",
                            "الدكتور": "doctor_name", "الوقت والتاريخ": "datetime", "الموعد": "datetime",
                            "ملاحظات": "notes"
                        }
                        english_key = key_map.get(key)
                        if english_key:
                            extracted_info[english_key] = value
                            if english_key == "name" and value and value != "غير محدد": name_extracted_this_turn = value
                if not extracted_info: print("Warning: ##بيانات_الحجز## tag found but no data extracted.")
                else:
                    print(f"Extracted booking data: {extracted_info}")
                    if name_extracted_this_turn: update_customer_name(sender_number_clean, name_extracted_this_turn)
            except Exception as e: print(f"Error parsing ##بيانات_الحجز##: {e}")
        
        if not name_extracted_this_turn and not known_customer_name: # Heuristic name capture
            if "أستاذ " in ai_model_reply_text: # ... (نفس منطق التقاط الاسم) ...
                try:
                    potential_name = ai_model_reply_text.split("أستاذ ", 1)[1].split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(c.isdigit() for c in potential_name):
                        update_customer_name(sender_number_clean, potential_name)
                except IndexError: pass
            elif "أستاذة " in ai_model_reply_text: # ...
                 try:
                    potential_name = ai_model_reply_text.split("أستاذة ", 1)[1].split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(c.isdigit() for c in potential_name):
                        update_customer_name(sender_number_clean, potential_name)
                 except IndexError: pass

    # ... (باقي معالجة أخطاء OpenAI كما هي) ...
    except openai.APIConnectionError as e: print(f"OpenAI Connection Error: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_connection")
    except openai.RateLimitError as e: print(f"OpenAI Rate Limit: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_ratelimit")
    except openai.AuthenticationError as e: print(f"OpenAI Auth Error: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_auth")
    except openai.APIStatusError as e: print(f"OpenAI API Error {e.status_code}: {e.message if hasattr(e, 'message') else e.response.text if hasattr(e, 'response') else str(e)}"); ai_model_reply_text = get_reply_from_file("error_openai_status", status_code=e.status_code if hasattr(e, 'status_code') else 'Unknown')
    except Exception as e: print(f"General OpenAI Error: {e}, Type: {type(e)}")
        
    return ai_model_reply_text, extracted_info

# --- 7. Twilio Webhook & Web Chat Endpoint ---
# ... (تبقى كما هي) ...
@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get("Body", "").strip()
    sender_full = request.values.get("From", "") 
    sender_clean = sender_full.replace("whatsapp:", "")
    if not incoming_msg: return Response(status=204)

    print(f"--- WhatsApp Request from {sender_full} ---")
    ai_reply_text, booking_data_extracted = get_openai_reply_and_extract_booking_info(incoming_msg, sender_clean)
    final_reply_to_user = ai_reply_text

    if booking_data_extracted:
        name_for_booking = booking_data_extracted.get("name")
        if not name_for_booking or name_for_booking == "غير محدد":
            customer_profile = load_customer_data().get(sender_clean, {})
            name_for_booking = customer_profile.get("name", f"عميل {sender_clean[-4:]}")
        booking_data_extracted["name"] = name_for_booking
        try:
            add_or_update_customer_booking(sender_clean, booking_data_extracted)
        except Exception as e: print(f"Error saving booking for {sender_clean}: {e}")
    
    twiml_response = MessagingResponse()
    twiml_response.message(final_reply_to_user)
    print(f"Sending Twilio reply to {sender_full}: {final_reply_to_user[:100]}...")
    return Response(str(twiml_response), mimetype='application/xml')

@app.route("/chat", methods=["POST"]) # For the web interface
def handle_web_chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        if not user_message:
            return jsonify({"reply": get_reply_from_file("error_web_no_message", default_reply="No message received.")}), 400
        
        web_user_id = "web_chat_user_01" 
        print(f"--- Web Chat Request from {web_user_id} ---")
        ai_reply_text, booking_data_web = get_openai_reply_and_extract_booking_info(user_message, web_user_id)
        
        if booking_data_web: print(f"Booking data extracted from web chat: {booking_data_web}")
        return jsonify({"reply": ai_reply_text})
    except Exception as e:
        print(f"Error in /chat endpoint: {e}")
        return jsonify({"reply": get_reply_from_file("error_generic_web", default_reply="Server error processing web chat.")}), 500

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# --- Test Routes & App Run ---
# ... (تبقى كما هي) ...
@app.route("/customer/<phone_number>")
def get_customer_info_route(phone_number):
    customer_data = load_customer_data().get(phone_number.replace("whatsapp:", ""))
    if customer_data: return jsonify(customer_data)
    return jsonify({"error": "Customer not found"}), 404

@app.route("/history/<phone_number>")
def get_history_route(phone_number):
    history = load_conversation_history(phone_number.replace("whatsapp:", ""))
    if history: return jsonify(history)
    return jsonify({"message": "No conversation history for this number."}), 404

if __name__ == "__main__":
    # ... (نفس كود التشغيل مع التحقق من الملفات والمفاتيح) ...
    if not os.path.exists(CUSTOMER_DATA_FILE): save_customer_data({})
    critical_errors = False
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV": print("!"*40 + "\n!!! CRITICAL: OPENAI_API_KEY is not set. Bot WILL NOT WORK. !!!\n" + "!"*40); critical_errors = True
    if not SYSTEM_PROMPT: print("!"*40 + "\n!!! WARNING: SYSTEM_PROMPT is empty. Bot responses will be poor. !!!\n" + "!"*40)
    if not REPLIES: print("!"*40 + "\n!!! WARNING: REPLIES file not loaded or empty. !!!\n" + "!"*40)
    if critical_errors: print("!!! Exiting due to critical configuration errors. !!!") # exit(1) can be added
    print("Bot (Web & WhatsApp) is ready with OpenAI (Time Hint, Keywords, History, Persistent Name, External Replies)...")
    app.run(debug=True, host='0.0.0.0', port=5000)