from flask import Blueprint, request, jsonify
import json
import logging
from .utils import get_openai_reply_and_extract_booking_info, send_meta_whatsapp_message

webhook_bp = Blueprint('webhook_bp', __name__)

VERIFY_TOKEN = "N@jj@9ent2030"  # أو import من config

@webhook_bp.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.mode") == "subscribe" and \
           request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        else:
            return "Verification failed", 403

    elif request.method == 'POST':
        data = request.get_json()
        logging.info(f"Received WhatsApp event from Meta: {json.dumps(data, indent=2)}")

        try:
            if data.get("object") == "whatsapp_business_account":
                changes = data.get("entry", [])[0].get("changes", [])
                if changes:
                    value = changes[0].get("value", {})
                    messages = value.get("messages", [])
                    if messages:
                        message = messages[0]
                        if message.get("type") == "text":
                            incoming_msg = message["text"]["body"]
                            sender_wa_id = message["from"]

                            ai_reply_text, booking_data = get_openai_reply_and_extract_booking_info(incoming_msg, sender_wa_id)
                            send_meta_whatsapp_message(sender_wa_id, ai_reply_text)
        except Exception as e:
            logging.error(f"Error processing webhook: {e}")

        return jsonify({"status": "ok"}), 200
