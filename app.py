import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv # Still useful for local development

# --- Import Blueprints ---
from routes.webhook import webhook_bp

# --- Start of App Setup ---
app = Flask(__name__)

# --- Register Blueprints ---
app.register_blueprint(webhook_bp)

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("app.log") # Uncomment to log to a file
    ]
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables (primarily for local development) ---
# On a hosting platform, these are usually set in the environment directly.
try:
    if os.path.exists(".env"): # Only load if .env file exists
        load_dotenv()
        logger.info("✅ .env file found and loaded (for local development).")
    else:
        logger.info("ℹ️ No .env file found, assuming environment variables are set externally (e.g., on host).")
except Exception as e:
    logger.warning(f"⚠️ Failed to load .env file: {e}")

# --- Check for Essential Environment Variables ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VERIFY_TOKEN_FROM_ENV = os.getenv("VERIFY_TOKEN") # Changed from META_VERIFY_TOKEN
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN") # For send_meta.py
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") # For send_meta.py


if not OPENAI_API_KEY:
    logger.critical("!!! CRITICAL WARNING: OPENAI_API_KEY not found. OpenAI features will FAIL. !!!")
if not VERIFY_TOKEN_FROM_ENV:
    logger.critical("!!! CRITICAL WARNING: VERIFY_TOKEN not found. Webhook verification will FAIL. !!!")
if not PAGE_ACCESS_TOKEN:
    logger.critical("!!! CRITICAL WARNING: PAGE_ACCESS_TOKEN not found. Sending messages via Meta will FAIL. !!!")
if not WHATSAPP_BUSINESS_ACCOUNT_ID:
    logger.critical("!!! CRITICAL WARNING: WHATSAPP_BUSINESS_ACCOUNT_ID not found. Sending messages via Meta will FAIL. !!!")


# --- Static Endpoints (for testing or basic info) ---
@app.route("/", methods=["GET"])
def index():
    """Serves the main page."""
    return render_template("index.html")

@app.route("/customer/<phone_number>")
def get_customer_info_route(phone_number):
    """Retrieves customer data."""
    try:
        from utils.helpers import load_customer_data
        customer_data = load_customer_data().get(phone_number.replace("whatsapp:", ""))
        if customer_data:
            return jsonify(customer_data)
        return jsonify({"error": "Customer not found"}), 404
    except ImportError:
        logger.error("Failed to import load_customer_data from utils.helpers.")
        return jsonify({"error": "Server configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in /customer/{phone_number}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/history/<phone_number>")
def get_history_route(phone_number):
    """Retrieves conversation history."""
    try:
        from utils.helpers import load_conversation_history
        history = load_conversation_history(phone_number.replace("whatsapp:", ""))
        if history:
            return jsonify(history)
        return jsonify({"message": "No conversation history for this number."}), 404
    except ImportError:
        logger.error("Failed to import load_conversation_history from utils.helpers.")
        return jsonify({"error": "Server configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in /history/{phone_number}: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- Run Server ---
if __name__ == "__main__":
    try:
        from utils.helpers import save_customer_data, CUSTOMER_DATA_FILE
        if not os.path.exists(CUSTOMER_DATA_FILE):
            logger.info(f"Customer data file not found at {CUSTOMER_DATA_FILE}, creating an empty one.")
            save_customer_data({})
    except ImportError:
        logger.warning("Could not import or run initial data setup from utils.helpers.")
    except Exception as e:
        logger.error(f"Error during initial data setup: {e}")

    critical_errors = False
    if not OPENAI_API_KEY:
        critical_errors = True
    if not VERIFY_TOKEN_FROM_ENV:
        critical_errors = True
    if not PAGE_ACCESS_TOKEN:
        critical_errors = True
    if not WHATSAPP_BUSINESS_ACCOUNT_ID:
        critical_errors = True

    if critical_errors:
        logger.critical("!!! Exiting due to critical configuration errors. Please check environment variables. !!!")
        exit(1)

    port = int(os.getenv("PORT", 5000))
    # Read FLASK_DEBUG from environment; default to "False" if not set, then convert to boolean
    flask_debug_str = os.getenv("FLASK_DEBUG", "False")
    debug_mode = flask_debug_str.lower() in ['true', '1', 't']

    logger.info(f"🚀 Bot (Web & WhatsApp) is initializing on host 0.0.0.0 and port {port} (Debug: {debug_mode})...")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
