import os

CAMERA_TOPIC = "/sancho_camera/image_rect"
IMAGE_CAPTURE_TIMEOUT_SEC = 5.0
POSE_TOPIC = "/amcl_pose"
POSE_TIMEOUT_SEC = 2.0
MAP_FRAME_ID = "map"
BASE_FRAME_ID = "base_link"
TF_TIMEOUT_SEC = 0.5


LMSTUDIO_BASE_URL = os.environ.get(
    "SANCHO_MCP_LMSTUDIO_BASE_URL", "http://lmstudio.jemonra.uedge.mapir:1234/v1"
)
LMSTUDIO_API_KEY = os.environ.get("SANCHO_MCP_LMSTUDIO_API_KEY", "lm-studio")
LMSTUDIO_VISION_MODEL = os.environ.get(
    "SANCHO_MCP_LVLM_MODEL", "google/gemma-4-31b"
)
LMSTUDIO_VISION_MAX_TOKENS = int(os.environ.get("SANCHO_MCP_LVLM_MAX_TOKENS", "5000"))


def normalize_openai_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    return base_url if base_url.endswith("/v1") else f"{base_url}/v1"