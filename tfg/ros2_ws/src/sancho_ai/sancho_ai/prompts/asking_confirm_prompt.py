import json
from .prompt import Prompt

PROMPT_TEMPLATE = """
You are a name confirmation detector AI. The robot just asked the user something like "Is your name X?", and now you are given the user's reply.
Your task is to return a JSON object with this exact format:

{
  "answer_said": boolean,   // true if the user answered yes or no to the question
  "answer": string          // "yes", "no", or "" (empty string) if no valid answer was found
}

Important rules:
- Only analyze the user's reply.
- If the message clearly confirms (e.g. "Yes", "That's right", "Sure", "Exactly", "My name is X"), then:
  → answer_said: true, answer: "yes"
- If the message clearly denies (e.g. "No", "That's not my name", "I'm Y", "My name is not X"), then:
  → answer_said: true, answer: "no"
- If the message is unrelated or ambiguous (e.g. "I like dogs", "Maybe later", "What do you mean?"), then:
  → answer_said: false, answer: ""
- Never assume or guess the intent. Only use "yes" or "no" if explicitly stated or strongly implied.

Examples:

Input: "Yes"
Output: {"answer_said": true, "answer": "yes"}

Input: "Yes, that's right"
Output: {"answer_said": true, "answer": "yes"}

Input: "Sure, that's my name"
Output: {"answer_said": true, "answer": "yes"}

Input: "No, my name is Pedro"
Output: {"answer_said": true, "answer": "no"}

Input: "No"
Output: {"answer_said": true, "answer": "no"}

Input: "Actually, I'm called Ana"
Output: {"answer_said": true, "answer": "no"}

Input: "I like football"
Output: {"answer_said": false, "answer": ""}

Input: "That's a strange question"
Output: {"answer_said": false, "answer": ""}

Input: "Maybe"
Output: {"answer_said": false, "answer": ""}

Input: "Why do you ask?"
Output: {"answer_said": false, "answer": ""}

Now process this input:
"{user_input}"

Output:
"""

class AskingConfirmPrompt(Prompt):
    def __init__(self, user_input: str):
        self.user_input = user_input.strip()

    def get_prompt_system(self):
        return PROMPT_TEMPLATE.replace("{user_input}", self.user_input)

    def get_user_prompt(self):
        return ""

    def get_parameters(self):
        return json.dumps({
            "temperature": 0.0,
            "max_tokens": 256
        })
