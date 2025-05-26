from flask import Blueprint, request, jsonify, current_app # ضيفنا current_app عشان نوصل للـ logger بتاع الـ app الرئيسي
import os
import json # لاستخدام dumps في اللوجينج
import logging

# --- Mock send_whatsapp_message (استبدلها بالدالة الحقيقية من send_meta.py) ---
# مثال لو send_meta.py فيه دالة اسمها send_whatsapp_message
# from ..utils.send_meta import send_whatsapp_message
# أو لو send_meta.py هو كلاس
# from ..utils.send_meta import SendMeta
# sender_instance = SendMeta() # لو محتاج تعمل instance
# def send_whatsapp_message(to_phone_number: str, message_text: str):
#    return sender_instance.send_message(to_phone_number, message_text)

def send_whatsapp_message(to_phone_number: str, message_text: str):
    # استخدم logger الـ app الرئيسي لو متاح، أو print لو لأ
    if current_app:
        current_app.logger.info(f"SIMULATING SEND to {to_phone_number}: '{message_text}'")
    else:
        print(f"SIMULATING SEND to {to_phone_number}: '{message_text}'")
    pass
# --- نهاية الـ Mock ---


# ... (باقي الكود فوق، زي الـ mock بتاع send_whatsapp_message)

# --- استيراد الـ helper functions و openai_logic ---
# بما إن app.py هو نقطة البداية وهو في الـ root (AICOMPANYCODEBASICPA...),
# و utils و routes مجلدات داخلية، نقدر نستوردهم مباشرة.

from utils.helpers import (
    store_user_info,
    get_user_info,
    get_user_language,
    get_reply_from_json,
    get_static_reply,
    add_to_conversation_history,
    load_conversation_history
)
from utils.openai_logic import generate_openai_response

# ... (باقي الكود تحت، زي تعريف الـ Blueprint)


# تعريف الـ Blueprint
webhook_bp = Blueprint('webhook_bp', __name__) # <--- ده الـ webhook_bp اللي هيتم استيراده

# استخدام الـ logger بتاع الـ app الرئيسي أفضل عشان يكون اللوجينج مركزي
# بس لو عايز logger خاص بالـ blueprint ده، ممكن تعمل كده:
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # أو حسب الـ app config

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_default_verify_token_if_not_set")

@webhook_bp.route('/webhook', methods=['GET', 'POST']) # <--- استخدمنا webhook_bp.route
def webhook_handler():
    logger = current_app.logger # الوصول للـ logger بتاع الـ app الرئيسي
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            logger.info("Webhook GET verification successful.")
            return request.args.get('hub.challenge'), 200
        else:
            logger.warning("Webhook GET verification failed.")
            return 'Forbidden', 403
    
    if request.method == 'POST':
        data = request.get_json()
        # تعديل في اللوج عشان يعرض الـ JSON بشكل مقروء أكتر في اللوجات
        logger.info(f"Received webhook data: {json.dumps(data, indent=2, ensure_ascii=False)}")


        if data and data.get('object') == 'whatsapp_business_account':
            try:
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                if 'messages' not in value:
                    logger.info("No 'messages' field in webhook data. Skipping.")
                    return jsonify({'status': 'no_message_field'}), 200

                message_object = value.get('messages', [{}])[0]
                
                if message_object.get('type') != 'text':
                    logger.info(f"Received non-text message type: {message_object.get('type')}")
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                from_user_id = message_object.get('from')
                msg_body = message_object.get('text', {}).get('body', '').strip()
                
                if not from_user_id or not msg_body:
                    logger.warning("Missing 'from' or 'msg_body' in message object.")
                    return jsonify({'status': 'missing_data_in_message'}), 400

                logger.info(f"Processing message from {from_user_id}: '{msg_body}'")
                
                add_to_conversation_history(from_user_id, "user", msg_body)

                user_data = get_user_info(from_user_id)
                onboarding_step = user_data.get("onboarding_step", "awaiting_language")
                current_lang = user_data.get("language", "en")

                reply_message_key = None
                reply_text_direct = None
                reply_kwargs = {}
                signature_type = "static"

                # 1. ONBOARDING FLOW
                if onboarding_step != "completed":
                    logger.info(f"User {from_user_id} at onboarding step: {onboarding_step}")
                    if onboarding_step == "awaiting_language":
                        reply_message_key = "welcome_najdaigent"
                        store_user_info(from_user_id, "onboarding_step", "awaiting_language_selection")
                    
                    elif onboarding_step == "awaiting_language_selection":
                        if msg_body == "1" or "english" in msg_body.lower():
                            current_lang = "en"
                            store_user_info(from_user_id, "language", current_lang)
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
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
                            welcome_again = get_reply_from_json("welcome_najdaigent", "en") # Bilingual
                            reply_text_direct = get_reply_from_json(reply_message_key, current_lang if user_data.get("language") else "en") + f"\n\n{welcome_again}"
                    
                    elif onboarding_step == "awaiting_name":
                        user_name = msg_body
                        store_user_info(from_user_id, "name", user_name)
                        store_user_info(from_user_id, "onboarding_step", "awaiting_service_interest")
                        reply_message_key = "ask_service_interest"
                        reply_kwargs = {"name": user_name}
                    
                    elif onboarding_step == "awaiting_service_interest":
                        service_interest = msg_body
                        store_user_info(from_user_id, "service_interest", service_interest)
                        store_user_info(from_user_id, "onboarding_step", "completed")
                        user_name = user_data.get("name", "Valued User")
                        reply_message_key = "onboarding_complete"
                        reply_kwargs = {"name": user_name}
                
                # 2. REGULAR INTERACTION
                else:
                    logger.info(f"User {from_user_id} onboarding complete. Processing regular message.")
                    current_lang = get_user_language(from_user_id)

                    static_answer = get_static_reply(msg_body, current_lang)
                    if static_answer:
                        logger.info(f"Static FAQ match found for '{msg_body}' in {current_lang}.")
                        reply_text_direct = static_answer
                        signature_type = "static"
                    else:
                        logger.info(f"No static FAQ match. Falling back to OpenAI for '{msg_body}' in {current_lang}.")
                        conversation_hist = load_conversation_history(from_user_id)
                        ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                        reply_text_direct = ai_response
                        signature_type = "openai"

                final_reply_to_send = ""
                if reply_message_key:
                    final_reply_to_send = get_reply_from_json(reply_message_key, current_lang, **reply_kwargs)
                elif reply_text_direct:
                    final_reply_to_send = reply_text_direct
                
                if final_reply_to_send:
                    if signature_type == "openai":
                        final_reply_to_send += get_reply_from_json("signature_openai", current_lang)
                    else:
                        final_reply_to_send += get_reply_from_json("signature_static", current_lang)
                    
                    send_whatsapp_message(from_user_id, final_reply_to_send)
                    add_to_conversation_history(from_user_id, "assistant", final_reply_to_send)
                    logger.info(f"Sent reply to {from_user_id} with '{signature_type}' signature.")

            except Exception as e:
                logger.error(f"Error processing webhook: {e}", exc_info=True)
                try:
                    error_lang = get_user_language(from_user_id) if 'from_user_id' in locals() else 'en'
                    error_msg = get_reply_from_json("error_occurred", error_lang)
                    if 'from_user_id' in locals():
                         send_whatsapp_message(from_user_id, error_msg)
                except Exception as e_send:
                    logger.error(f"Failed to send error message to user: {e_send}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        return jsonify({'status': 'received_ok'}), 200
