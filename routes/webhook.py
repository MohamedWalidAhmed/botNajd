from flask import Blueprint, request, jsonify, current_app
import os
import json
# لا تحتاج لاستيراد logging هنا طالما ستستخدم current_app.logger

# --- استيراد الدالة الحقيقية لإرسال الرسائل من utils/send_meta.py ---
try:
    # هذا المسار يفترض أن utils فولدر شقيق لـ routes
    # وأن app.py (أو نقطة تشغيل المشروع) في مستوى يسمح بهذا النوع من الاستيراد النسبي
    from ..utils.send_meta import send_whatsapp_message_real
except ImportError as e:
    # في حالة فشل الاستيراد، استخدم دالة وهمية مؤقتة مع تسجيل خطأ فادح.
    # هذا غير مثالي للإنتاج، يجب أن يكون الاستيراد ناجحًا.
    if current_app: # current_app قد لا يكون متاحًا هنا إذا فشل الاستيراد قبل تهيئة الـ app
        current_app.logger.critical(f"CRITICAL IMPORT ERROR: Could not import 'send_whatsapp_message_real' from 'utils.send_meta'. Falling back to mock. Error: {e}")
    else:
        print(f"CRITICAL IMPORT ERROR (pre-app context): Could not import 'send_whatsapp_message_real'. Error: {e}")
    
    def send_whatsapp_message_real(recipient_wa_id: str, message_text: str) -> bool:
        log_target = current_app.logger if current_app else print
        log_target(
            f"FALLBACK MOCK SEND to {recipient_wa_id}: '{message_text}' - "
            "REAL SEND FUNCTION ('send_whatsapp_message_real') FAILED TO IMPORT."
        )
        return False # تشير إلى فشل الإرسال
# --- نهاية استيراد دالة الإرسال ---


# --- استيراد دوال المساعدة من utils/helpers.py و utils/openai_logic.py ---
try:
    from ..utils.helpers import (
        store_user_info, get_user_info, get_user_language,
        get_reply_from_json, get_static_reply,
        add_to_conversation_history, load_conversation_history
    )
    from ..utils.openai_logic import generate_openai_response
except ImportError as e:
    if current_app:
        current_app.logger.critical(f"CRITICAL IMPORT ERROR: Could not import helper functions from 'utils'. Error: {e}")
    else:
        print(f"CRITICAL IMPORT ERROR (pre-app context): Could not import helper functions. Error: {e}")
    # يجب أن تقرر كيف ستتعامل مع هذا الخطأ الفادح.
    # إيقاف التطبيق قد يكون مناسبًا إذا كانت هذه الدوال حيوية.
    # For now, we'll let it proceed, but it will likely cause runtime errors later.
# --- نهاية استيراد دوال المساعدة ---


# تعريف الـ Blueprint
webhook_bp = Blueprint('webhook_bp', __name__)

# تحميل Verify Token من متغيرات البيئة
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_fallback_verify_token_if_not_set")
if VERIFY_TOKEN == "your_fallback_verify_token_if_not_set":
    # لا تستخدم current_app.logger هنا لأنه قد لا يكون متاحًا بعد
    print("WARNING: WHATSAPP_VERIFY_TOKEN is using a fallback value. Please set it in environment variables.")


