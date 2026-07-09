from typing import List, Dict, Tuple
from datasketch import MinHash, MinHashLSH
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import torch
import sys
import os
from bebcare.utils.image_utils import hamming_distance, calculate_phash
from bebcare.knowledge_base.chroma_client import chroma_client

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
        
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.long_clip_path = os.path.join(backend_dir, 'Long-CLIP')
        self.longclip_available = False
        self.longclip = None
        
        if os.path.exists(self.long_clip_path):
            sys.path.insert(0, self.long_clip_path)
            try:
                from model import longclip
                self.longclip = longclip
                self.longclip_available = True
                print("Long-CLIP tokenizer loaded successfully")
            except Exception as e:
                print(f"Failed to load Long-CLIP tokenizer: {e}")
    
    def check_image_duplicate(self, image, product_id=None) -> Tuple[bool, float]:
        phash_value = calculate_phash(image)
        
        if product_id:
            results = chroma_client.get_images_by_product(product_id)
            for metadata in results.get('metadatas', []):
                existing_phash = metadata.get('phash')
                if existing_phash:
                    distance = hamming_distance(phash_value, existing_phash)
                    if distance <= self.phash_threshold:
                        return True, distance
        
        return False, float('inf')
    
    def check_image_similarity(self, image, product_id=None) -> Tuple[bool, float]:
        embedding = chroma_client.get_image_embedding(image)
        
        results = chroma_client.search_similar_images(embedding, product_id)
        
        for i, similarity in enumerate(results.get('distances', [])):
            if similarity > self.clip_threshold:
                return True, similarity
        
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
            minhash.update(token.encode('utf-8'))
        return minhash
    
    def calculate_text_image_match(self, text: str, image) -> float:
        image_embedding = chroma_client.get_image_embedding(image)
        
        model = chroma_client.clip_model
        processor = chroma_client.clip_processor
        device = chroma_client.device
        
        if self.longclip_available and hasattr(model, 'encode_text'):
            text_input = self.longclip.tokenize([text]).to(device)
            with torch.no_grad():
                text_embedding = model.encode_text(text_input).cpu().numpy()
        else:
            max_chars = 300
            truncated_text = text[:max_chars] if len(text) > max_chars else text
            inputs = processor(text=[truncated_text], return_tensors="pt").to(device)
            with torch.no_grad():
                text_embedding = model.get_text_features(**inputs).cpu().detach().numpy()
        
        similarity = cosine_similarity(text_embedding, np.array([image_embedding]))[0][0]
        return similarity

deduplication_engine = DeduplicationEngine()