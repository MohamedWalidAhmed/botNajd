from flask import Blueprint, request, jsonify, current_app
import os
import json
import logging

# ---------------------------------------------------------------------------- #
#             استيراد دالة الإرسال الحقيقية من utils/send_meta.py              #
# ---------------------------------------------------------------------------- #
try:
    from utils.send_meta import send_whatsapp_message_real
    ACTIVE_MESSAGE_SENDER = send_whatsapp_message_real
except ImportError:
    def mock_send_whatsapp_message(to_phone_number: str, message_text: str):
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"MOCK SEND (Real function not imported) to {to_phone_number}: '{message_text}'")
    ACTIVE_MESSAGE_SENDER = mock_send_whatsapp_message

# --- استيراد الدوال الجديدة من db_helpers و باقي الأدوات --- #
from utils.db_helpers import (
    add_or_update_customer,
    get_customer,
    add_message,
    get_conversation,
)
from utils.helpers import (
    get_user_language,
    get_reply_from_json,
    get_static_reply,
)
from utils.openai_logic import generate_openai_response

# تعريف الـ Blueprint
webhook_bp = Blueprint('webhook_bp', __name__)
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_default_verify_token_if_not_set")

# --- دالة معالجة الـ onboarding والرد المناسب ---
def handle_onboarding(phone, msg_body, user_data):
    onboarding_step = user_data.onboarding_step if user_data and user_data.onboarding_step else "awaiting_language"
    current_lang = user_data.language if user_data and user_data.language else "en"

    if onboarding_step == "awaiting_language":
        # إرسال رسالة ترحيب وخيارات اللغة
        reply = get_reply_from_json("welcome_najdaigent", current_lang)
        add_or_update_customer(phone, onboarding_step="awaiting_language_selection")
        return reply

    elif onboarding_step == "awaiting_language_selection":
        if msg_body == "1" or "english" in msg_body.lower():
            current_lang = "en"
            add_or_update_customer(phone, language=current_lang, onboarding_step="awaiting_name")
            confirm_lang = get_reply_from_json("language_selected_en", current_lang)
            ask_name = get_reply_from_json("ask_name", current_lang)
            return f"{confirm_lang}\n\n{ask_name}"
        elif msg_body == "2" or "عربية" in msg_body or "arabic" in msg_body.lower():
            current_lang = "ar"
            add_or_update_customer(phone, language=current_lang, onboarding_step="awaiting_name")
            confirm_lang = get_reply_from_json("language_selected_ar", current_lang)
            ask_name = get_reply_from_json("ask_name", current_lang)
            return f"{confirm_lang}\n\n{ask_name}"
        else:
            reply = get_reply_from_json("invalid_language_choice", current_lang)
            welcome_again = get_reply_from_json("welcome_najdaigent", current_lang)
            return f"{reply}\n\n{welcome_again}"

    elif onboarding_step == "awaiting_name":
        user_name = msg_body.strip()
        add_or_update_customer(phone, name=user_name, onboarding_step="awaiting_service_interest")
        current_lang = get_user_language(phone)
        reply = get_reply_from_json("ask_service_interest", current_lang, name=user_name)
        return reply

    elif onboarding_step == "awaiting_service_interest":
        service_interest = msg_body.strip()
        add_or_update_customer(phone, service_interest=service_interest, onboarding_step="completed")
        current_lang = get_user_language(phone)
        user_obj = get_customer(phone)
        user_name = user_obj.name if user_obj and user_obj.name else get_reply_from_json("default_username", current_lang)
        reply = get_reply_from_json("onboarding_complete", current_lang, name=user_name)
        return reply

    else:
        # احتياطاً لو فيه خطوة مش متوقعة
        return get_reply_from_json("error_occurred_generic", current_lang)

# --- نقطة الدخول للويب هوك ---
@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook_handler():
    logger = current_app.logger

    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            logger.info("Webhook GET verification successful.")
            return request.args.get('hub.challenge'), 200
        else:
            logger.warning(f"Webhook GET verification failed. Token received: {request.args.get('hub.verify_token')}")
            return 'Forbidden', 403

    if request.method == 'POST':
        data = request.get_json()
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
                    msg_type = message_object.get('type', 'unknown')
                    logger.info(f"Received non-text message type: {msg_type}")
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                from_user_id = message_object.get('from')
                msg_body = message_object.get('text', {}).get('body', '').strip()
                if not from_user_id or not msg_body:
                    logger.warning("Missing 'from' or 'msg_body' in message object.")
                    return jsonify({'status': 'missing_data_in_message'}), 400

                logger.info(f"Processing message from {from_user_id}: '{msg_body}'")
                add_message(from_user_id, "user", msg_body)

                # استرجاع بيانات العميل من قاعدة البيانات
                user_data = get_customer(from_user_id)
                onboarding_step = user_data.onboarding_step if user_data and user_data.onboarding_step else "awaiting_language"

                # إذا العميل في onboarding
                if onboarding_step != "completed":
                    reply = handle_onboarding(from_user_id, msg_body, user_data)
                    ACTIVE_MESSAGE_SENDER(from_user_id, reply)
                    add_message(from_user_id, "assistant", reply)
                    logger.info(f"Onboarding step '{onboarding_step}' processed for user {from_user_id}.")
                    return jsonify({'status': 'onboarding_handled'}), 200

                # -------- التفاعل العادي بعد الـ onboarding -------- #
                current_lang = user_data.language if user_data and user_data.language else "en"
                static_answer = get_static_reply(msg_body, current_lang)

                if static_answer:
                    reply = static_answer + get_reply_from_json("signature_static", current_lang)
                else:
                    conversation_hist = get_conversation(from_user_id)
                    ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                    reply = ai_response + get_reply_from_json("signature_openai", current_lang)

                ACTIVE_MESSAGE_SENDER(from_user_id, reply)
                add_message(from_user_id, "assistant", reply)
                logger.info(f"Regular reply sent to user {from_user_id}.")
                return jsonify({'status': 'reply_sent'}), 200

            except Exception as e:
                logger.error(f"Unhandled error processing webhook POST data: {e}", exc_info=True)
                try:
                    error_lang = 'en'
                    if 'from_user_id' in locals() and from_user_id:
                        user_lang_data = get_customer(from_user_id)
                        if user_lang_data and user_lang_data.language:
                            error_lang = user_lang_data.language
                    error_msg = get_reply_from_json("error_occurred_generic", error_lang)
                    if 'from_user_id' in locals() and from_user_id and error_msg:
                        ACTIVE_MESSAGE_SENDER(from_user_id, error_msg)
                except Exception as e_send:
                    logger.error(f"Failed to send generic error message to user after an exception: {e_send}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 500

        logger.info("Webhook POST received, but not a recognized WhatsApp business account message or no data.")
        return jsonify({'status': 'received_ok_not_processed'}), 200
