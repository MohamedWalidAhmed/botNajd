import os
import json
import openai
from flask import Flask, request, Response, jsonify, render_template
from twilio.twiml.messaging_response import MessagingResponse # Note: This is for Twilio, will be unused by Meta webhook directly
from dotenv import load_dotenv
from datetime import datetime
import logging # Added for better logging, especially for webhook

# --- Start of WhatsApp Cloud API Webhook Integration (Meta) ---
# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

VERIFY_TOKEN = "N@jj@9ent2030" # Your Meta App Verify Token

app = Flask(__name__) # Initialize Flask App (moved here as it's needed before routes)

@app.route("/webhook", methods=['GET', 'POST'])
def webhook_whatsapp_meta():
    if request.method == 'GET':
        # Webhook verification logic for WhatsApp Cloud API (Meta)
        if request.args.get("hub.mode") == "subscribe" and \
           request.args.get("hub.verify_token") == VERIFY_TOKEN:
            logging.info("WhatsApp Cloud API Webhook verification successful.")
            return request.args.get("hub.challenge"), 200
        else:
            logging.error(f"WhatsApp Cloud API Webhook verification failed. Token received: {request.args.get('hub.verify_token')}")
            return "Verification token mismatch or mode is not 'subscribe'", 403
    elif request.method == 'POST':
        # This is where you will process incoming messages from Meta
        data = request.get_json()
        logging.info(f"Received WhatsApp event from Meta: {json.dumps(data, indent=2)}")

        # TODO: Extract message text and sender ID from 'data'
        # Example (structure might vary based on actual payload):
        # if data.get("object") == "whatsapp_business_account":
        #     if data.get("entry") and data["entry"][0].get("changes") and \
        #        data["entry"][0]["changes"][0].get("value") and \
        #        data["entry"][0]["changes"][0]["value"].get("messages"):
        #
        #         message_object = data["entry"][0]["changes"][0]["value"]["messages"][0]
        #         if message_object.get("type") == "text":
        #             incoming_msg = message_object["text"]["body"]
        #             sender_wa_id = message_object["from"] # WhatsApp ID (phone number)
        #
        #             # Clean sender ID if needed (e.g. for conversation history key)
        #             sender_clean = sender_wa_id
        #
        #             print(f"--- Meta WhatsApp Request from {sender_wa_id} ---")
        #             # Process with your existing OpenAI logic
        #             # ai_reply_text, booking_data_extracted = get_openai_reply_and_extract_booking_info(incoming_msg, sender_clean)
        #             # final_reply_to_user = ai_reply_text
        #
        #             # if booking_data_extracted:
        #             #     # ... (your booking logic) ...
        #
        #             # TODO: Send reply back using Meta Graph API (not Twilio TwiML)
        #             # For example:
        #             # send_meta_whatsapp_message(sender_wa_id, final_reply_to_user)
        #             # print(f"Preparing to send Meta reply to {sender_wa_id}: {final_reply_to_user[:100]}...")
        #
        #             pass # Placeholder for actual processing and reply

        return jsonify({"status": "success"}), 200 # Acknowledge receipt to Meta
# --- End of WhatsApp Cloud API Webhook Integration (Meta) ---

# --- 1. Load Environment Variables ---
try:
    load_dotenv()
    logging.info("Environment variables loaded from .env file.") # Changed print to logging
except ImportError:
    logging.warning("Warning: python-dotenv library is not installed. .env file will not be loaded.") # Changed print to logging
except FileNotFoundError:
    logging.info("Warning: .env file not found.") # Changed print to logging

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.critical("!!! CRITICAL WARNING: OPENAI_API_KEY not found in environment variables. !!!") # Changed print to logging
    OPENAI_API_KEY = "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV"

client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized successfully.") # Changed print to logging
    except Exception as e:
        logging.critical(f"!!! CRITICAL ERROR initializing OpenAI client: {e} !!!") # Changed print to logging
else:
    logging.warning("!!! OpenAI client NOT initialized due to missing or placeholder API key. !!!") # Changed print to logging

