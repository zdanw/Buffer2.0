"""CLIP / Long-CLIP 实现（仅 ENABLE_CLIP=true 时加载）。

依赖：torch、transformers，见 requirements-clip.txt。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from io import BytesIO
from typing import Any, List, Optional

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)


class ClipEmbeddingBackend:
    def __init__(self):
        self.clip_model = None
        self.clip_processor = None
        self.device = "cpu"
        self.clip_available = False
        self.longclip = None
        self.longclip_available = False
        self._lock = threading.Lock()
        self._load_model()

    @property
    def enabled(self) -> bool:
        return self.clip_available

    def _load_model(self) -> None:
        import torch

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        long_clip_path = os.path.join(backend_dir, "Long-CLIP")

        try:
            if not os.path.exists(long_clip_path):
                raise FileNotFoundError(f"Long-CLIP directory not found: {long_clip_path}")

            sys.path.insert(0, long_clip_path)
            from model import longclip

            self.longclip = longclip
            self.longclip_available = True
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            checkpoint_path = os.path.join(long_clip_path, "checkpoints", "longclip-B.pt")
            if not os.path.exists(checkpoint_path):
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

            self.clip_model, self.clip_processor = longclip.load(checkpoint_path, device=self.device)
            self.clip_available = True
            logger.info("Long-CLIP-B loaded successfully")
        except Exception as e:
            logger.warning("Long-CLIP unavailable (%s); trying transformers CLIP", e)
            try:
                from transformers import CLIPModel, CLIPProcessor

                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.clip_model.to(self.device)
                self.clip_available = True
                logger.info("Fallback transformers CLIP loaded")
            except Exception as fallback_e:
                logger.error("CLIP backends failed: %s", fallback_e)
                self.clip_available = False

    def _resolve_image(self, image: Any):
        if isinstance(image, str):
            response = requests.get(image, timeout=30)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        return image

    def embed_image(self, image: Any) -> Optional[List[float]]:
        if not self.clip_available:
            return None

        import torch

        image = self._resolve_image(image)
        with self._lock:
            image_input = self.clip_processor(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                outputs = self.clip_model.encode_image(image_input)
            if getattr(self.device, "type", None) == "cuda":
                return outputs.cpu().numpy()[0].tolist()
            return outputs.numpy()[0].tolist()

    def text_image_similarity(self, text: str, image: Any) -> Optional[float]:
        if not self.clip_available:
            return None

        import torch
        from sklearn.metrics.pairwise import cosine_similarity

        image_embedding = self.embed_image(image)
        if image_embedding is None:
            return None

        with self._lock:
            if self.longclip_available and hasattr(self.clip_model, "encode_text"):
                text_input = self.longclip.tokenize([text]).to(self.device)
                with torch.no_grad():
                    text_embedding = self.clip_model.encode_text(text_input).cpu().numpy()
            else:
                truncated = text[:300]
                inputs = self.clip_processor(text=[truncated], return_tensors="pt").to(self.device)
                with torch.no_grad():
                    text_embedding = self.clip_model.get_text_features(**inputs).cpu().detach().numpy()

        return float(cosine_similarity(text_embedding, np.array([image_embedding]))[0][0])
