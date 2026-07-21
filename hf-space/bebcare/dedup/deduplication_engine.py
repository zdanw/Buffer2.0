"""去重引擎：phash / MinHash 始终可用；CLIP 相似度走 embedding 扩展点。"""
from __future__ import annotations

from typing import List, Optional, Tuple

from datasketch import MinHash, MinHashLSH

from bebcare.knowledge_base.chroma_client import chroma_client
from bebcare.knowledge_base.embedding_backend import get_embedding_backend
from bebcare.utils.image_utils import calculate_phash, hamming_distance


class DeduplicationEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeduplicationEngine, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.phash_threshold = 5
        self.clip_threshold = 0.92
        self.minhash_threshold = 0.8
        self.lsh = MinHashLSH(threshold=self.minhash_threshold, num_perm=128)

    def check_image_duplicate(self, image, product_id=None) -> Tuple[bool, float]:
        phash_value = calculate_phash(image)

        if product_id:
            results = chroma_client.get_images_by_product(product_id)
            for metadata in results.get("metadatas", []) or []:
                existing_phash = metadata.get("phash")
                if existing_phash:
                    distance = hamming_distance(phash_value, existing_phash)
                    if distance <= self.phash_threshold:
                        return True, distance

        return False, float("inf")

    def check_image_similarity(self, image, product_id=None) -> Tuple[bool, float]:
        backend = get_embedding_backend()
        if not backend.enabled:
            return False, 0.0

        embedding = backend.embed_image(image)
        if embedding is None:
            return False, 0.0

        results = chroma_client.search_similar_images(embedding, product_id)
        for similarity in results.get("distances", []) or []:
            # Chroma 可能返回嵌套 list
            scores = similarity if isinstance(similarity, list) else [similarity]
            for score in scores:
                if score > self.clip_threshold:
                    return True, float(score)

        return False, 0.0

    def check_text_duplicate(self, text: str, existing_texts: List[str]) -> Tuple[bool, float]:
        text_minhash = self._text_to_minhash(text)

        max_similarity = 0.0
        for existing_text in existing_texts:
            existing_minhash = self._text_to_minhash(existing_text)
            similarity = text_minhash.jaccard(existing_minhash)
            max_similarity = max(max_similarity, similarity)
            if similarity >= self.minhash_threshold:
                return True, similarity

        return False, max_similarity

    def _text_to_minhash(self, text: str) -> MinHash:
        tokens = text.lower().split()
        minhash = MinHash(num_perm=128)
        for token in tokens:
            minhash.update(token.encode("utf-8"))
        return minhash

    def calculate_text_image_match(self, text: str, image) -> Optional[float]:
        """未启用 CLIP 时返回 None，调用方应跳过图文匹配闸门。"""
        return get_embedding_backend().text_image_similarity(text, image)


deduplication_engine = DeduplicationEngine()
