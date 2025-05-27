from flask import Blueprint, request, jsonify, current_app
import os
import json
import logging # مهم يبقى موجود حتى لو هنعتمد على current_app.logger أحياناً

# ---------------------------------------------------------------------------- #
#             🛑▶️▶️▶️ تعديل هام: استيراد دالة الإرسال الحقيقية ◀️◀️◀️🛑             #
# ---------------------------------------------------------------------------- #
# 1. تأكد أن لديك ملف مثلاً utils/send_meta.py يحتوي على دالة الإرسال الفعلية
#    باسم send_whatsapp_message_real أو أي اسم تختاره.
# 2. إذا كان الاسم مختلفًا، عدّل السطر التالي:
#    from utils.send_meta import your_actual_send_function_name as send_whatsapp_message_real

ACTIVE_MESSAGE_SENDER = None
try:
    # حاول تستورد الدالة الحقيقية
    from utils.send_meta import send_whatsapp_message_real # <--- تأكد إن الاسم ده صح!
    ACTIVE_MESSAGE_SENDER = send_whatsapp_message_real
    # استخدام logger الـ app لو متاح، لو لأ يبقى logging العادي
    # هذه الطريقة قد لا تعمل دائماً لـ current_app.logger قبل تهيئة الـ app بالكامل
    _logger_init = current_app.logger if current_app else logging.getLogger(__name__)
    _logger_init.info("Successfully imported REAL message sender: send_whatsapp_message_real")

except ImportError as e:
    # لو فشل، استخدم دالة وهمية وسجل خطأ فادح
    _logger_init = current_app.logger if current_app else logging.getLogger(__name__)
    _logger_init.critical(f"CRITICAL IMPORT ERROR: Could not import 'send_whatsapp_message_real' from 'utils.send_meta'. Using MOCK sender. Error: {e}")
    
    def mock_send_whatsapp_message(to_phone_number: str, message_text: str):
        # استخدم الـ logger اللي عرفناه فوق
        _logger_init.info(f"MOCK SEND (Real function NOT IMPORTED) to {to_phone_number}: '{message_text}'")
        # pass # مش محتاجين pass هنا، الدالة كده خلصت
    ACTIVE_MESSAGE_SENDER = mock_send_whatsapp_message
# --- نهاية استيراد دالة الإرسال ---

# routes/webhook.py

# ... (import بتاع ACTIVE_MESSAGE_SENDER) ...

# --- استيراد الـ helper functions و openai_logic ---
try:
    from ..utils.helpers import ( # <--- التعديل هنا: ضيفنا نقطتين
        store_user_info, get_user_info, get_user_language,
        get_reply_from_json, get_static_reply,
        add_to_conversation_history, load_conversation_history
    )
    from ..utils.openai_logic import generate_openai_response # <--- التعديل هنا: ضيفنا نقطتين
    
    _logger_init_helpers = current_app.logger if current_app else logging.getLogger(__name__) # استخدم لوجر آمن
    _logger_init_helpers.info("Successfully imported helper functions and openai_logic using relative import.")

except ImportError as e:
    _logger_init_error = current_app.logger if current_app else logging.getLogger(__name__)
    _logger_init_error.critical(f"CRITICAL RELATIVE IMPORT ERROR: Could not import from '..utils.*'. Bot may not function. Error: {e}")
    # مهم جداً: لو الـ imports دي فشلت، الـ app مينفعش يشتغل صح.
    # الأفضل إننا نوقف الـ app هنا عشان المشكلة متكملش.
    raise RuntimeError(f"Failed to import critical utils (relative import): {e}") from e
# --- نهاية استيراد الـ helper functions ---

# تعريف الـ Blueprint
webhook_bp = Blueprint('webhook_bp', __name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "fallback_token_123_webhook")
if VERIFY_TOKEN == "fallback_token_123_webhook":
    _logger_init.warning("SECURITY WARNING: WHATSAPP_VERIFY_TOKEN is using a fallback value. Set it in .env or environment variables.")


