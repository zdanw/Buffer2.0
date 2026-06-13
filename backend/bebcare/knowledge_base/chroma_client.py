import chromadb
import torch
from datetime import datetime
import sys
import os
import requests
from PIL import Image
from io import BytesIO

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
        self._load_longclip_model()
    
    def _get_or_create_collection(self):
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(self.collection_name)
    
    def _load_longclip_model(self):
        try:
            # Get absolute path to Long-CLIP directory
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.long_clip_path = os.path.join(backend_dir, 'Long-CLIP')
            
            print(f"Trying to load Long-CLIP from: {self.long_clip_path}")
            
            if os.path.exists(self.long_clip_path):
                sys.path.insert(0, self.long_clip_path)
                from model import longclip
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                
                checkpoint_path = os.path.join(self.long_clip_path, 'checkpoints', 'longclip-B.pt')
                print(f"Looking for checkpoint at: {checkpoint_path}")
                
                if os.path.exists(checkpoint_path):
                    self.clip_model, self.clip_processor = longclip.load(checkpoint_path, device=self.device)
                    self.clip_available = True
                    print("Long-CLIP-B model loaded successfully from local checkpoint")
                else:
                    print(f"Checkpoint not found at {checkpoint_path}")
                    raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")
            else:
                print(f"Long-CLIP directory not found: {self.long_clip_path}")
                raise FileNotFoundError(f"Long-CLIP directory not found: {self.long_clip_path}")
                
        except Exception as e:
            print(f"Long-CLIP model not available: {e}")
            # Fallback to standard CLIP
            try:
                from transformers import CLIPProcessor, CLIPModel
                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.clip_model.to(self.device)
                self.clip_available = True
                print("Fallback: Standard CLIP model loaded successfully")
            except Exception as fallback_e:
                print(f"Fallback CLIP also failed: {fallback_e}")
                self.clip_model = None
                self.clip_processor = None
                self.device = "cpu"
                self.clip_available = False
    
    def get_image_embedding(self, image):
        if not self.clip_available:
            return [0.0] * 512
        
        if isinstance(image, str):
            response = requests.get(image, timeout=30)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
        
        image_input = self.clip_processor(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.clip_model.encode_image(image_input)
        if self.device.type == "cuda":
            return outputs.cpu().numpy()[0].tolist()
        else:
            return outputs.numpy()[0].tolist()
    
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
        
        self.collection.add(
            ids=[str(image_id)],
            embeddings=[embedding],
            metadatas=[clean_metadata]
        )
    
    def get_images_by_product(self, product_id):
        results = self.collection.get(
            where={"product_id": str(product_id)}
        )
        return results
    
    def search_similar_images(self, embedding, product_id=None, n_results=10):
        where_clause = None
        if product_id:
            where_clause = {"product_id": str(product_id)}
        
        results = self.collection.query(
            query_embeddings=[embedding],
            where=where_clause,
            n_results=n_results
        )
        return results
    
    def delete_image(self, image_id):
        self.collection.delete(ids=[image_id])
    
    def reset_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
            print(f"Collection {self.collection_name} deleted")
        except Exception as e:
            print(f"Collection not found or error deleting: {e}")
        
        self.collection = self.client.create_collection(self.collection_name)
        print(f"New collection {self.collection_name} created")

chroma_client = ChromaClient()