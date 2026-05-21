import base64
import logging
import traceback
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import SecretStr
from sensor_msgs.msg import Image

from .config import (
    LMSTUDIO_API_KEY,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_VISION_MAX_TOKENS,
    LMSTUDIO_VISION_MODEL,
    normalize_openai_base_url,
)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if text:
                    parts.append(str(text))
            elif hasattr(part, "text"):
                parts.append(str(getattr(part, "text")))
            else:
                parts.append(str(part))
        return "\n".join(piece for piece in parts if piece).strip()

    return str(content).strip()


class LMStudioVisionDescriber:
    def __init__(
        self,
        base_url: str = LMSTUDIO_BASE_URL,
        api_key: str = LMSTUDIO_API_KEY,
        model: str = LMSTUDIO_VISION_MODEL,
        logger: Optional[Any] = None,
    ):
        self.base_url = normalize_openai_base_url(base_url)
        self.model = model
        self.logger = logger or logging.getLogger(__name__)
        # initialize LLM client
        try:
            self.llm = ChatOpenAI(
                model=model,
                base_url=self.base_url,
                api_key=SecretStr(api_key),
                temperature=0.2,
                max_completion_tokens=LMSTUDIO_VISION_MAX_TOKENS,
            )
            self.raw_client = OpenAI(base_url=self.base_url, api_key=api_key)
        except Exception as exc:  # pragma: no cover - surface initialization issues
            self.logger.error(f"Failed to initialize ChatOpenAI client: {exc}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    @staticmethod
    def _ros_image_to_data_uri(ros_image: Image, cv_bridge: Any, cv2: Any) -> str:
        cv_image = cv_bridge.imgmsg_to_cv2(ros_image, desired_encoding="bgr8")
        _, buffer = cv2.imencode(".jpg", cv_image)
        encoded_image = base64.b64encode(buffer.tobytes()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded_image}"

    @staticmethod
    def _vision_prompt() -> str:
        return (
            "Describe what the robot sees in as much detail as possible, "
            "without redundancy."
        )

    def _build_message(self, prompt: str, image_data_uri: str) -> HumanMessage:
        return HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ]
        )

    def _log_request(self, image_data_uri: str) -> None:
        try:
            self.logger.debug(
                f"Sending vision request to LMStudio model={self.model} "
                f"base_url={self.base_url} image_b64_len={len(image_data_uri)}"
            )
        except Exception:
            pass

    def _fallback_reasoning(self, prompt: str, image_data_uri: str) -> str:
        try:
            raw = self.raw_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_uri}},
                        ],
                    }
                ],
                max_tokens=LMSTUDIO_VISION_MAX_TOKENS,
                temperature=0.2,
            )
            raw_choice = raw.choices[0]
            raw_message = raw_choice.message
            reasoning = getattr(raw_message, "reasoning_content", None)
            if reasoning:
                return _message_content_to_text(reasoning)
        except Exception as exc:
            self.logger.error(f"Raw OpenAI fallback failed: {exc}")
        return ""

    def describe_ros_image(self, ros_image: Image, cv_bridge: Any, cv2: Any) -> str:
        image_data_uri = self._ros_image_to_data_uri(ros_image, cv_bridge, cv2)
        prompt = self._vision_prompt()
        message = self._build_message(prompt, image_data_uri)

        self._log_request(image_data_uri)

        try:
            response = self.llm.invoke([message])
            try:
                self.logger.debug(f"Raw LMStudio response: {repr(response)}")
            except Exception:
                self.logger.debug("Raw LMStudio response received (repr failed)")

            raw_content = getattr(response, "content", "")
            description = _message_content_to_text(raw_content)
            if not description:
                description = self._fallback_reasoning(prompt, image_data_uri)

            if not description:
                self.logger.error(
                    f"Vision model returned empty description. Raw content: {raw_content}"
                )
                raise RuntimeError("The vision model returned an empty description.")

            finish_reason = None
            try:
                metadata = getattr(response, "response_metadata", {}) or {}
                finish_reason = metadata.get("finish_reason")
            except Exception:
                finish_reason = None

            if finish_reason == "length":
                description = f"{description}\n\n[Truncated: increase SANCHO_MCP_LVLM_MAX_TOKENS]"

            self.logger.info(
                f"Vision description length={len(description)} finish_reason={finish_reason}"
            )
            return description
        except Exception as exc:
            self.logger.error(f"Error during vision describe call: {exc}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            raise