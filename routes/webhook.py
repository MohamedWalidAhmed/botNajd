from flask import Flask, request, jsonify
import os
import logging # For better logging

# Assuming send_meta.py is in utils and has a function to send messages
# from utils.send_meta import send_whatsapp_message 
# For this example, I'll mock it. Replace with your actual import and initialization if needed.
# If send_meta is a class:
# from utils.send_meta import SendMeta
# sender = SendMeta() # Initialize if it's a class
# def send_whatsapp_message(to_phone_number: str, message_text: str):
#    return sender.send_message(to_phone_number, message_text)

# Mock for now:
def send_whatsapp_message(to_phone_number: str, message_text: str):
    app.logger.info(f"SIMULATING SEND to {to_phone_number}: '{message_text}'")
    # In your actual code, this will call the WhatsApp Cloud API
    pass


# Import helper functions from the utils directory
# Ensure your Python path allows this import structure (e.g. by running app from AICO... root)
# or adjust paths if utils is structured differently relative to routes.
# If webhook.py is in routes/ and utils/ is at the same level as routes/, then:
# from ..utils.helpers import (
# or configure PYTHONPATH
from utils.helpers import (
    store_user_info,
    get_user_info,
    get_user_language,
    get_reply_from_json,
    get_static_reply,
    add_to_conversation_history,
    load_conversation_history
)
# from ..utils.openai_logic import generate_openai_response
from utils.openai_logic import generate_openai_response


app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


