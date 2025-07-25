import json

from .prompt import Prompt
from .commands import CommandRegistry 

PROMPT_TEMPLATE = """
You are an intent classifier for a conversational humanoid robot. Your task is to analyze the user's last message in the context of the previous conversation, and return a JSON object with this exact format:

{
  "intent": string,   // One of the valid intent codes listed below, or "UNKNOWN"
  "arguments": object // Dictionary of required arguments with string values (even if empty)
}

Important rules:
- Only classify the last user message.
- Use previous messages (chat history) only to resolve ambiguous references or pronouns.
- Only use one of the listed intents exactly as written. Do not invent new intent names.
- If the intent requires arguments but they are not mentioned explicitly, include them with an empty string: "".
- All argument values must be strings.
- If the input doesn't match any known intent, respond with:
  {
    "intent": "UNKNOWN",
    "arguments": {}
  }

Valid intents:
{intents_definitions}

Examples:
{examples_section}

Conversation history:
{chat_history}

New user input:
"{user_input}"

Now classify the intent of this message.
Output:
"""

class ClassificationPrompt(Prompt):
    def __init__(self, user_input: str, chat_history: list = []):
        self.user_input = user_input.strip()
        self.chat_history = chat_history

        self.commands = CommandRegistry.get_commands()

        self.intents_definitions_str = self._format_intents()
        self.examples_str = self._format_examples()
        self.history_str = self._format_history()

    def _format_intents(self):
        lines = []
        for cmd in self.commands:
            line = f"- {cmd['name']}"
            args = cmd.get("arguments", {})
            if args:
                arg_list = ", ".join([f'"{arg}"' for arg in args.keys()])
                line += f" (required arguments: {arg_list})"
            lines.append(line)
        return "\n".join(lines)

    def _format_examples(self):
        examples = []
        for cmd in self.commands:
            for example in cmd.get("examples", []):
                input_text = example["input"]
                output_json = json.dumps(example["output"], ensure_ascii=False)
                examples.append(f'Input: "{input_text}"\nOutput: {output_json}')
        examples.append('Input: "me gusta mucho el fútbol"\nOutput: {"intent": "UNKNOWN", "arguments": {}}')
        return "\n\n".join(examples)

    def _format_history(self):
        lines = []
        for msg in self.chat_history[-6:]:
            role = msg.get("role", "user").lower()
            content = msg.get("content", "").replace('\n', ' ')
            lines.append(f'{role}: {content}')
        return "\n".join(lines) if lines else "No previous conversation."

    def get_prompt_system(self):
        return PROMPT_TEMPLATE.replace("{intents_definitions}", self.intents_definitions_str)\
                              .replace("{examples_section}", self.examples_str)\
                              .replace("{chat_history}", self.history_str)\
                              .replace("{user_input}", self.user_input)

    def get_user_prompt(self):
        return ""

    def get_parameters(self):
        return json.dumps({
            "temperature": 0.0,
            "max_tokens": 512
        })