from flask import Blueprint, request, jsonify, current_app
import os
import json
import logging

# ---------------------------------------------------------------------------- #
#             🛑▶️▶️▶️ تعديل هام: استيراد دالة الإرسال الحقيقية ◀️◀️◀️🛑             #
# ---------------------------------------------------------------------------- #
# 1. تأكد أن لديك ملف مثلاً utils/send_meta.py يحتوي على دالة الإرسال الفعلية.
# 2. عدّل السطر التالي ليشير إلى دالتك الفعلية.
# 3. تأكد من أن هذه الدالة تأخذ (رقم المستلم، نص الرسالة) كـ arguments.

# مثال لو الدالة اسمها send_whatsapp_message_real في utils/send_meta.py
try:
    from utils.send_meta import send_whatsapp_message_real
    ACTIVE_MESSAGE_SENDER = send_whatsapp_message_real
    # لو الدالة الحقيقية لها اسم آخر، استبدل send_whatsapp_message_real بالاسم الصحيح
    # مثال: from utils.my_whatsapp_sender import actual_send_function
    #       ACTIVE_MESSAGE_SENDER = actual_send_function
except ImportError:
    current_app.logger.error("CRITICAL: Could not import REAL message sending function. Using MOCK.")
    # دالة وهمية في حالة فشل استيراد الدالة الحقيقية (للتشغيل المبدئي فقط)
    def mock_send_whatsapp_message(to_phone_number: str, message_text: str):
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"MOCK SEND (Real function not imported) to {to_phone_number}: '{message_text}'")
        pass
    ACTIVE_MESSAGE_SENDER = mock_send_whatsapp_message

# --- استيراد الـ helper functions و openai_logic ---
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

