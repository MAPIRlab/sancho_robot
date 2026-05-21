import os
import google.generativeai as genai

def list_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        return

    genai.configure(api_key=api_key)

    print("--- Available Gemini Models ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Name: {m.name}")
                print(f"  Description: {m.description}")
                print(f"  Supported Methods: {m.supported_generation_methods}\n")
    except Exception as e:
        print(f"Error calling list_models: {e}")

if __name__ == "__main__":
    list_models()