# --- 2. Define Paths for External Config Files ---
CONFIG_DATA_FOLDER = "config_data"
SYSTEM_PROMPT_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "system_prompt.txt")
REFERENCE_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "reference_data.txt")
REPLIES_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "replies.json")

# --- 3. Load SYSTEM_PROMPT, REFERENCE, and REPLIES ---
SYSTEM_PROMPT = ""
try:
    if not os.path.exists(SYSTEM_PROMPT_FILE_PATH): logging.error(f"!!! ERROR: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' not found. Using empty prompt. !!!") # Changed print to logging
    else:
        with open(SYSTEM_PROMPT_FILE_PATH, "r", encoding="utf-8") as f: SYSTEM_PROMPT = f.read().strip()
        if SYSTEM_PROMPT: logging.info(f"System prompt loaded from: '{SYSTEM_PROMPT_FILE_PATH}'") # Changed print to logging
        else: logging.warning(f"!!! WARNING: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' is empty. !!!") # Changed print to logging
except Exception as e: logging.error(f"!!! ERROR reading system prompt: {e} !!!") # Changed print to logging

REFERENCE = ""
try:
    if not os.path.exists(REFERENCE_FILE_PATH): logging.warning(f"!!! WARNING: Reference file '{REFERENCE_FILE_PATH}' not found. No reference data will be used. !!!") # Changed print to logging
    else:
        with open(REFERENCE_FILE_PATH, "r", encoding="utf-8") as f: REFERENCE = f.read().strip()
        if REFERENCE: logging.info(f"Reference data loaded from: '{REFERENCE_FILE_PATH}'") # Changed print to logging
        else: logging.warning(f"Warning: Reference file '{REFERENCE_FILE_PATH}' is empty.") # Changed print to logging
except Exception as e: logging.error(f"!!! ERROR reading reference data: {e} !!!") # Changed print to logging

REPLIES = {}
try:
    if not os.path.exists(REPLIES_FILE_PATH): logging.warning(f"!!! WARNING: Replies file '{REPLIES_FILE_PATH}' not found. Using default/inline error replies. !!!") # Changed print to logging
    else:
        with open(REPLIES_FILE_PATH, "r", encoding="utf-8") as f: REPLIES = json.load(f)
        logging.info(f"Replies loaded successfully from '{REPLIES_FILE_PATH}'.") # Changed print to logging
except Exception as e: logging.error(f"Error loading replies from '{REPLIES_FILE_PATH}': {e}") # Changed print to logging

def get_reply_from_file(key, default_reply="عذرًا، حدث خطأ ما.", **kwargs):
    message_template = REPLIES.get(key, default_reply)
    try:
        return message_template.format(**kwargs) if kwargs else message_template
    except KeyError as e:
        logging.warning(f"Warning: Missing key '{e}' for reply template '{key}'.") # Changed print to logging
        return message_template
    except Exception as e:
        logging.error(f"Error formatting reply for key '{key}': {e}") # Changed print to logging
        return default_reply

# --- 4. Flask App Setup & Data Folders --- (app already initialized above)
CUSTOMERS_FOLDER = "customers"
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_FOLDER, "customer_data.json")
CONVERSATION_HISTORY_FOLDER = "conversation_history"
if not os.path.exists(CUSTOMERS_FOLDER): os.makedirs(CUSTOMERS_FOLDER)
if not os.path.exists(CONVERSATION_HISTORY_FOLDER): os.makedirs(CONVERSATION_HISTORY_FOLDER)

