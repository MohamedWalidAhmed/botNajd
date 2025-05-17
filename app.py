import os
import json
import openai # For OpenAI API
import requests # Still needed if you decide to add other API calls, but not directly for OpenAI client
from flask import Flask, request, Response, jsonify # Added jsonify for test routes
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
# from datetime import datetime, timedelta # Not strictly needed for current logic

# --- 1. Load Environment Variables ---
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
    print("!!! The bot WILL NOT function correctly without a valid API key. !!!")
    OPENAI_API_KEY = "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV" # Replace or ensure it's in .env

# --- Initialize OpenAI Client ---
client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized successfully.")
    except Exception as e:
        print(f"!!! CRITICAL ERROR initializing OpenAI client: {e} !!!")
        print("!!! Ensure your OPENAI_API_KEY is correct and the 'openai' library is installed. !!!")
else:
    print("!!! OpenAI client NOT initialized due to missing or placeholder API key. !!!")
    print("!!! The bot will not be able to communicate with OpenAI. !!!")

# --- 2. Define Paths for External Config Files ---
CONFIG_DATA_FOLDER = "config_data"
SYSTEM_PROMPT_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "system_prompt.txt")
REFERENCE_FILE_PATH = os.path.join(CONFIG_DATA_FOLDER, "reference_data.txt")

# --- 3. Load SYSTEM_PROMPT and REFERENCE from External Files ---
SYSTEM_PROMPT = ""
try:
    if not os.path.exists(SYSTEM_PROMPT_FILE_PATH):
        print(f"!!! ERROR: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' not found. Bot will use an empty system prompt. !!!")
    else:
        with open(SYSTEM_PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
            SYSTEM_PROMPT = f.read().strip()
        if SYSTEM_PROMPT:
            print(f"System prompt loaded successfully from: '{SYSTEM_PROMPT_FILE_PATH}'")
        else:
            print(f"!!! WARNING: System prompt file '{SYSTEM_PROMPT_FILE_PATH}' is empty. Bot performance will be affected. !!!")
except Exception as e:
    print(f"!!! ERROR reading system prompt file '{SYSTEM_PROMPT_FILE_PATH}': {e} !!!")

REFERENCE = ""
try:
    if not os.path.exists(REFERENCE_FILE_PATH):
        print(f"!!! WARNING: Reference file '{REFERENCE_FILE_PATH}' not found. No reference data will be used. !!!")
    else:
        with open(REFERENCE_FILE_PATH, "r", encoding="utf-8") as f:
            REFERENCE = f.read().strip()
        if REFERENCE:
            print(f"Reference data loaded successfully from: '{REFERENCE_FILE_PATH}'")
        else:
            print(f"Warning: Reference file '{REFERENCE_FILE_PATH}' is empty.")
except Exception as e:
    print(f"!!! ERROR reading reference data file '{REFERENCE_FILE_PATH}': {e} !!!")

# --- 4. Flask App Setup & Data Folders ---
app = Flask(__name__)
CUSTOMERS_FOLDER = "customers"
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_FOLDER, "customer_data.json")
CONVERSATION_HISTORY_FOLDER = "conversation_history"

if not os.path.exists(CUSTOMERS_FOLDER):
    try: os.makedirs(CUSTOMERS_FOLDER)
    except OSError as e: print(f"Error creating customers folder: {e}")
if not os.path.exists(CONVERSATION_HISTORY_FOLDER):
    try: os.makedirs(CONVERSATION_HISTORY_FOLDER)
    except OSError as e: print(f"Error creating conversation history folder: {e}")


