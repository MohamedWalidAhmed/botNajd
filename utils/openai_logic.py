import openai
import os
# from .helpers import load_conversation_history, add_to_conversation_history # If managed here

# Ensure API key is set (preferably as an environment variable)
# openai.api_key = os.getenv("OPENAI_API_KEY")
# if not openai.api_key:
#    print("Critical: OPENAI_API_KEY environment variable not set.")

# Assuming you have these files or similar content for context
def get_system_prompt_content() -> str:
    try:
        with open(os.path.join("config_data", "system_prompt.txt"), 'r', encoding='utf-8') as f:
            # Added NajdAIgent identity to system prompt
            base_prompt = f.read().strip()
            return f"{base_prompt} You are NajdAIgent, a helpful, professional, and confident AI assistant from a Saudi AI company aligned with Vision 2030. Respond in a polished and structured manner."
    except FileNotFoundError:
        return "You are NajdAIgent, a helpful, professional, and confident AI assistant from a Saudi AI company aligned with Vision 2030. Respond in a polished and structured manner."

def get_reference_data_content() -> str:
    try:
        with open(os.path.join("config_data", "reference_data.txt"), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def generate_openai_response(user_id: str, user_message: str, lang: str, conversation_history: list) -> str:
    """
    Generates a response using OpenAI API, incorporating conversation history and language.
    The decision to call this (i.e., no static FAQ match) is made in webhook.py.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not configured.")
        return "I am currently unable to process this request due to a configuration issue." if lang == "en" else "أنا غير قادر حاليًا على معالجة هذا الطلب بسبب مشكلة في الإعدادات."

    openai.api_key = os.getenv("OPENAI_API_KEY") # Ensure it's set for each call or globally

    system_prompt = get_system_prompt_content()
    if lang == "ar":
        system_prompt += " Please respond in Arabic."
    else:
        system_prompt += " Please respond in English."

    messages = [{"role": "system", "content": system_prompt}]
    
    reference_text = get_reference_data_content()
    if reference_text:
        messages.append({"role": "system", "content": f"Reference Information: {reference_text}"})

    # Add existing conversation history (already loaded and passed from webhook.py)
    for entry in conversation_history:
        messages.append(entry)
    
    # Add the current user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"), # Use your preferred model
            messages=messages,
            temperature=0.7, # Adjust as needed
            max_tokens=300   # Adjust as needed
        )
        ai_response = response.choices[0].message.content.strip()
    except openai.error.OpenAIError as e:
        print(f"OpenAI API Error for user {user_id}: {e}")
        ai_response = "I encountered an issue while trying to generate a response. Please try again."
        if lang == "ar":
            ai_response = "واجهت مشكلة أثناء محاولة إنشاء رد. يرجى المحاولة مرة أخرى."
    except Exception as e:
        print(f"An unexpected error occurred in generate_openai_response for user {user_id}: {e}")
        ai_response = "An unexpected error occurred. Our team has been notified."
        if lang == "ar":
            ai_response = "حدث خطأ غير متوقع. تم إخطار فريقنا."
            
    return ai_response
