from .base_provider import BaseProvider


class APIProvider(BaseProvider):

    def load(self, *args, **kwargs):
        print(f"[INFO] Skipping load: API-based provider, nothing to load.")

    def unload(self, *args, **kwargs):
        print(f"[INFO] Skipping unload: API-based provider, nothing to unload.")