# تعريف الـ Blueprint
webhook_bp = Blueprint('webhook_bp', __name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_default_verify_token_if_not_set") # تأكد من أن هذا مضبوط في البيئة

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
                    # يمكنك إضافة رد هنا لو أردت، مثلاً "أنا أفهم الرسائل النصية فقط حاليًا"
                    # error_lang_non_text = get_user_language(message_object.get('from')) if message_object.get('from') else 'en'
                    # non_text_reply = get_reply_from_json("unsupported_message_type", error_lang_non_text, msg_type=msg_type)
                    # if message_object.get('from') and non_text_reply:
                    #    ACTIVE_MESSAGE_SENDER(message_object.get('from'), non_text_reply)
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                from_user_id = message_object.get('from')
                msg_body = message_object.get('text', {}).get('body', '').strip()
                
                if not from_user_id or not msg_body:
                    logger.warning("Missing 'from' or 'msg_body' in message object.")
                    return jsonify({'status': 'missing_data_in_message'}), 400

                logger.info(f"Processing message from {from_user_id}: '{msg_body}'")
                
                add_to_conversation_history(from_user_id, "user", msg_body)

                user_data = get_user_info(from_user_id) # يتم تحميل بيانات المستخدم هنا
                onboarding_step = user_data.get("onboarding_step", "awaiting_language")
                current_lang = user_data.get("language", "en") # اللغة الافتراضية هي الإنجليزية

                reply_message_key = None
                reply_text_direct = None
                reply_kwargs = {}
                signature_type = "static" # افتراضي

                # 1. ONBOARDING FLOW
                if onboarding_step != "completed":
                    logger.info(f"User {from_user_id} at onboarding step: {onboarding_step}")
                    if onboarding_step == "awaiting_language":
                        reply_message_key = "welcome_najdaigent" # يجب أن تكون هذه الرسالة بلغتين أو بلغة محايدة
                        store_user_info(from_user_id, "onboarding_step", "awaiting_language_selection")
                    
                    elif onboarding_step == "awaiting_language_selection":
                        if msg_body == "1" or "english" in msg_body.lower():
                            current_lang = "en"
                            store_user_info(from_user_id, {"language": current_lang, "onboarding_step": "awaiting_name"})
                            confirm_lang_text = get_reply_from_json("language_selected_en", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        elif msg_body == "2" or "عربية" in msg_body or "arabic" in msg_body.lower():
                            current_lang = "ar"
                            store_user_info(from_user_id, {"language": current_lang, "onboarding_step": "awaiting_name"})
                            confirm_lang_text = get_reply_from_json("language_selected_ar", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        else:
                            # إذا لم يختار لغة، أعد إرسال رسالة الترحيب وخيارات اللغة
                            reply_message_key = "invalid_language_choice" # مفتاح لرسالة "خيار غير صالح"
                            welcome_again_text = get_reply_from_json("welcome_najdaigent", user_data.get("language", "en")) # أعد رسالة الترحيب باللغة الحالية أو الافتراضية
                            reply_text_direct = get_reply_from_json(reply_message_key, user_data.get("language", "en")) + f"\n\n{welcome_again_text}"
                    
                    elif onboarding_step == "awaiting_name":
                        user_name = msg_body.strip()
                        store_user_info(from_user_id, {"name": user_name, "onboarding_step": "awaiting_service_interest"})
                        current_lang = get_user_language(from_user_id) # تأكد من استخدام اللغة المخزنة
                        reply_message_key = "ask_service_interest"
                        reply_kwargs = {"name": user_name}
                    
                    elif onboarding_step == "awaiting_service_interest":
                        service_interest = msg_body.strip()
                        store_user_info(from_user_id, {"service_interest": service_interest, "onboarding_step": "completed"})
                        current_lang = get_user_language(from_user_id)
                        user_name = get_user_info(from_user_id).get("name", get_reply_from_json("default_username", current_lang)) # اسم افتراضي مترجم
                        reply_message_key = "onboarding_complete"
                        reply_kwargs = {"name": user_name}
                
                # 2. REGULAR INTERACTION (Onboarding completed)
                else:
                    logger.info(f"User {from_user_id} onboarding complete. Processing regular message.")
                    current_lang = get_user_language(from_user_id) # احصل على اللغة الحالية للمستخدم

                    static_answer = get_static_reply(msg_body, current_lang)
                    if static_answer:
                        logger.info(f"Static FAQ match found for '{msg_body}' in {current_lang}.")
                        reply_text_direct = static_answer
                        signature_type = "static"
                    else:
                        logger.info(f"No static FAQ match. Falling back to OpenAI for '{msg_body}' in {current_lang}.")
                        conversation_hist = load_conversation_history(from_user_id)
                        # تأكد من أن generate_openai_response تعالج الـ conversation_hist بشكل صحيح
                        ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                        reply_text_direct = ai_response
                        signature_type = "openai"

                # --- تجميع وإرسال الرد النهائي ---
                final_reply_to_send = ""
                if reply_message_key:
                    # تأكد من أن current_lang هنا هي اللغة الصحيحة للرد
                    lang_for_reply = get_user_language(from_user_id) if onboarding_step == "completed" else current_lang
                    final_reply_to_send = get_reply_from_json(reply_message_key, lang_for_reply, **reply_kwargs)
                elif reply_text_direct:
                    final_reply_to_send = reply_text_direct
                
                if final_reply_to_send:
                    # إضافة التوقيع المناسب
                    lang_for_signature = get_user_language(from_user_id) if onboarding_step == "completed" else current_lang
                    if signature_type == "openai":
                        final_reply_to_send += get_reply_from_json("signature_openai", lang_for_signature)
                    else: # static or onboarding
                        final_reply_to_send += get_reply_from_json("signature_static", lang_for_signature)
                    
                    logger.info(f"Attempting to send to {from_user_id}: '{final_reply_to_send}'")
                    ACTIVE_MESSAGE_SENDER(from_user_id, final_reply_to_send)
                    add_to_conversation_history(from_user_id, "assistant", final_reply_to_send)
                    logger.info(f"Successfully processed and sent reply to {from_user_id} with '{signature_type}' signature.")
                else:
                    logger.info(f"No reply generated for user {from_user_id} with message '{msg_body}'.")


            except Exception as e:
                logger.error(f"Unhandled error processing webhook POST data: {e}", exc_info=True) # exc_info=True لطباعة الـ traceback
                try:
                    # محاولة إرسال رسالة خطأ عامة للمستخدم باللغة التي يفهمها إن أمكن
                    error_lang = 'en' # لغة افتراضية للخطأ
                    if 'from_user_id' in locals() and from_user_id: # إذا كان رقم المستخدم متاحًا
                       user_lang_data = get_user_info(from_user_id)
                       if user_lang_data and user_lang_data.get("language"):
                           error_lang = user_lang_data.get("language")
                    
                    error_msg_key = "error_occurred_generic" # مفتاح لرسالة خطأ عامة جداً
                    error_msg_text = get_reply_from_json(error_msg_key, error_lang)
                    
                    if 'from_user_id' in locals() and from_user_id and error_msg_text:
                         logger.info(f"Attempting to send generic error message to {from_user_id} in {error_lang}.")
                         ACTIVE_MESSAGE_SENDER(from_user_id, error_msg_text)
                except Exception as e_send:
                    logger.error(f"Failed to send generic error message to user after an exception: {e_send}", exc_info=True)
                
                # دائماً أرجع 500 في حالة الخطأ غير المعالج لـ Meta
                return jsonify({'status': 'error', 'message': str(e)}), 500

        # إذا لم يكن الكائن هو 'whatsapp_business_account' أو لا توجد بيانات
        logger.info("Webhook POST received, but not a recognized WhatsApp business account message or no data.")
        return jsonify({'status': 'received_ok_not_processed'}), 200
