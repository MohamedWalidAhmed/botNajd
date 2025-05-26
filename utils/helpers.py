import json
import os
from typing import Dict, Any, Optional, List
from thefuzz import fuzz # For fuzzy matching

CONFIG_DATA_PATH = "config_data" # Assumes config_data is at the same level as the script running this or accessible via this path
CUSTOMERS_PATH = "customers"   # Assumes customers is at the same level
REPLIES_FILE = os.path.join(CONFIG_DATA_PATH, "replies.json")
CUSTOMER_DATA_FILE = os.path.join(CUSTOMERS_PATH, "customer_data.json")
FAQ_DATA_FILE = os.path.join(CONFIG_DATA_PATH, "faq_data.json") # New FAQ file

# --- JSON Data Handling ---
def _load_json_data(file_path: str) -> Dict:
    try:
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {} # Return empty dict if file doesn't exist, it will be created on save
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in {file_path}. Returning empty data.")
        return {}

def _save_json_data(data: Dict, file_path: str):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Customer Information ---
def store_user_info(phone_number: str, key: str, value: Any):
    """Stores or updates a specific piece of information for a user."""
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    if phone_number not in all_customers:
        all_customers[phone_number] = {"onboarding_step": "awaiting_language"} # Default onboarding step
    all_customers[phone_number][key] = value
    _save_json_data(all_customers, CUSTOMER_DATA_FILE)

def get_user_info(phone_number: str) -> Dict[str, Any]:
    """Retrieves all stored information for a user."""
    all_customers = _load_json_data(CUSTOMER_DATA_FILE)
    return all_customers.get(phone_number, {"onboarding_step": "awaiting_language"})

def get_user_language(phone_number: str) -> str:
    """
    Retrieves the user's preferred language. Defaults to 'en' if not set,
    though the onboarding flow should set this.
    """
    user_data = get_user_info(phone_number)
    return user_data.get("language", "en")

# --- Reply Management ---
def get_reply_from_json(reply_key: str, lang: str, **kwargs) -> str:
    """
    Fetches a reply from replies.json based on key and language.
    kwargs are used for formatting placeholders in the reply string.
    """
    replies_content = _load_json_data(REPLIES_FILE)
    message_template = replies_content.get(reply_key, {}).get(lang)

    if not message_template:
        # Fallback to English if specific language or key is missing
        message_template = replies_content.get(reply_key, {}).get("en", f"Error: Reply key '{reply_key}' not found for lang '{lang}'.")
        print(f"Warning: Reply key '{reply_key}' not found for lang '{lang}'. Fallback to EN or error msg.")
    
    try:
        return message_template.format(**kwargs)
    except KeyError as e:
        print(f"Warning: Missing placeholder {e} for reply key '{reply_key}' (lang: {lang}).")
        return message_template # Return unformatted if placeholder is missing

# --- Smart Static Reply (FAQ) ---
def get_static_reply(user_message: str, lang: str, threshold: int = 75) -> Optional[str]:
    """
    Checks user message against FAQ keywords using fuzzy matching.
    Returns the answer if a match is found above the threshold, otherwise None.
    """
    faq_content = _load_json_data(FAQ_DATA_FILE)
    user_message_lower = user_message.lower().strip()

    best_match_score = 0
    best_answer = None

    for _, faq_item in faq_content.items():
        keywords_key = f"keywords_{lang}"
        answer_key = f"answer_{lang}"

        if keywords_key not in faq_item or answer_key not in faq_item:
            continue

        keywords: List[str] = faq_item[keywords_key]
        
        for keyword in keywords:
            # Using token_set_ratio for better partial matching
            similarity_score = fuzz.token_set_ratio(user_message_lower, keyword.lower())
            if similarity_score >= threshold and similarity_score > best_match_score:
                best_match_score = similarity_score
                best_answer = faq_item[answer_key]
                
    return best_answer

# --- Conversation History ---
# Assuming your existing conversation history functions are here.
# If not, you'll need to add/adapt them. For example:
CONVERSATION_HISTORY_PATH = "conversation_hist" 

def load_conversation_history(user_id: str) -> List[Dict[str, str]]:
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{user_id}.json")
    # Ensure parent directory exists when trying to load (though it's more for saving)
    # os.makedirs(os.path.dirname(file_path), exist_ok=True) # Not strictly needed for load but good practice
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_conversation_history(user_id: str, history: List[Dict[str, str]]):
    os.makedirs(CONVERSATION_HISTORY_PATH, exist_ok=True)
    file_path = os.path.join(CONVERSATION_HISTORY_PATH, f"{user_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def add_to_conversation_history(user_id: str, role: str, content: str, max_history_length: int = 20):
    history = load_conversation_history(user_id)
    history.append({"role": role, "content": content})
    # Keep history to a reasonable length
    history = history[-max_history_length:] 
    save_conversation_history(user_id, history)

# Note: `detect_language()` function requested:
# For this bot, language is explicitly chosen by the user during onboarding.
# A true language detection for arbitrary input is more complex (e.g., using 'langdetect' library).
# Given the flow, an explicit choice is more robust for the "Basic Package".
# If a message comes before language selection, we default to the welcome message which offers the choice.