# --- 5. Helper Functions for Customer Data & Conversation History ---
def load_customer_data():
    if not os.path.exists(CUSTOMER_DATA_FILE):
        return {}
    try:
        with open(CUSTOMER_DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content.strip() else {}
    except json.JSONDecodeError:
        print(f"Warning: '{CUSTOMER_DATA_FILE}' is corrupted or not valid JSON. Returning empty data.")
        return {}
    except Exception as e:
        print(f"Error loading customer data from '{CUSTOMER_DATA_FILE}': {e}")
        return {}

def save_customer_data(data):
    try:
        with open(CUSTOMER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # print(f"Customer data saved to '{CUSTOMER_DATA_FILE}'") # Optional: for debugging
    except Exception as e:
        print(f"Error saving customer data to '{CUSTOMER_DATA_FILE}': {e}")

def update_customer_name(phone_number, name):
    """Updates or sets the customer's name in the customer data file."""
    all_customers = load_customer_data()
    clean_phone = phone_number.replace("whatsapp:", "")
    if not name or name == "غير محدد": # Don't save if name is invalid
        return

    if clean_phone not in all_customers:
        all_customers[clean_phone] = {"name": name, "bookings": []}
        print(f"New customer profile created for {clean_phone} with name: {name}")
    elif all_customers[clean_phone].get("name") != name : # Update only if different or not set
        all_customers[clean_phone]["name"] = name
        print(f"Customer name updated for {clean_phone} to: {name}")
    save_customer_data(all_customers)


def add_or_update_customer_booking(phone_number, booking_info):
    """Adds a new booking to a customer's record. Updates name if provided."""
    all_customers = load_customer_data()
    clean_phone = phone_number.replace("whatsapp:", "")
    
    customer_name_in_booking = booking_info.get("name")

    if clean_phone not in all_customers:
        # If customer is new, use the name from booking_info or a default
        default_name = f"عميل {clean_phone[-4:]}"
        all_customers[clean_phone] = {
            "name": customer_name_in_booking if customer_name_in_booking and customer_name_in_booking != "غير محدد" else default_name,
            "bookings": []
        }
        print(f"New customer profile created for booking: {clean_phone}")
    
    current_customer = all_customers[clean_phone]
    # Update customer's main name if a valid one is in booking_info and different from current
    if customer_name_in_booking and \
       customer_name_in_booking != "غير محدد" and \
       current_customer.get("name", "") != customer_name_in_booking:
        current_customer["name"] = customer_name_in_booking
        print(f"Customer name updated via booking for {clean_phone} to: {customer_name_in_booking}")

    new_booking = {
        "specialty": booking_info.get("specialty", "غير محدد"),
        "service_type": booking_info.get("service_type", "غير محدد"),
        "doctor_name": booking_info.get("doctor_name", "غير محدد"),
        "datetime": booking_info.get("datetime", "غير محدد"),
        "notes": booking_info.get("notes", "")
    }
    current_customer["bookings"].append(new_booking)
    save_customer_data(all_customers)
    print(f"New booking added for {clean_phone} (Name: {current_customer['name']})")


def get_conversation_history_path(sender_id):
    return os.path.join(CONVERSATION_HISTORY_FOLDER, f"{sender_id}_history.json")

def load_conversation_history(sender_id):
    history_path = get_conversation_history_path(sender_id)
    if not os.path.exists(history_path):
        return []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content.strip() else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    except Exception as e:
        print(f"Error loading conversation history for {sender_id}: {e}")
        return []


def save_conversation_history(sender_id, history):
    history_path = get_conversation_history_path(sender_id)
    max_history_turns = 5  # Keep last 5 user/assistant turns (10 messages total)
    max_history_items = max_history_turns * 2
    if len(history) > max_history_items:
        history = history[-max_history_items:]
    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving conversation history for {sender_id}: {e}")

def add_to_conversation_history(sender_id, role, text):
    history = load_conversation_history(sender_id)
    history.append({"role": role, "content": text}) # OpenAI uses 'content'
    save_conversation_history(sender_id, history)

# --- 6. Function to Interact with OpenAI & Extract Booking Info ---
def get_openai_reply_and_extract_booking_info(user_msg, sender_number_clean):
    print(f"Processing message for OpenAI from {sender_number_clean}: '{user_msg}'")

    if not client:
        print("OpenAI client not initialized. Aborting API call.")
        return "عفواً، خدمة الذكاء الاصطناعي غير مهيأة بشكل صحيح.", None
    if not SYSTEM_PROMPT:
        print("Warning: System prompt is empty. This will likely lead to poor AI responses.")
        # Fallback or error, depending on desired behavior
        return "عفواً، هناك مشكلة في إعدادات المساعد الأساسية.", None

    # --- Load customer's known name to pass in System Prompt ---
    customer_profile = load_customer_data().get(sender_number_clean)
    known_customer_name = None
    if customer_profile and customer_profile.get("name") and customer_profile.get("name") != "غير محدد":
        known_customer_name = customer_profile["name"]
        print(f"Known customer: {known_customer_name} ({sender_number_clean})")
    
    effective_system_prompt = SYSTEM_PROMPT
    if known_customer_name:
        # Prepend information about the known customer to the system prompt
        effective_system_prompt = (
            f"أنت تتحدث الآن مع العميل المعروف لدينا: الأستاذ/الأستاذة {known_customer_name} (رقمه: {sender_number_clean}). "
            f"خاطبه بهذا الاسم ولا تطلب اسمه مرة أخرى إلا إذا طلب هو تغييره.\n\n"
            f"{SYSTEM_PROMPT}"
        )
    # --- End of customer name injection ---

    conversation_history = load_conversation_history(sender_number_clean)
    messages_for_openai = []
    
    system_message_content = f"{effective_system_prompt}\n\nالمعلومات المرجعية (استخدم هذه للإجابة إذا كانت ذات صلة):\n{REFERENCE}"
    messages_for_openai.append({"role": "system", "content": system_message_content})
    
    messages_for_openai.extend(conversation_history)
    messages_for_openai.append({"role": "user", "content": user_msg})

    ai_model_reply_text = "عفواً، أواجه بعض الصعوبات حالياً. يرجى المحاولة مرة أخرى بعد قليل."
    extracted_info = None
    name_extracted_this_turn = None

    try:
        print(f"Sending to OpenAI (model: gpt-3.5-turbo): First 3 msgs: {json.dumps(messages_for_openai[:3], ensure_ascii=False, indent=2)} ... Total: {len(messages_for_openai)}")
        
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages_for_openai,
            temperature=0.6, # Slightly lower temperature for more predictable responses
            max_tokens=400
        )
        
        if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
            ai_model_reply_text = completion.choices[0].message.content.strip()
            print(f"OpenAI Generated Reply: {ai_model_reply_text}")
            
            add_to_conversation_history(sender_number_clean, "user", user_msg)
            add_to_conversation_history(sender_number_clean, "assistant", ai_model_reply_text)
        else:
            print("OpenAI response was empty or malformed.")
            return "عفواً، تلقيت رداً غير متوقع من الذكاء الاصطناعي.", None

        if "##بيانات_الحجز##" in ai_model_reply_text:
            try:
                _, details_part_with_tag = ai_model_reply_text.split("##بيانات_الحجز##", 1)
                details_part = details_part_with_tag.strip()
                extracted_info = {}
                for line in details_part.split('\n'):
                    if ':' in line:
                        key_val = line.split(':', 1)
                        key = key_val[0].strip()
                        value = key_val[1].strip() if len(key_val) > 1 else ""
                        key_map = {
                            "الاسم": "name", "اسم المريض": "name", "الاسم الكريم": "name",
                            "التخصص": "specialty",
                            "نوع الخدمة": "service_type", "الخدمة": "service_type",
                            "الدكتور": "doctor_name",
                            "الوقت والتاريخ": "datetime", "الموعد": "datetime",
                            "ملاحظات": "notes"
                        }
                        english_key = key_map.get(key)
                        if english_key:
                            extracted_info[english_key] = value
                            if english_key == "name" and value and value != "غير محدد":
                                name_extracted_this_turn = value
                
                if not extracted_info:
                    print("Warning: ##بيانات_الحجز## tag found but no data was extracted.")
                else:
                    print(f"Extracted booking data: {extracted_info}")
                    if name_extracted_this_turn:
                        # Update customer's persistent name if AI extracted it in booking
                        update_customer_name(sender_number_clean, name_extracted_this_turn)
            except Exception as e:
                print(f"Error parsing ##بيانات_الحجز##: {e}")
        
        # Attempt to capture name even if no booking data tag is present
        # This relies on the SYSTEM_PROMPT guiding the AI to confirm the name.
        if not name_extracted_this_turn and not known_customer_name:
            # Example: if AI says "أهلاً أستاذ محمد، كيف أساعدك؟"
            # This is a simple heuristic and might need refinement based on AI's typical responses
            if "أستاذ " in ai_model_reply_text:
                try:
                    potential_name_parts = ai_model_reply_text.split("أستاذ ", 1)[1]
                    potential_name = potential_name_parts.split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(char.isdigit() for char in potential_name):
                        print(f"Potentially extracted name from general AI reply: {potential_name}")
                        update_customer_name(sender_number_clean, potential_name)
                except IndexError:
                    pass # Name pattern not found
            elif "أستاذة " in ai_model_reply_text:
                 try:
                    potential_name_parts = ai_model_reply_text.split("أستاذة ", 1)[1]
                    potential_name = potential_name_parts.split("،")[0].split(" ")[0].strip()
                    if potential_name and len(potential_name) > 1 and not any(char.isdigit() for char in potential_name):
                        print(f"Potentially extracted name (female) from general AI reply: {potential_name}")
                        update_customer_name(sender_number_clean, potential_name)
                 except IndexError:
                    pass


    except openai.APIConnectionError as e: print(f"OpenAI API Connection Error: {e}"); ai_model_reply_text = "عفواً، لم أتمكن من الاتصال بخدمة الذكاء الاصطناعي."
    except openai.RateLimitError as e: print(f"OpenAI Rate Limit Exceeded: {e}"); ai_model_reply_text = "عفواً، لقد وصلنا إلى حد الاستخدام للذكاء الاصطناعي الآن."
    except openai.AuthenticationError as e: print(f"OpenAI Authentication Error: {e}"); ai_model_reply_text = "عفواً، هناك مشكلة في المصادقة مع خدمة الذكاء الاصطناعي."
    except openai.APIStatusError as e: print(f"OpenAI API Error {e.status_code}: {e.message}"); ai_model_reply_text = f"عفواً، خدمة الذكاء الاصطناعي أرجعت خطأ ({e.status_code})."
    except Exception as e:
        print(f"A general error in get_openai_reply: {e}, Type: {type(e)}")
    
    return ai_model_reply_text, extracted_info

# --- 7. Twilio Webhook for WhatsApp Messages ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    sender_number_full = request.values.get('From', '') 
    sender_number_clean = sender_number_full.replace("whatsapp:", "")
    if not incoming_msg: return Response(status=204)

    print(f"--- New WhatsApp Request from {sender_number_full} ---")
    ai_reply_text, booking_data_extracted = get_openai_reply_and_extract_booking_info(incoming_msg, sender_number_clean)
    
    final_reply_to_user = ai_reply_text

    if booking_data_extracted:
        # Ensure name is present for the booking record
        name_for_booking = booking_data_extracted.get("name")
        if not name_for_booking or name_for_booking == "غير محدد":
            customer_profile = load_customer_data().get(sender_number_clean, {})
            name_for_booking = customer_profile.get("name", f"عميل {sender_number_clean[-4:]}")
        booking_data_extracted["name"] = name_for_booking # Ensure it's set
        
        try:
            add_or_update_customer_booking(sender_number_clean, booking_data_extracted)
            print(f"Booking data saved for customer: {sender_number_clean} (Name: {name_for_booking})")
        except Exception as e: 
            print(f"Error saving booking for customer {sender_number_clean}: {e}")
    
    twiml_response = MessagingResponse()
    twiml_response.message(final_reply_to_user)
    print(f"Sending reply to {sender_number_full}: {final_reply_to_user}")
    return Response(str(twiml_response), mimetype='application/xml')

# --- 8 & 9. Test Routes & App Run ---
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
    if not os.path.exists(CUSTOMER_DATA_FILE): save_customer_data({})
    
    critical_errors = False
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
        print("!"*40 + "\n!!! CRITICAL: OPENAI_API_KEY is not set or is a placeholder. Bot WILL NOT WORK. !!!\n" + "!"*40)
        critical_errors = True
    if not SYSTEM_PROMPT:
        print("!"*40 + "\n!!! WARNING: SYSTEM_PROMPT is empty. Bot responses will be poor. !!!\n" + "!"*40)
        # critical_errors = True # Might still work but poorly
    
    if critical_errors:
        print("!!! Exiting due to critical configuration errors. !!!")
        # exit(1) # Uncomment to force exit if critical errors are present

    print("Bot is ready to run with OpenAI (Conversation History & Persistent Customer Name)...")
    print("Ensure ngrok is running and Twilio Webhook is updated.")
    app.run(debug=True, host='0.0.0.0', port=5000)