@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook_handler():
    # استخدم logger الـ app الرئيسي دائمًا داخل الـ request context
    logger = current_app.logger # logger هنا هو بتاع الـ app الرئيسي

    # --- معالجة طلب GET (لـ Webhook Verification) ---
    if request.method == 'GET':
        hub_mode = request.args.get('hub.mode')
        hub_token = request.args.get('hub.verify_token')
        hub_challenge = request.args.get('hub.challenge')

        logger.info(f"WEBHOOK.PY: GET request received. Mode: {hub_mode}, Token Sent: {hub_token}")
        if hub_mode == 'subscribe' and hub_token == VERIFY_TOKEN:
            logger.info(f"WEBHOOK.PY: GET verification successful. Challenge: {hub_challenge}")
            return hub_challenge, 200
        else:
            logger.warning(f"WEBHOOK.PY: GET verification FAILED. Expected Token: {VERIFY_TOKEN}")
            return 'Forbidden - Verification Failed', 403

    # --- معالجة طلب POST (لاستقبال رسائل الواتساب) ---
    if request.method == 'POST':
        data = request.get_json()
        logger.info(f"WEBHOOK.PY: Received POST data on /webhook: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # تأكد إن ACTIVE_MESSAGE_SENDER متعرف صح
        if ACTIVE_MESSAGE_SENDER is None:
            logger.critical("WEBHOOK.PY: CRITICAL - ACTIVE_MESSAGE_SENDER is None. Cannot send replies.")
            # ممكن ترجع خطأ هنا أو تحاول تعيد تهيئته لو منطقي

        if data and data.get('object') == 'whatsapp_business_account':
            try:
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                if 'messages' not in value:
                    logger.info("WEBHOOK.PY: POST data no 'messages' field. Skipping.")
                    return jsonify({'status': 'no_message_field_in_value'}), 200

                message_object = value.get('messages', [{}])[0]
                
                if message_object.get('type') != 'text':
                    msg_type = message_object.get('type', 'unknown_type')
                    logger.info(f"WEBHOOK.PY: Received non-text message type: {msg_type}. Ignoring.")
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                from_user_id = message_object.get('from')
                msg_body = message_object.get('text', {}).get('body', '').strip()
                
                if not from_user_id or not msg_body:
                    logger.warning("WEBHOOK.PY: POST Missing 'from' or 'msg_body'.")
                    return jsonify({'status': 'missing_user_id_or_message_body'}), 400

                logger.info(f"WEBHOOK.PY: Processing msg from {from_user_id}: '{msg_body}'")
                
                logger.info(f"WEBHOOK.PY: --- Adding USER message to history for {from_user_id} ---")
                add_to_conversation_history(from_user_id, "user", msg_body)

                logger.info(f"WEBHOOK.PY: --- Getting USER data for {from_user_id} BEFORE onboarding ---")
                user_data = get_user_info(from_user_id) # دي هتطبع لوجاتها من helpers.py
                onboarding_step = user_data.get("onboarding_step", "awaiting_language")
                # current_lang هتتحدد بناءً على اختيار المستخدم أو من user_data
                current_lang = user_data.get("language", "en") # لغة افتراضية لو لسه مفيش
                logger.info(f"WEBHOOK.PY: User {from_user_id} - Initial DB onboarding_step: {onboarding_step}, lang: {current_lang}")

                reply_message_key = None
                reply_text_direct = None
                reply_kwargs = {}
                signature_type = "static"

                # 1. === تدفق الـ Onboarding ===
                if onboarding_step != "completed":
                    logger.info(f"WEBHOOK.PY: User {from_user_id} ENTERING onboarding_step: {onboarding_step}")
                    if onboarding_step == "awaiting_language":
                        reply_message_key = "welcome_najdaigent"
                        logger.info(f"WEBHOOK.PY: --- Storing onboarding_step='awaiting_language_selection' for {from_user_id} ---")
                        store_user_info(from_user_id, "onboarding_step", "awaiting_language_selection")
                        # اطبع البيانات بعد التحديث عشان تتأكد
                        logger.info(f"WEBHOOK.PY: User {from_user_id} data AFTER 'awaiting_language_selection' update: {get_user_info(from_user_id)}")
                    
                    elif onboarding_step == "awaiting_language_selection":
                        logger.info(f"WEBHOOK.PY: User {from_user_id} in 'awaiting_language_selection', received msg_body: '{msg_body}'")
                        if msg_body == "1" or "english" in msg_body.lower():
                            current_lang = "en" # حددنا اللغة هنا
                            logger.info(f"WEBHOOK.PY: User {from_user_id} selected English.")
                            logger.info(f"WEBHOOK.PY: --- Storing lang='{current_lang}' FOR {from_user_id} ---")
                            store_user_info(from_user_id, "language", current_lang)
                            logger.info(f"WEBHOOK.PY: --- Storing onboarding_step='awaiting_name' FOR {from_user_id} ---")
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            logger.info(f"WEBHOOK.PY: User {from_user_id} data AFTER lang/step update: {get_user_info(from_user_id)}")
                            confirm_lang_text = get_reply_from_json("language_selected_en", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        elif msg_body == "2" or "عربية" in msg_body or "arabic" in msg_body.lower():
                            current_lang = "ar" # حددنا اللغة هنا
                            logger.info(f"WEBHOOK.PY: User {from_user_id} selected Arabic.")
                            logger.info(f"WEBHOOK.PY: --- Storing lang='{current_lang}' FOR {from_user_id} ---")
                            store_user_info(from_user_id, "language", current_lang)
                            logger.info(f"WEBHOOK.PY: --- Storing onboarding_step='awaiting_name' FOR {from_user_id} ---")
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            logger.info(f"WEBHOOK.PY: User {from_user_id} data AFTER lang/step update: {get_user_info(from_user_id)}")
                            confirm_lang_text = get_reply_from_json("language_selected_ar", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        else:
                            logger.warning(f"WEBHOOK.PY: User {from_user_id} invalid language choice: '{msg_body}'")
                            reply_message_key = "invalid_language_choice"
                            # استخدم current_lang اللي كانت محددة قبل كده أو الافتراضية لو أول مرة
                            lang_for_error_msg = user_data.get("language", "en")
                            error_text = get_reply_from_json(reply_message_key, lang_for_error_msg)
                            welcome_again_text = get_reply_from_json("welcome_najdaigent", lang_for_error_msg) # رسالة الترحيب بنفس اللغة
                            reply_text_direct = f"{error_text}\n\n{welcome_again_text}"
                    
                    elif onboarding_step == "awaiting_name":
                        user_name = msg_body.strip()
                        logger.info(f"WEBHOOK.PY: User {from_user_id} provided name: '{user_name}'. Current lang for reply: {current_lang}")
                        logger.info(f"WEBHOOK.PY: --- Storing name='{user_name}' FOR {from_user_id} ---")
                        store_user_info(from_user_id, "name", user_name)
                        logger.info(f"WEBHOOK.PY: --- Storing onboarding_step='awaiting_service_interest' FOR {from_user_id} ---")
                        store_user_info(from_user_id, "onboarding_step", "awaiting_service_interest")
                        logger.info(f"WEBHOOK.PY: User {from_user_id} data AFTER name/step update: {get_user_info(from_user_id)}")
                        # اللغة للرد لازم تكون اللي المستخدم اختارها
                        reply_lang = get_user_language(from_user_id) # هات اللغة المتخزنة
                        reply_message_key = "ask_service_interest"
                        reply_kwargs = {"name": user_name}
                        current_lang = reply_lang # حدث current_lang عشان الردود والتوقيع
                    
                    elif onboarding_step == "awaiting_service_interest":
                        service_interest = msg_body.strip()
                        logger.info(f"WEBHOOK.PY: User {from_user_id} interested in service: '{service_interest}'. Current lang for reply: {current_lang}")
                        logger.info(f"WEBHOOK.PY: --- Storing service_interest='{service_interest}' FOR {from_user_id} ---")
                        store_user_info(from_user_id, "service_interest", service_interest)
                        logger.info(f"WEBHOOK.PY: --- Storing onboarding_step='completed' FOR {from_user_id} ---")
                        store_user_info(from_user_id, "onboarding_step", "completed")
                        # هات البيانات بعد التحديث عشان الاسم
                        updated_user_data = get_user_info(from_user_id)
                        logger.info(f"WEBHOOK.PY: User {from_user_id} data AFTER service_interest/step (ONBOARDING COMPLETE): {updated_user_data}")
                        user_name = updated_user_data.get("name", "User") # اسم احتياطي
                        reply_lang = updated_user_data.get("language", "en") # اللغة المؤكدة
                        reply_message_key = "onboarding_complete"
                        reply_kwargs = {"name": user_name}
                        current_lang = reply_lang # حدث current_lang
                
                # 2. === التفاعل العادي (بعد اكتمال الـ Onboarding) ===
                else: # onboarding_step == "completed"
                    logger.info(f"WEBHOOK.PY: User {from_user_id} (onboarding completed). Processing regular message.")
                    current_lang = get_user_language(from_user_id) # دي اللغة المؤكدة للمستخدم
                    logger.info(f"WEBHOOK.PY: Confirmed language for user {from_user_id}: {current_lang}")
                    
                    static_answer = get_static_reply(msg_body, current_lang)
                    if static_answer:
                        logger.info(f"WEBHOOK.PY: Static FAQ match found for '{msg_body}' (lang: {current_lang}).")
                        reply_text_direct = static_answer
                        signature_type = "static"
                    else:
                        logger.info(f"WEBHOOK.PY: No static FAQ match. Falling back to OpenAI for '{msg_body}' (lang: {current_lang}).")
                        conversation_hist = load_conversation_history(from_user_id)
                        ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                        reply_text_direct = ai_response
                        signature_type = "openai"

                # --- بناء وإرسال الرد النهائي ---
                final_reply_to_send = ""
                # اللغة للرد لازم تكون current_lang اللي اتحددت صح في كل خطوة
                lang_for_final_reply = current_lang 

                if reply_message_key:
                    final_reply_to_send = get_reply_from_json(reply_message_key, lang_for_final_reply, **reply_kwargs)
                elif reply_text_direct:
                    final_reply_to_send = reply_text_direct
                
                if final_reply_to_send:
                    if signature_type == "openai":
                        final_reply_to_send += get_reply_from_json("signature_openai", lang_for_final_reply)
                    else:
                        final_reply_to_send += get_reply_from_json("signature_static", lang_for_final_reply)
                    
                    logger.info(f"WEBHOOK.PY: Final reply to send to {from_user_id} (lang: {lang_for_final_reply}, type: {signature_type}): '{final_reply_to_send[:300]}...'")
                    
                    logger.info(f"WEBHOOK.PY: --- Attempting to send reply to {from_user_id} via ACTIVE_MESSAGE_SENDER ---")
                    # استخدم ACTIVE_MESSAGE_SENDER لإرسال الرسالة
                    message_sent_successfully = ACTIVE_MESSAGE_SENDER(from_user_id, final_reply_to_send)
                    
                    if message_sent_successfully: # افترض إن الدالة الحقيقية بترجع True عند النجاح
                        logger.info(f"WEBHOOK.PY: Reply INITIATED successfully for {from_user_id}.")
                        logger.info(f"WEBHOOK.PY: --- Adding ASSISTANT message to history for {from_user_id} ---")
                        add_to_conversation_history(from_user_id, "assistant", final_reply_to_send)
                    else:
                        logger.error(f"WEBHOOK.PY: FAILED to initiate sending reply to {from_user_id}. Check logs from ACTIVE_MESSAGE_SENDER.")
                else:
                    logger.warning(f"WEBHOOK.PY: No reply generated for user {from_user_id} and message: '{msg_body}'")

            except Exception as e:
                logger.error(f"WEBHOOK.PY: Unhandled error in webhook POST processing: {e}", exc_info=True)
                try:
                    error_lang_user_id = locals().get('from_user_id')
                    error_lang = 'en'
                    if error_lang_user_id:
                       user_lang_data_for_error = get_user_info(error_lang_user_id) # ممكن تعمل لوجاتها من helpers
                       if user_lang_data_for_error and user_lang_data_for_error.get("language"):
                           error_lang = user_lang_data_for_error.get("language")
                    
                    error_msg_text = get_reply_from_json("error_occurred", error_lang) # مفتاح لرسالة خطأ عامة
                    
                    if error_lang_user_id and error_msg_text and ACTIVE_MESSAGE_SENDER:
                         logger.info(f"WEBHOOK.PY: Attempting to send generic error message to {error_lang_user_id} in {error_lang}.")
                         ACTIVE_MESSAGE_SENDER(error_lang_user_id, error_msg_text)
                except Exception as e_send_error:
                    logger.error(f"WEBHOOK.PY: Failed to send generic error message to user after an exception: {e_send_error}", exc_info=True)
                
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        logger.info("WEBHOOK.PY: POST received, but 'object' not 'whatsapp_business_account'.")
        return jsonify({'status': 'received_ok_not_processed'}), 200

    logger.warning(f"WEBHOOK.PY: Received request with unsupported method: {request.method}")
    return jsonify({'status': 'unsupported_http_method'}), 405