# --- 5. Helper Functions for Customer Data & Conversation History ---
def load_customer_data():
    if not os.path.exists(CUSTOMER_DATA_FILE): return {}
    try:
        with open(CUSTOMER_DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read(); return json.loads(content) if content.strip() else {}
    except (json.JSONDecodeError, FileNotFoundError): return {}
    except Exception as e: logging.error(f"Error loading customer data: {e}"); return {} # Changed print to logging

def save_customer_data(data):
    try:
        with open(CUSTOMER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: logging.error(f"Error saving customer data: {e}") # Changed print to logging

def update_customer_name(phone_number, name):
    all_customers = load_customer_data(); clean_phone = phone_number.replace("whatsapp:", "") # Keep this for Twilio, adapt for Meta
    if not name or name == "غير محدد": return
    if clean_phone not in all_customers: all_customers[clean_phone] = {"name": name, "bookings": []}; logging.info(f"New customer profile for {clean_phone} with name: {name}") # Changed print to logging
    elif all_customers[clean_phone].get("name") != name : all_customers[clean_phone]["name"] = name; logging.info(f"Customer name updated for {clean_phone} to: {name}") # Changed print to logging
    save_customer_data(all_customers)

def add_or_update_customer_booking(phone_number, booking_info):
    all_customers = load_customer_data(); clean_phone = phone_number.replace("whatsapp:", "") # Keep this for Twilio, adapt for Meta
    customer_name_in_booking = booking_info.get("name")
    if clean_phone not in all_customers:
        default_name = f"عميل {clean_phone[-4:]}"
        all_customers[clean_phone] = {"name": customer_name_in_booking if customer_name_in_booking and customer_name_in_booking != "غير محدد" else default_name, "bookings": []}
    cust = all_customers[clean_phone]
    if customer_name_in_booking and customer_name_in_booking != "غير محدد" and cust.get("name", "") != customer_name_in_booking: cust["name"] = customer_name_in_booking
    new_booking = {k: booking_info.get(k, "غير محدد") for k in ["specialty", "service_type", "doctor_name", "datetime", "notes"]}
    cust["bookings"].append(new_booking); save_customer_data(all_customers)
    logging.info(f"New booking added for {clean_phone} (Name: {cust['name']})") # Changed print to logging

def get_conversation_history_path(sender_id): return os.path.join(CONVERSATION_HISTORY_FOLDER, f"{sender_id}_history.json")
def load_conversation_history(sender_id):
    history_path = get_conversation_history_path(sender_id)
    if not os.path.exists(history_path): return []
    try:
        with open(history_path, "r", encoding="utf-8") as f: content = f.read(); return json.loads(content) if content.strip() else []
    except (json.JSONDecodeError, FileNotFoundError): return []
    except Exception as e: logging.error(f"Error loading conv history for {sender_id}: {e}"); return [] # Changed print to logging

def save_conversation_history(sender_id, history):
    history_path = get_conversation_history_path(sender_id); max_history_turns = 5; max_history_items = max_history_turns * 2
    if len(history) > max_history_items: history = history[-max_history_items:]
    try:
        with open(history_path, "w", encoding="utf-8") as f: json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e: logging.error(f"Error saving conversation history for {sender_id}: {e}") # Changed print to logging

def add_to_conversation_history(sender_id, role, text):
    history = load_conversation_history(sender_id); history.append({"role": role, "content": text}); save_conversation_history(sender_id, history)

# --- 6. Function to Interact with OpenAI & Extract Booking Info (MODIFIED with Time Hint) ---
def get_openai_reply_and_extract_booking_info(user_msg, sender_number_clean):
    logging.info(f"Processing message for OpenAI from {sender_number_clean}: '{user_msg}'") # Changed print to logging
    user_msg_lower = user_msg.lower()

    # --- Simple keyword-based pre-defined replies ---
    if any(keyword in user_msg_lower for keyword in ["العيون", "عين", "رمد"]):
        logging.info("Keyword for 'eye_department_info' detected."); add_to_conversation_history(sender_number_clean, "user", user_msg) # Changed print to logging
        return get_reply_from_file("eye_department_info"), None
    if any(keyword in user_msg_lower for keyword in ["الأسنان", "اسنان", "سني", "سنان"]):
        logging.info("Keyword for 'dental_department_info' detected."); add_to_conversation_history(sender_number_clean, "user", user_msg) # Changed print to logging
        return get_reply_from_file("dental_department_info"), None
    logging.info("No simple keywords matched or proceeding to OpenAI.") # Changed print to logging

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

    now = datetime.now()
    hour = now.hour
    current_shift = ""
    if 8 <= hour < 16: current_shift = "الصباحي"
    elif 16 <= hour < 24: current_shift = "المسائي"
    else: current_shift = "الليلي"

    time_hint = f"توجيه إضافي لك: الوقت الحالي الآن هو حوالي الساعة {hour}:00 بتوقيت العميل (السعودية)، مما يعني أن الشفت الحالي هو '{current_shift}'. عند اقتراح أقرب موعد لدكتور في أي تخصص بناءً على طلب العميل، يرجى الرجوع للمعلومات المرجعية ومحاولة اختيار طبيب يعمل في هذا الشفت الحالي أو الشفت التالي مباشرة إذا لم يتوفر في الحالي، مع ذكر اسم الطبيب المقترح."

    conversation_history = load_conversation_history(sender_number_clean)
    messages_for_openai = []
    system_message_content = f"{effective_system_prompt}\n\n{time_hint}\n\nالمعلومات المرجعية (استخدم هذه للإجابة إذا كانت ذات صلة):\n{REFERENCE}"
    messages_for_openai.append({"role": "system", "content": system_message_content})
    messages_for_openai.extend(conversation_history)
    messages_for_openai.append({"role": "user", "content": user_msg})

    ai_model_reply_text = get_reply_from_file("error_generic_ai")
    extracted_info = None
    name_extracted_this_turn = None

    try:
        logging.info(f"Sending to OpenAI for {sender_number_clean}: ... Total messages: {len(messages_for_openai)}") # Changed print to logging
        # logging.debug(f"System Message sent to OpenAI:\n{system_message_content}\n--------------------") # Use debug for verbose

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages_for_openai,
            temperature=0.5,
            max_tokens=450
        )

        if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
            ai_model_reply_text = completion.choices[0].message.content.strip()
            logging.info(f"OpenAI Generated Reply for {sender_number_clean}: {ai_model_reply_text[:150]}...") # Changed print to logging
            add_to_conversation_history(sender_number_clean, "user", user_msg)
            add_to_conversation_history(sender_number_clean, "assistant", ai_model_reply_text)
        else:
            logging.warning("OpenAI response was empty or malformed.") # Changed print to logging
            return get_reply_from_file("error_openai_empty_response"), None

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
                if not extracted_info: logging.warning("Warning: ##بيانات_الحجز## tag found but no data extracted.") # Changed print to logging
                else:
                    logging.info(f"Extracted booking data: {extracted_info}") # Changed print to logging
                    if name_extracted_this_turn: update_customer_name(sender_number_clean, name_extracted_this_turn)
            except Exception as e: logging.error(f"Error parsing ##بيانات_الحجز##: {e}") # Changed print to logging

        if not name_extracted_this_turn and not known_customer_name:
            if "أستاذ " in ai_model_reply_text:
                try:
                    potential_name = ai_model_reply_text.split("أستاذ ", 1)[1].split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(c.isdigit() for c in potential_name):
                        update_customer_name(sender_number_clean, potential_name)
                except IndexError: pass
            elif "أستاذة " in ai_model_reply_text:
                 try:
                    potential_name = ai_model_reply_text.split("أستاذة ", 1)[1].split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(c.isdigit() for c in potential_name):
                        update_customer_name(sender_number_clean, potential_name)
                 except IndexError: pass

    except openai.APIConnectionError as e: logging.error(f"OpenAI Connection Error: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_connection") # Changed print to logging
    except openai.RateLimitError as e: logging.error(f"OpenAI Rate Limit: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_ratelimit") # Changed print to logging
    except openai.AuthenticationError as e: logging.error(f"OpenAI Auth Error: {e}"); ai_model_reply_text = get_reply_from_file("error_openai_auth") # Changed print to logging
    except openai.APIStatusError as e: logging.error(f"OpenAI API Error {e.status_code}: {e.message if hasattr(e, 'message') else e.response.text if hasattr(e, 'response') else str(e)}"); ai_model_reply_text = get_reply_from_file("error_openai_status", status_code=e.status_code if hasattr(e, 'status_code') else 'Unknown') # Changed print to logging
    except Exception as e: logging.exception(f"General OpenAI Error: {e}, Type: {type(e)}") # Changed print to logging, used .exception to log stacktrace
        
    return ai_model_reply_text, extracted_info

# --- 7. Twilio Webhook & Web Chat Endpoint ---
@app.route("/whatsapp", methods=["POST"]) # This is your existing Twilio webhook
def whatsapp_reply():
    incoming_msg = request.values.get("Body", "").strip()
    sender_full = request.values.get("From", "")
    sender_clean = sender_full.replace("whatsapp:", "")
    if not incoming_msg: return Response(status=204)

    logging.info(f"--- Twilio WhatsApp Request from {sender_full} ---") # Changed print to logging
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
        except Exception as e: logging.error(f"Error saving booking for {sender_clean}: {e}") # Changed print to logging

    twiml_response = MessagingResponse()
    twiml_response.message(final_reply_to_user)
    logging.info(f"Sending Twilio reply to {sender_full}: {final_reply_to_user[:100]}...") # Changed print to logging
    return Response(str(twiml_response), mimetype='application/xml')

@app.route("/chat", methods=["POST"]) # For the web interface
def handle_web_chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        if not user_message:
            return jsonify({"reply": get_reply_from_file("error_web_no_message", default_reply="No message received.")}), 400

        web_user_id = "web_chat_user_01"
        logging.info(f"--- Web Chat Request from {web_user_id} ---") # Changed print to logging
        ai_reply_text, booking_data_web = get_openai_reply_and_extract_booking_info(user_message, web_user_id)

        if booking_data_web: logging.info(f"Booking data extracted from web chat: {booking_data_web}") # Changed print to logging
        return jsonify({"reply": ai_reply_text})
    except Exception as e:
        logging.error(f"Error in /chat endpoint: {e}") # Changed print to logging
        return jsonify({"reply": get_reply_from_file("error_generic_web", default_reply="Server error processing web chat.")}), 500

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# --- Test Routes & App Run ---
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

# --- Function to send message via Meta Graph API (NEW - Needs Implementation) ---
def send_meta_whatsapp_message(recipient_wa_id, message_text):
    # This function needs your WhatsApp Business Account ID and a Page Access Token
    # Store these securely, e.g., in .env file
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
    PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN") # A long-lived Page Access Token

    if not WHATSAPP_BUSINESS_ACCOUNT_ID or not PAGE_ACCESS_TOKEN:
        logging.error("Missing WHATSAPP_BUSINESS_ACCOUNT_ID or PAGE_ACCESS_TOKEN for sending Meta reply.")
        return False

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/messages" # Use current API version
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_wa_id,
        "type": "text",
        "text": {"body": message_text},
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors
        logging.info(f"Message sent successfully to {recipient_wa_id} via Meta. Response: {response.json()}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message via Meta Graph API to {recipient_wa_id}: {e}")
        if e.response is not None:
            logging.error(f"Meta API Response content: {e.response.text}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error in send_meta_whatsapp_message: {e}")
        return False


if __name__ == "__main__":
    if not os.path.exists(CUSTOMER_DATA_FILE): save_customer_data({})
    critical_errors = False
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV": logging.critical("!"*40 + "\n!!! CRITICAL: OPENAI_API_KEY is not set. Bot WILL NOT WORK. !!!\n" + "!"*40); critical_errors = True # Changed print to logging
    if not SYSTEM_PROMPT: logging.warning("!"*40 + "\n!!! WARNING: SYSTEM_PROMPT is empty. Bot responses will be poor. !!!\n" + "!"*40) # Changed print to logging
    if not REPLIES: logging.warning("!"*40 + "\n!!! WARNING: REPLIES file not loaded or empty. !!!\n" + "!"*40) # Changed print to logging
    if critical_errors: logging.critical("!!! Exiting due to critical configuration errors. !!!") # Changed print to logging; # exit(1) can be added
    
    # Add check for Meta tokens if you intend to use the send function
    if not os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or not os.getenv("PAGE_ACCESS_TOKEN"):
        logging.warning("!!! WARNING: WHATSAPP_BUSINESS_ACCOUNT_ID or PAGE_ACCESS_TOKEN not set. Replies via Meta webhook will not work. !!!")

    logging.info("Bot (Web & WhatsApp - Twilio & Meta Webhook Ready) is initializing with OpenAI...") # Changed print to logging
    # For production, use a proper WSGI server like Gunicorn or Waitress
    # app.run(debug=False, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000))) # Kept debug=True for now as in original
