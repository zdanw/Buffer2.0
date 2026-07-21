"""Chroma 向量库客户端。CLIP 通过 embedding_backend 扩展点接入。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

import chromadb

from bebcare.knowledge_base.embedding_backend import get_embedding_backend

logger = logging.getLogger(__name__)

# 未启用 CLIP 时写入占位向量，仅用于挂载 metadata（如 phash）
_PLACEHOLDER_DIM = 512


class ChromaClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.client = chromadb.PersistentClient(path="./chroma_data")
        self.collection_name = "bebcare_products"
        self._get_or_create_collection()

    def _get_or_create_collection(self):
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(self.collection_name)

    @property
    def embeddings_enabled(self) -> bool:
        return get_embedding_backend().enabled

    def get_image_embedding(self, image: Any) -> List[float]:
        embedding = get_embedding_backend().embed_image(image)
        if embedding is None:
            return [0.0] * _PLACEHOLDER_DIM
        return embedding

    def add_image(self, image_id, embedding, metadata):
        clean_metadata = {}
        for key, value in metadata.items():
            if value is None:
                clean_metadata[key] = ""
            elif isinstance(value, (datetime,)):
                clean_metadata[key] = str(value)
            elif isinstance(value, (str, int, float, bool)):
                clean_metadata[key] = value
            else:
                clean_metadata[key] = str(value)

        if not embedding:
            embedding = [0.0] * _PLACEHOLDER_DIM

        self.collection.add(
            ids=[str(image_id)],
            embeddings=[embedding],
            metadatas=[clean_metadata],
        )

    def get_images_by_product(self, product_id):
        return self.collection.get(where={"product_id": str(product_id)})

    def search_similar_images(self, embedding, product_id=None, n_results=10):
        if not self.embeddings_enabled:
            return {"distances": [], "ids": [], "metadatas": []}

        where_clause = {"product_id": str(product_id)} if product_id else None
        return self.collection.query(
            query_embeddings=[embedding],
            where=where_clause,
            n_results=n_results,
        )

    def delete_image(self, image_id):
        self.collection.delete(ids=[image_id])

    def reset_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
            logger.info("Collection %s deleted", self.collection_name)
        except Exception as e:
            logger.warning("Collection delete: %s", e)

        self.collection = self.client.create_collection(self.collection_name)
        logger.info("New collection %s created", self.collection_name)


chroma_client = ChromaClient()
