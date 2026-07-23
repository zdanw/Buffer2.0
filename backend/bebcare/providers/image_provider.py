from typing import List, Optional, Protocol


class ImageProvider(Protocol):
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "2048x2048",
        model: Optional[str] = None,
    ) -> List[str]:
        """Return list of temporary image URLs."""
        ...

    def list_models(self) -> List[dict]:
        """Return [{id, owned_by?}, ...]. Empty if unsupported."""
        ...
