"""
Simplified RAG System that reads ChromaDB embeddings without ChromaDB dependency
Uses TF-IDF fallback when ChromaDB is not available in main environment
"""
import os
import re
import json
import pickle
from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config.settings import Config

class ArgoRAGSystemSimple:
    """Simplified RAG system that can work without ChromaDB in main environment"""
    
    def __init__(self):
        self.config = Config()
        self.knowledge_chunks = []
        self.vectorizer = None
        self.vectors = None
        self.is_initialized = False
        
        # Try to load pre-created embeddings or create TF-IDF fallback
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize embeddings - try ChromaDB first, fallback to TF-IDF"""
        
        # First, try to read from ChromaDB if it exists (created in embeddings environment)
        chroma_path = os.path.join(self.config.CHROMA_PERSIST_DIRECTORY, "chroma.sqlite3")
        
        if os.path.exists(chroma_path):
            print("📚 Found existing ChromaDB, but using simplified access...")
            # ChromaDB exists but we can't access it without chromadb package
            # Fall back to creating TF-IDF from knowledge base
            self._create_tfidf_fallback()
        else:
            print("📚 No ChromaDB found, creating TF-IDF fallback...")
            self._create_tfidf_fallback()
    
    def _create_tfidf_fallback(self):
        """Create TF-IDF based similarity search from knowledge base"""
        knowledge_base_path = "./data/improved_knowledge_base.md"
        
        if not os.path.exists(knowledge_base_path):
            print(f"⚠️ Knowledge base file not found: {knowledge_base_path}")
            return
        
        try:
            # Read knowledge base
            with open(knowledge_base_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Split into chunks
            self.knowledge_chunks = self._split_content_simple(content)
            
            # Create TF-IDF vectors
            chunk_texts = [chunk['content'] for chunk in self.knowledge_chunks]
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000, ngram_range=(1,2))
            self.vectors = self.vectorizer.fit_transform(chunk_texts)
            
            self.is_initialized = True
            print(f"✅ Initialized TF-IDF RAG system with {len(self.knowledge_chunks)} chunks")
            
        except Exception as e:
            print(f"❌ Error creating TF-IDF fallback: {e}")
    
    def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant context using TF-IDF similarity"""
        if not self.is_initialized:
            print("⚠️ RAG system not initialized")
            return self._get_hardcoded_context(query)
        
        try:
            # Transform query
            query_vector = self.vectorizer.transform([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.vectors).flatten()
            
            # Get top-k most similar chunks
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            context_chunks = []
            for idx in top_indices:
                if similarities[idx] > 0.05:  # Lower threshold for TF-IDF
                    chunk = self.knowledge_chunks[idx].copy()
                    chunk['distance'] = float(1 - similarities[idx])  # Convert similarity to distance
                    chunk['metadata'] = {
                        'section': chunk['section'],
                        'chunk_type': chunk['chunk_type']
                    }
                    context_chunks.append(chunk)
            
            print(f"🔍 Retrieved {len(context_chunks)} relevant chunks for query")
            return context_chunks
            
        except Exception as e:
            print(f"❌ Error retrieving context: {str(e)}")
            return self._get_hardcoded_context(query)
    
    def search_by_category(self, query: str, chunk_type: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for specific chunk types"""
        if not self.is_initialized:
            return []
        
        try:
            # Filter chunks by category first
            category_chunks = [(i, chunk) for i, chunk in enumerate(self.knowledge_chunks) 
                              if chunk.get('chunk_type') == chunk_type]
            
            if not category_chunks:
                return []
            
            # Get indices and chunks
            category_indices = [i for i, chunk in category_chunks]
            category_vectors = self.vectors[category_indices]
            
            # Transform query and calculate similarities
            query_vector = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, category_vectors).flatten()
            
            # Get top results
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for local_idx in top_indices:
                if similarities[local_idx] > 0.05:
                    global_idx = category_indices[local_idx]
                    chunk = self.knowledge_chunks[global_idx].copy()
                    chunk['distance'] = float(1 - similarities[local_idx])
                    chunk['metadata'] = {
                        'section': chunk['section'], 
                        'chunk_type': chunk['chunk_type']
                    }
                    results.append(chunk)
            
            return results
            
        except Exception as e:
            print(f"❌ Error in category search: {str(e)}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        if not self.is_initialized:
            return {"error": "RAG system not initialized"}
        
        return {
            "total_chunks": len(self.knowledge_chunks),
            "collection_name": "argo_knowledge_base_tfidf", 
            "embedding_model": "TF-IDF (sklearn)"
        }
    
    def _split_content_simple(self, content: str) -> List[Dict[str, Any]]:
        """Simple content splitter without LangChain"""
        chunks = []
        
        # Split by sections
        sections = re.split(r'\n## ', content)
        
        for section in sections:
            if not section.strip():
                continue
            
            lines = section.split('\n')
            section_title = lines[0].replace('# ', '').strip()
            section_content = '\n'.join(lines[1:])
            
            # Categorize chunk
            chunk_type = self._categorize_chunk(section_title, section_content)
            
            # Simple splitting for large sections
            if len(section_content) > 600:
                paragraphs = section_content.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    if len(current_chunk) + len(para) < 600:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            chunks.append({
                                'content': current_chunk.strip(),
                                'section': section_title,
                                'chunk_type': chunk_type
                            })
                        current_chunk = para + "\n\n"
                
                if current_chunk.strip():
                    chunks.append({
                        'content': current_chunk.strip(),
                        'section': section_title,
                        'chunk_type': chunk_type
                    })
            else:
                if section_content.strip():
                    chunks.append({
                        'content': section_content.strip(),
                        'section': section_title,
                        'chunk_type': chunk_type
                    })
        
        return chunks
    
    def _categorize_chunk(self, title: str, content: str) -> str:
        """Categorize chunk based on content"""
        title_lower = title.lower()
        content_lower = content.lower()
        
        if 'schema' in title_lower or 'table' in title_lower or 'column' in title_lower:
            return 'schema'
        elif 'geographic' in title_lower or 'region' in title_lower:
            return 'geography'
        elif 'temporal' in title_lower or 'time' in title_lower:
            return 'temporal'
        elif 'example' in title_lower or 'select' in content_lower:
            return 'examples'
        elif 'bgc' in content_lower or 'bio-geo' in content_lower:
            return 'bgc'
        else:
            return 'general'
    
    def _get_hardcoded_context(self, query: str) -> List[Dict[str, Any]]:
        """Fallback hardcoded context for common queries"""
        query_lower = query.lower()
        
        hardcoded_chunks = []
        
        if 'arabian sea' in query_lower:
            hardcoded_chunks.append({
                'content': 'Arabian Sea coordinates: 8°N to 30°N, 50°E to 75°E. SQL: latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75',
                'metadata': {'section': 'Geographic Regions', 'chunk_type': 'geography'},
                'distance': 0.1
            })
        
        if 'bgc' in query_lower:
            hardcoded_chunks.append({
                'content': 'BGC floats have biochemical sensors. Use float_category = "BGC" to filter. Available parameters: dissolved oxygen, chlorophyll, nitrate.',
                'metadata': {'section': 'Float Categories', 'chunk_type': 'bgc'},
                'distance': 0.1
            })
        
        if 'temperature' in query_lower or 'salinity' in query_lower:
            hardcoded_chunks.append({
                'content': 'Temperature and salinity are core parameters. Always use array_length(temperature_celsius, 1) > 0 for valid data checks.',
                'metadata': {'section': 'Core Parameters', 'chunk_type': 'schema'},
                'distance': 0.1
            })
        
        return hardcoded_chunks

    # Add compatibility methods
    def create_embeddings_from_file(self, file_path: str):
        """Compatibility method - not needed in simplified version"""
        print("⚠️ Embeddings creation should be done in separate ChromaDB environment")
        return 0