import os
import json
import openai
import logging
from flask import Flask, request, Response, jsonify, render_template
from dotenv import load_dotenv
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse
from routes.webhook import webhook_bp

# --- Start of App Setup ---
app = Flask(__name__)
app.register_blueprint(webhook_bp)

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load Environment Variables ---
try:
    load_dotenv()
    logging.info("✅ Environment variables loaded successfully.")
except Exception as e:
    logging.warning(f"⚠️ Failed to load .env file: {e}")

# --- OpenAI Setup ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.critical("!!! CRITICAL WARNING: OPENAI_API_KEY not found in environment variables. !!!")
    OPENAI_API_KEY = "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV"

client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized successfully.")
    except Exception as e:
        logging.critical(f"!!! CRITICAL ERROR initializing OpenAI client: {e} !!!")
else:
    logging.warning("!!! OpenAI client NOT initialized due to missing or placeholder API key. !!!")

# --- Static Endpoints ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/customer/<phone_number>")
def get_customer_info_route(phone_number):
    from utils.helpers import load_customer_data
    customer_data = load_customer_data().get(phone_number.replace("whatsapp:", ""))
    if customer_data:
        return jsonify(customer_data)
    return jsonify({"error": "Customer not found"}), 404

@app.route("/history/<phone_number>")
def get_history_route(phone_number):
    from utils.helpers import load_conversation_history
    history = load_conversation_history(phone_number.replace("whatsapp:", ""))
    if history:
        return jsonify(history)
    return jsonify({"message": "No conversation history for this number."}), 404

# --- Run Server ---
if __name__ == "__main__":
    from utils.helpers import save_customer_data, CUSTOMER_DATA_FILE
    if not os.path.exists(CUSTOMER_DATA_FILE):
        save_customer_data({})

    critical_errors = False
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_FALLBACK_OPENAI_KEY_IF_NO_ENV":
        logging.critical("!!! CRITICAL: OPENAI_API_KEY is not set. Bot WILL NOT WORK. !!!")
        critical_errors = True

    if critical_errors:
        logging.critical("!!! Exiting due to critical configuration errors. !!!")
        exit(1)

    logging.info("Bot (Web & WhatsApp) is initializing...")
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