@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook_handler():
    # استخدم logger الـ app الرئيسي دائمًا داخل الـ request context
    logger = current_app.logger

    # --- معالجة طلب GET (لـ Webhook Verification) ---
    if request.method == 'GET':
        hub_mode = request.args.get('hub.mode')
        hub_token = request.args.get('hub.verify_token')
        hub_challenge = request.args.get('hub.challenge')

        if hub_mode == 'subscribe' and hub_token == VERIFY_TOKEN:
            logger.info(f"Webhook GET verification successful. Challenge: {hub_challenge}")
            return hub_challenge, 200
        else:
            logger.warning(
                f"Webhook GET verification failed. Mode: {hub_mode}, Token Sent: {hub_token}, Expected Token: {VERIFY_TOKEN}"
            )
            return 'Forbidden - Verification Failed', 403

    # --- معالجة طلب POST (لاستقبال رسائل الواتساب) ---
    if request.method == 'POST':
        data = request.get_json()
        # تسجيل البيانات المستلمة بالكامل (مع الحرص على عدم تسجيل معلومات حساسة لو كانت موجودة)
        logger.info(f"Received POST data on /webhook: {json.dumps(data, indent=2, ensure_ascii=False)}")

        if data and data.get('object') == 'whatsapp_business_account':
            try:
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                if 'messages' not in value:
                    logger.info("Webhook POST data does not contain 'messages' field. Skipping processing.")
                    return jsonify({'status': 'no_message_field_in_value'}), 200 # أو 204 No Content

                message_object = value.get('messages', [{}])[0]
                
                if message_object.get('type') != 'text':
                    logger.info(f"Received non-text message type: {message_object.get('type')}. Ignoring.")
                    return jsonify({'status': 'ignored_non_text_message'}), 200

                from_user_id = message_object.get('from') # رقم هاتف المستخدم
                msg_body = message_object.get('text', {}).get('body', '').strip()
                
                if not from_user_id or not msg_body:
                    logger.warning("Webhook POST: Missing 'from' (user ID) or 'msg_body' (text content) in message object.")
                    return jsonify({'status': 'missing_user_id_or_message_body'}), 400 # Bad Request

                logger.info(f"Processing incoming text message from {from_user_id}: '{msg_body}'")
                
                # إضافة رسالة المستخدم إلى سجل المحادثة
                add_to_conversation_history(from_user_id, "user", msg_body)

                # الحصول على معلومات المستخدم وحالة الـ Onboarding
                user_data = get_user_info(from_user_id)
                onboarding_step = user_data.get("onboarding_step", "awaiting_language")
                current_lang = user_data.get("language", "en") # الافتراضي هو الإنجليزية

                reply_message_key = None # مفتاح الرسالة من replies.json
                reply_text_direct = None # نص مباشر للرد (من FAQ أو OpenAI)
                reply_kwargs = {}      # متغيرات لتمريرها لدالة format
                signature_type = "static" # نوع التوقيع الافتراضي

                # 1. === تدفق الـ Onboarding ===
                if onboarding_step != "completed":
                    logger.info(f"User {from_user_id} is in onboarding_step: {onboarding_step}")
                    if onboarding_step == "awaiting_language":
                        reply_message_key = "welcome_najdaigent" # رسالة الترحيب واختيار اللغة
                        store_user_info(from_user_id, "onboarding_step", "awaiting_language_selection")
                    
                    elif onboarding_step == "awaiting_language_selection":
                        if msg_body == "1" or "english" in msg_body.lower(): # اختيار الإنجليزية
                            current_lang = "en"
                            store_user_info(from_user_id, "language", current_lang)
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            confirm_lang_text = get_reply_from_json("language_selected_en", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        elif msg_body == "2" or "عربية" in msg_body or "arabic" in msg_body.lower(): # اختيار العربية
                            current_lang = "ar"
                            store_user_info(from_user_id, "language", current_lang)
                            store_user_info(from_user_id, "onboarding_step", "awaiting_name")
                            confirm_lang_text = get_reply_from_json("language_selected_ar", current_lang)
                            ask_name_text = get_reply_from_json("ask_name", current_lang)
                            reply_text_direct = f"{confirm_lang_text}\n\n{ask_name_text}"
                        else: # اختيار لغة غير صالح
                            reply_message_key = "invalid_language_choice"
                            # أعد إرسال رسالة اختيار اللغة مرة أخرى بلغة افتراضية أو آخر لغة تم تحديدها
                            welcome_again_lang = user_data.get("language", "en") # استخدم لغة المستخدم إن وجدت
                            welcome_again = get_reply_from_json("welcome_najdaigent", welcome_again_lang)
                            error_reply_lang = current_lang if user_data.get("language") else "en"
                            reply_text_direct = get_reply_from_json(reply_message_key, error_reply_lang) + f"\n\n{welcome_again}"
                    
                    elif onboarding_step == "awaiting_name": # انتظار اسم المستخدم
                        user_name = msg_body.strip() # تنظيف الاسم من مسافات زائدة
                        store_user_info(from_user_id, "name", user_name)
                        store_user_info(from_user_id, "onboarding_step", "awaiting_service_interest")
                        reply_message_key = "ask_service_interest"
                        reply_kwargs = {"name": user_name}
                    
                    elif onboarding_step == "awaiting_service_interest": # انتظار الخدمة المهتم بها
                        service_interest = msg_body.strip()
                        store_user_info(from_user_id, "service_interest", service_interest)
                        store_user_info(from_user_id, "onboarding_step", "completed") # اكتمل الـ Onboarding
                        user_name = user_data.get("name", "User") # اسم احتياطي
                        reply_message_key = "onboarding_complete"
                        reply_kwargs = {"name": user_name}
                
                # 2. === التفاعل العادي (بعد اكتمال الـ Onboarding) ===
                else:
                    logger.info(f"User {from_user_id} (onboarding completed). Processing regular message.")
                    current_lang = get_user_language(from_user_id) # احصل على لغة المستخدم المؤكدة

                    # 2.1 التحقق من الأسئلة الشائعة (FAQ)
                    static_answer = get_static_reply(msg_body, current_lang)
                    if static_answer:
                        logger.info(f"Static FAQ match found for '{msg_body}' (lang: {current_lang}).")
                        reply_text_direct = static_answer
                        signature_type = "static"
                    else:
                        # 2.2 إذا لم يوجد رد في الـ FAQ، استخدم OpenAI
                        logger.info(f"No static FAQ match. Falling back to OpenAI for '{msg_body}' (lang: {current_lang}).")
                        
                        # (اختياري) إرسال رسالة "جارٍ التفكير..."
                        # ack_msg = get_reply_from_json("openai_fallback_acknowledge", current_lang)
                        # send_whatsapp_message_real(from_user_id, ack_msg) # استخدم الدالة الحقيقية

                        conversation_hist = load_conversation_history(from_user_id)
                        ai_response = generate_openai_response(from_user_id, msg_body, current_lang, conversation_hist)
                        reply_text_direct = ai_response
                        signature_type = "openai"

                # --- بناء وإرسال الرد النهائي ---
                final_reply_to_send = ""
                if reply_message_key: # إذا كان الرد من replies.json
                    final_reply_to_send = get_reply_from_json(reply_message_key, current_lang, **reply_kwargs)
                elif reply_text_direct: # إذا كان الرد مباشر (FAQ أو OpenAI)
                    final_reply_to_send = reply_text_direct
                
                if final_reply_to_send:
                    # إضافة التوقيع المناسب
                    if signature_type == "openai":
                        final_reply_to_send += get_reply_from_json("signature_openai", current_lang)
                    else: # static, onboarding
                        final_reply_to_send += get_reply_from_json("signature_static", current_lang)
                    
                    # إرسال الرسالة باستخدام الدالة الحقيقية
                    message_sent_successfully = send_whatsapp_message_real(from_user_id, final_reply_to_send)
                    
                    if message_sent_successfully:
                        logger.info(f"Successfully initiated sending of reply to {from_user_id}.")
                        # إضافة رد البوت إلى سجل المحادثة فقط إذا تم الإرسال بنجاح (أو محاولة الإرسال)
                        add_to_conversation_history(from_user_id, "assistant", final_reply_to_send)
                    else:
                        logger.error(
                            f"Failed to send reply to {from_user_id}. "
                            "Check logs from 'send_whatsapp_message_real' for details."
                        )
                        # قد تقرر هنا عدم إضافة الرد الفاشل إلى الهيستوري، أو إضافته بعلامة خاصة
                else:
                    logger.warning(f"No reply generated for user {from_user_id} and message: '{msg_body}'")

            except Exception as e:
                logger.error(f"Unhandled error processing webhook POST data: {e}", exc_info=True)
                # محاولة إرسال رسالة خطأ عامة للمستخدم إذا أمكن
                try:
                    # حاول تحديد لغة المستخدم لإرسال رسالة الخطأ
                    error_lang_user_id = locals().get('from_user_id') # احصل على from_user_id إن وجد
                    error_lang = get_user_language(error_lang_user_id) if error_lang_user_id else 'en'
                    error_msg_reply = get_reply_from_json("error_occurred", error_lang)
                    if error_lang_user_id: # فقط إذا كان لدينا رقم المستخدم
                         send_whatsapp_message_real(error_lang_user_id, error_msg_reply)
                except Exception as e_send_error:
                    logger.error(f"Failed to send generic error message to user after an exception: {e_send_error}")
                
                # مهم جدًا أن ترجع 500 Internal Server Error إذا حدث خطأ غير معالج
                return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500
        
        # إذا لم يكن الكائن 'whatsapp_business_account'
        logger.info("Webhook POST data received, but 'object' is not 'whatsapp_business_account'.")
        return jsonify({'status': 'received_ok_not_whatsapp_event'}), 200

    # إذا كانت الـ method غير GET أو POST
    logger.warning(f"Received request with unsupported method: {request.method}")
    return jsonify({'status': 'unsupported_http_method'}), 405 # Method Not Allowed
