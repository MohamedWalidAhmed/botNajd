import os
import json
import logging
from flask import Blueprint, request, jsonify

# --- Initialize Blueprint and Logger ---
webhook_bp = Blueprint('webhook_bp', __name__)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
# VERIFY_TOKEN is now read directly from environment variables set on the host
VERIFY_TOKEN_FROM_ENV = os.getenv("VERIFY_TOKEN") # Changed from META_VERIFY_TOKEN

if not VERIFY_TOKEN_FROM_ENV:
    # This fallback is more for local testing if .env is not used or var is missing
    # In production, the app should ideally fail to start if critical env vars are missing (handled in app.py)
    logger.critical("!!! CRITICAL: VERIFY_TOKEN is not set in environment variables. Webhook verification will fail! Using a default insecure token for local dev if needed. !!!")
    # For safety, if VERIFY_TOKEN_FROM_ENV is None, the verification logic will fail anyway.
    # You might choose to assign a default here for local testing ONLY if you absolutely need to,
    # but it's better to ensure it's set.
    # VERIFY_TOKEN_FROM_ENV = "FALLBACK_LOCAL_TOKEN_ONLY_IF_ABSOLUTELY_NECESSARY"


@webhook_bp.route("/webhook", methods=['GET', 'POST'])
def webhook():
    """Handles incoming webhook events from Meta (WhatsApp)."""
    if request.method == 'GET':
        hub_mode = request.args.get("hub.mode")
        hub_challenge = request.args.get("hub.challenge")
        hub_verify_token = request.args.get("hub.verify_token")

        # Check if VERIFY_TOKEN_FROM_ENV is actually set before comparing
        if VERIFY_TOKEN_FROM_ENV and hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN_FROM_ENV:
            logger.info("✅ Webhook verified successfully!")
            return hub_challenge, 200
        else:
            expected_token_log = VERIFY_TOKEN_FROM_ENV if VERIFY_TOKEN_FROM_ENV else "NOT SET IN ENV"
            logger.warning(f"⚠️ Webhook verification failed. Mode: {hub_mode}, Received Token: {hub_verify_token} (Expected: {expected_token_log})")
            return "Verification token mismatch, invalid mode, or VERIFY_TOKEN not configured on server.", 403

    elif request.method == 'POST':
        data = request.get_json()
        logger.info(f"⬇️ Received WhatsApp event from Meta: {json.dumps(data, indent=2)}")

        try:
            # Ensure these utils exist and have the required functions
            from utils.openai_logic import get_openai_reply_and_extract_booking_info
            from utils.send_meta import send_meta_whatsapp_message

            if data.get("object") == "whatsapp_business_account":
                entry = data.get("entry", [])
                if not entry:
                    logger.warning("No 'entry' in webhook data.")
                    return jsonify({"status": "error", "message": "No entry in data"}), 400 # Or 200 if Meta prefers

                changes = entry[0].get("changes", [])
                if not changes:
                    logger.warning("No 'changes' in webhook entry.")
                    return jsonify({"status": "error", "message": "No changes in entry"}), 400 # Or 200

                value = changes[0].get("value", {})
                messages = value.get("messages", [])

                if messages:
                    message = messages[0]
                    if message.get("type") == "text":
                        incoming_msg = message["text"]["body"]
                        sender_wa_id = message["from"]
                        logger.info(f"💬 Message from {sender_wa_id}: {incoming_msg}")

                        ai_reply_text, booking_data = get_openai_reply_and_extract_booking_info(incoming_msg, sender_wa_id)

                        if booking_data:
                            logger.info(f"ℹ️ Booking data extracted: {booking_data}")

                        send_meta_whatsapp_message(sender_wa_id, ai_reply_text)
                        logger.info(f"⬆️ Sent AI reply to {sender_wa_id}: {ai_reply_text}")
                    else:
                        logger.info(f"Received non-text message type: {message.get('type')} from {message.get('from')}. Ignoring.")
                elif "statuses" in value:
                    logger.info(f"Received a status update: {json.dumps(value.get('statuses'), indent=2)}")
                else:
                    logger.info("Received webhook data without messages or known statuses. Value: %s", value)
            else:
                logger.warning(f"Received webhook data for unhandled object type: {data.get('object')}")

        except ImportError as ie:
            logger.critical(f"!!! CRITICAL ERROR: Failed to import utility functions: {ie}. Check utils directory. !!!")
            return jsonify({"status": "error", "message": "Internal server configuration error"}), 500
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)

        return jsonify({"status": "ok"}), 200 # Always return 200 OK to Meta quickly
    
    return "Method Not Allowed", 405
