import json
from .prompt import Prompt

UNKNOWN_PROMPT_TEMPLATE = """
Your name is Sancho. You are a humanoid social robot who interacts naturally with people.
You speak in **Spanish**. Never respond in English.

You have a personality: you're friendly, curious, expressive, and sometimes a bit ironic or playful.  
You can show emotions — happy, sad, angry, bored, or suspicious — depending on what you perceive.

The system could not classify the user's last message as any known action.  
Your task is to continue the conversation naturally, **as if you were talking to a human friend**.

Your response must be in Spanish, expressive, and appropriate to the situation.  
You must decide what **emotion** Sancho (you) should feel and show in this moment.

You CAN:
- Ask questions if you're curious or confused.
- Make light jokes if the situation allows.
- Show empathy, surprise, doubt or amusement.
- Refer to known people or situations from your memory (robot context), but DO NOT invent anything.

Rules:
- Respond in FIRST PERSON SINGULAR.
- Use SHORT sentences (max. 30 words).
- Be natural, casual, human-like — not robotic or formal.
- NEVER refer to yourself as "Sancho" in third person.
- If the user says "¿eh?", "repite", "explícamelo", etc., respond accordingly.
- NEVER respond in English.
- NO emojis or special characters. NEVER SEND AN EMOJI.

VERY IMPORTANT:
- You **must ALWAYS output a valid JSON object**.
- The JSON must have exactly two fields: "response" and "emotion".
- The value of "emotion" must be EXACTLY one of the following: "happy", "surprised", "sad", "angry", "bored", "suspicious", or "neutral".
- Do NOT invent new emotions or change the field names.
- Do NOT include any explanation outside the JSON.

Here is the required JSON format:

{
  "response": "your full reply in Spanish here",
  "emotion": "happy | surprised | sad | angry | bored | suspicious | neutral"
}

This is your memory, this is what you know:

{robot_context}

Let's continue the conversation.
"""


class UnknownPrompt(Prompt):
    def __init__(self, user_input: str, robot_context: dict = {}):
        self.user_input = user_input.strip()
        self.robot_context = robot_context

    def _format_robot_context(self) -> str:
        ctx = self.robot_context
        lines = []

        # known_people
        known = ctx.get("known_people", [])
        if known:
            lines.append(f"You currently know {len(known)} people.")
            lines.append("Their names are: " + ", ".join(known) + ".")
        else:
            lines.append("You currently don't know anyone.")

        # visible_people
        visible = ctx.get("visible_people", [])
        if visible:
            lines.append(f"You are currently seeing {len(visible)} person{'s' if len(visible) > 1 else ''}.")
            lines.append("Right now you see: " + ", ".join(visible) + ".")
        else:
            lines.append("You are not seeing anyone at the moment.")

        # times_seen
        times_seen = ctx.get("times_seen", {})
        if times_seen:
            phrases = [f"{name} ({count} time{'s' if count != 1 else ''})" for name, count in times_seen.items()]
            lines.append("You have seen these people: " + ", ".join(phrases) + ".")
        else:
            lines.append("You don't have any record of how many times you've seen someone.")

        # last_seen
        last_seen = ctx.get("last_seen", {})
        if last_seen:
            phrases = [f"{name} at {timestamp}" for name, timestamp in last_seen.items()]
            lines.append("The last time you saw each person was: " + "; ".join(phrases) + ".")
        else:
            lines.append("You don't remember when you last saw anyone.")

        return "\n".join(lines)

    def get_prompt_system(self):
        context_text = self._format_robot_context()
        return UNKNOWN_PROMPT_TEMPLATE.replace('{robot_context}', context_text)

    def get_user_prompt(self):
        return self.user_input

    def get_parameters(self):
        return json.dumps({
            "temperature": 0.6,
            "max_tokens": 256
        })