# Your WhatsApp Business Account VERIFY_TOKEN from .env
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_default_verify_token_if_not_set")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook_handler(): # Renamed to avoid conflict with flask 'webhook'
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            app.logger.info("Webhook GET verification successful.")
            return request.args.get('hub.challenge'), 200
        else:
            app.logger.warning("Webhook GET verification failed.")
            return 'Forbidden', 403
    
    if request.method == 'POST':
        data = request.get_json()
        app.logger.info(f"Received webhook data: {json.dumps(data, indent=2)}")

        if data and data.get('object') == 'whatsapp_business_account':
            try:
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                # Check for messages field
                if 'messages' not in value:
                    app.logger.info("No 'messages' field in webhook data. Skipping.")
                    return jsonify({'status': 'no_message_field'}), 200

                message_object = value.get('messages', [{}])[0]
                
                if message_object.get('type') != 'text':
                    app.logger.info(f"Received non-text message type: {message_object.get('type')}")
                    # Optionally send a message saying you only process text
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                # phone_number_id = value.get('metadata', {}).get('phone_number_id') # Bot's number
                from_user_id = message_object.get('from') # User's WhatsApp ID (phone number)
                msg_body = message_object.get('text', {}).get('body', '').strip()
                
                if not from_user_id or not msg_body:
                    app.logger.warning("Missing 'from' or 'msg_body' in message object.")
                    return jsonify({'status': 'missing_data_in_message'}), 400

                app.logger.info(f"Processing message from {from_user_id}: '{msg_body}'")
                
                # Add incoming user message to history (before processing response)
                add_to_conversation_history(from_user_id, "user", msg_body)

                user_data = get_user_info(from_user_id)
                onboarding_step = user_data.get("onboarding_step", "awaiting_language")
                current_lang = user_data.get("language", "en") # Default to 'en' for initial interactions

                reply_message_key = None # Key from replies.json
                reply_text_direct = None # Direct text for FAQ or OpenAI
                reply_kwargs = {}      # For formatting replies.json messages
                signature_type = "static" # Default signature

                # 1. ONBOARDING FLOW
                if onboarding_step != "completed":
                    app.logger.info(f"User {from_user_id} at onboarding step: {onboarding_step}")
                    if onboarding_step == "awaiting_language":
                        # This is the first interaction or reset. Send bilingual welcome.
                        reply_message_key = "welcome_najdaigent"
                        # Language for this specific message should be one that contains both choices
                        # We'll use 'en' as the key for the bilingual message in replies.json
                        store_user_info(from_user_id, "onboarding_step", "awaiting_language_selection")
                    
                    elif onboarding_step == "awaiting_language_selection":
                        if msg_body == "1" or "english" in msg_body.lower():
                            current_lang = "en"
                            store_user_info(from_user_id, "language", current_lang)
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            # Send two messages: confirmation and next question
                            confirm_lang_text = get_reply_from_json("language_selected_en", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        elif msg_body == "2" or "عربية" in msg_body or "arabic" in msg_body.lower():
                            current_lang = "ar"
                            store_user_info(from_user_id, "language", current_lang)
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            confirm_lang_text = get_reply_from_json("language_selected_ar", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        else:
                            reply_message_key = "invalid_language_choice"
                            # Append the welcome message again for clarity
                            welcome_again = get_reply_from_json("welcome_najdaigent", "en") # Bilingual
                            reply_text_direct = get_reply_from_json(reply_message_key, current_lang) + f"\n\n{welcome_again}"
                    
                    elif onboarding_step == "awaiting_name":
                        user_name = msg_body # Consider basic validation/sanitization if needed
                        store_user_info(from_user_id, "name", user_name)
                        store_user_info(from_user_id, "onboarding_step", "awaiting_service_interest")
                        reply_message_key = "ask_service_interest"
                        reply_kwargs = {"name": user_name}
                    
                    elif onboarding_step == "awaiting_service_interest":
                        service_interest = msg_body
                        store_user_info(from_user_id, "service_interest", service_interest)
                        store_user_info(from_user_id, "onboarding_step", "completed")
                        user_name = user_data.get("name", "Valued User") # Fallback
                        reply_message_key = "onboarding_complete"
                        reply_kwargs = {"name": user_name}
                
                # 2. REGULAR INTERACTION (Onboarding Completed)
                else:
                    app.logger.info(f"User {from_user_id} onboarding complete. Processing regular message.")
                    current_lang = get_user_language(from_user_id) # Get confirmed language

                    # 2.1 Check for Static FAQ reply
                    static_answer = get_static_reply(msg_body, current_lang)
                    if static_answer:
                        app.logger.info(f"Static FAQ match found for '{msg_body}' in {current_lang}.")
                        reply_text_direct = static_answer
                        signature_type = "static"
                    else:
                        # 2.2 Fallback to OpenAI
                        app.logger.info(f"No static FAQ match. Falling back to OpenAI for '{msg_body}' in {current_lang}.")
                        # Optional: Send an acknowledgement message
                        # ack_msg = get_reply_from_json("openai_fallback_acknowledge", current_lang)
                        # send_whatsapp_message(from_user_id, ack_msg)
                        
                        conversation_hist = load_conversation_history(from_user_id)
                        # Remove the last user message we just added, as OpenAI function will add it again
                        # or ensure generate_openai_response expects history *including* current user message.
                        # For this example, let's assume generate_openai_response expects history *before* current user message, then adds it.
                        # So, if add_to_conversation_history(user_id, "user", msg_body) was called,
                        # pass conversation_hist[:-1] if generate_openai_response adds the user message itself.
                        # My current openai_logic.py expects the full history INCLUDING the latest user message.
                        
                        ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                        reply_text_direct = ai_response
                        signature_type = "openai"

                # Construct final reply
                final_reply_to_send = ""
                if reply_message_key:
                    final_reply_to_send = get_reply_from_json(reply_message_key, current_lang, **reply_kwargs)
                elif reply_text_direct:
                    final_reply_to_send = reply_text_direct
                
                # Add signature
                if final_reply_to_send: # Only add signature if there's a message
                    if signature_type == "openai":
                        final_reply_to_send += get_reply_from_json("signature_openai", current_lang)
                    else: # Static replies or onboarding messages
                        final_reply_to_send += get_reply_from_json("signature_static", current_lang)
                    
                    send_whatsapp_message(from_user_id, final_reply_to_send)
                    add_to_conversation_history(from_user_id, "assistant", final_reply_to_send)
                    app.logger.info(f"Sent reply to {from_user_id} with '{signature_type}' signature.")

            except Exception as e:
                app.logger.error(f"Error processing webhook: {e}", exc_info=True)
                # Send a generic error message to the user
                try:
                    error_lang = get_user_language(from_user_id) if 'from_user_id' in locals() else 'en'
                    error_msg = get_reply_from_json("error_occurred", error_lang)
                    if 'from_user_id' in locals():
                         send_whatsapp_message(from_user_id, error_msg)
                except Exception as e_send:
                    app.logger.error(f"Failed to send error message to user: {e_send}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        return jsonify({'status': 'received_ok'}), 200

if __name__ == "__main__":
    # For local development:
    # Ensure you have .env file with WHATSAPP_VERIFY_TOKEN and OPENAI_API_KEY
    # from dotenv import load_dotenv
    # load_dotenv()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
    # For production, use a WSGI server like Gunicorn:
    # gunicorn --bind 0.0.0.0:5000 webhook:app
