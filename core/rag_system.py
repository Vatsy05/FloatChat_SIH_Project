"""
RAG System with ChromaDB for ARGO domain knowledge retrieval
Enhanced version with MarkdownHeaderTextSplitter for better semantic chunking
"""
import os
import re
import chromadb
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from config.settings import Config

class ArgoRAGSystem:
    def __init__(self):
        self.config = Config()
        self.embedding_model = SentenceTransformer(self.config.EMBEDDING_MODEL)
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=self.config.CHROMA_PERSIST_DIRECTORY
        )
        
        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(
                name=self.config.COLLECTION_NAME
            )
            print(f"✅ Loaded existing ChromaDB collection: {self.config.COLLECTION_NAME}")
        except Exception:
            print(f"🔄 Creating new ChromaDB collection: {self.config.COLLECTION_NAME}")
            self.collection = None
    
    def create_embeddings_from_file(self, file_path: str = "./data/improved_knowledge_base.md"):
        """Create embeddings from the knowledge base file using enhanced markdown splitting"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Knowledge base file not found: {file_path}")
        
        # Read the knowledge base file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Split content into chunks with enhanced markdown splitting
        chunks = self._split_content_enhanced(content)
        
        # Create collection if it doesn't exist
        if self.collection is None:
            self.collection = self.chroma_client.create_collection(
                name=self.config.COLLECTION_NAME,
                metadata={"description": "ARGO FloatChat domain knowledge base"}
            )
        
        # Generate embeddings and store
        print(f"🔄 Processing {len(chunks)} knowledge chunks...")
        
        chunk_texts = []
        chunk_metadatas = []
        chunk_ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_texts.append(chunk['content'])
            chunk_metadatas.append({
                'section': chunk['section'],
                'subsection': chunk.get('subsection', ''),
                'full_header_path': chunk.get('full_header_path', ''),
                'chunk_type': chunk['chunk_type'],
                'header_level': chunk.get('header_level', 1),
                'content_length': len(chunk['content']),
                'is_sub_chunk': chunk.get('is_sub_chunk', False),
                'semantic_score': chunk.get('semantic_score', 1.0)
            })
            chunk_ids.append(f"chunk_{i}")
        
        # Add to ChromaDB collection
        self.collection.add(
            documents=chunk_texts,
            metadatas=chunk_metadatas,
            ids=chunk_ids
        )
        
        print(f"✅ Successfully created {len(chunks)} embeddings in ChromaDB")
        print(f"📊 Chunk distribution by type: {self._get_chunk_type_distribution(chunks)}")
        return len(chunks)
    
    def _split_content_enhanced(self, content: str) -> List[Dict[str, Any]]:
        """Enhanced content splitting using MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter"""
        
        # Define headers to split on - respecting the document hierarchy
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"), 
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]
        
        # Initialize the markdown header splitter
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False  # Keep headers in content for context
        )
        
        # First pass: Split by headers
        header_splits = markdown_splitter.split_text(content)
        
        print(f"📝 Initial header splits: {len(header_splits)} sections")
        
        # Second pass: Process each section
        final_chunks = []
        
        for doc in header_splits:
            # Extract header information from metadata
            section_info = self._extract_section_info(doc.metadata)
            
            # Determine chunk type based on content and headers
            chunk_type = self._categorize_chunk_enhanced(section_info, doc.page_content)
            
            # Calculate semantic importance score
            semantic_score = self._calculate_semantic_score(section_info, doc.page_content)
            
            # Handle large sections with recursive splitting
            if len(doc.page_content) > 1000:
                sub_chunks = self._split_large_section(doc.page_content, section_info)
                
                for i, sub_chunk in enumerate(sub_chunks):
                    if len(sub_chunk.strip()) > 50:  # Ignore very small chunks
                        final_chunks.append({
                            'content': sub_chunk.strip(),
                            'section': section_info['section'],
                            'subsection': section_info['subsection'],
                            'full_header_path': section_info['full_path'],
                            'chunk_type': chunk_type,
                            'header_level': section_info['level'],
                            'is_sub_chunk': len(sub_chunks) > 1,
                            'sub_chunk_index': i if len(sub_chunks) > 1 else None,
                            'semantic_score': semantic_score
                        })
            else:
                # Keep smaller sections intact
                if len(doc.page_content.strip()) > 50:
                    final_chunks.append({
                        'content': doc.page_content.strip(),
                        'section': section_info['section'],
                        'subsection': section_info['subsection'],
                        'full_header_path': section_info['full_path'],
                        'chunk_type': chunk_type,
                        'header_level': section_info['level'],
                        'is_sub_chunk': False,
                        'sub_chunk_index': None,
                        'semantic_score': semantic_score
                    })
        
        print(f"✨ Final optimized chunks: {len(final_chunks)}")
        return final_chunks
    
    def _extract_section_info(self, metadata: Dict) -> Dict[str, Any]:
        """Extract hierarchical section information from LangChain metadata"""
        
        # Build section hierarchy from metadata
        headers = []
        section = ""
        subsection = ""
        level = 1
        
        # LangChain stores headers as "Header 1", "Header 2", etc.
        for i in range(1, 5):  # Check up to Header 4
            header_key = f"Header {i}"
            if header_key in metadata:
                headers.append(metadata[header_key])
                level = i
        
        if headers:
            section = headers[0] if len(headers) > 0 else ""
            subsection = headers[-1] if len(headers) > 1 else ""
        
        full_path = " > ".join(headers) if headers else ""
        
        return {
            'section': section,
            'subsection': subsection,
            'full_path': full_path,
            'level': level,
            'headers': headers
        }
    
    def _split_large_section(self, content: str, section_info: Dict) -> List[str]:
        """Split large sections using RecursiveCharacterTextSplitter"""
        
        # Adjust chunk size based on content type
        chunk_size = 800
        chunk_overlap = 100
        
        # Increase chunk size for code examples and schemas
        if any(keyword in section_info['full_path'].lower() 
               for keyword in ['schema', 'example', 'template', 'sql']):
            chunk_size = 1200
            chunk_overlap = 150
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "```", ".", "!", "?", ",", " ", ""]
        )
        
        return text_splitter.split_text(content)
    
    def _categorize_chunk_enhanced(self, section_info: Dict, content: str) -> str:
        """Enhanced chunk categorization using header information and content"""
        
        full_path_lower = section_info['full_path'].lower()
        content_lower = content.lower()
        
        # Use header hierarchy for better categorization
        if any(keyword in full_path_lower for keyword in ['schema', 'table', 'column', 'database']):
            return 'schema'
        
        if any(keyword in full_path_lower for keyword in ['geographic', 'region', 'spatial']):
            return 'geography'
        
        if any(keyword in full_path_lower for keyword in ['temporal', 'time', 'date']):
            return 'temporal'
        
        if any(keyword in full_path_lower for keyword in ['example', 'query', 'template', 'pattern']):
            return 'examples'
        
        if any(keyword in full_path_lower for keyword in ['bgc', 'bio-geo', 'biochemical']):
            return 'bgc'
        
        if any(keyword in full_path_lower for keyword in ['rule', 'practice', 'implementation', 'critical']):
            return 'rules'
        
        if any(keyword in full_path_lower for keyword in ['quality', 'qc', 'validation']):
            return 'quality'
        
        # Content-based classification as fallback
        if 'select' in content_lower and ('from' in content_lower or 'where' in content_lower):
            return 'examples'
        
        if any(keyword in content_lower for keyword in ['bgc', 'oxygen', 'chlorophyll', 'nitrate']):
            return 'bgc'
        
        return 'general'
    
    def _calculate_semantic_score(self, section_info: Dict, content: str) -> float:
        """Calculate semantic importance score for better retrieval ranking"""
        
        score = 1.0
        full_path = section_info['full_path'].lower()
        
        # Boost important sections
        high_priority_keywords = ['schema', 'example', 'template', 'critical', 'rule']
        if any(keyword in full_path for keyword in high_priority_keywords):
            score += 0.3
        
        # Boost based on content richness
        if len(content) > 500 and 'sql' in content.lower():
            score += 0.2
        
        if content.count('\n') > 10:  # Multi-line structured content
            score += 0.1
        
        # Boost based on header level (higher level = more important)
        level_boost = max(0, (3 - section_info['level']) * 0.1)
        score += level_boost
        
        return min(score, 2.0)  # Cap at 2.0
    
    def _get_chunk_type_distribution(self, chunks: List[Dict]) -> Dict[str, int]:
        """Get distribution of chunk types for analysis"""
        distribution = {}
        for chunk in chunks:
            chunk_type = chunk['chunk_type']
            distribution[chunk_type] = distribution.get(chunk_type, 0) + 1
        return distribution
    
    def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query with enhanced ranking"""
        if self.collection is None:
            print("⚠️ ChromaDB collection not found. Please run embeddings setup first.")
            return []
        
        try:
            # Query the collection with increased results for re-ranking
            initial_results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k * 2, 20)  # Get more results for re-ranking
            )
            
            # Format and re-rank results
            context_chunks = []
            if initial_results['documents'] and len(initial_results['documents']) > 0:
                for i, doc in enumerate(initial_results['documents'][0]):
                    metadata = initial_results['metadatas'][0][i] if initial_results['metadatas'] else {}
                    distance = initial_results['distances'][0][i] if initial_results['distances'] else 0
                    
                    # Calculate combined score (semantic importance + similarity)
                    semantic_score = metadata.get('semantic_score', 1.0)
                    similarity_score = max(0, 1 - distance)  # Convert distance to similarity
                    combined_score = similarity_score * semantic_score
                    
                    context_chunks.append({
                        'content': doc,
                        'metadata': metadata,
                        'distance': distance,
                        'semantic_score': semantic_score,
                        'combined_score': combined_score,
                        'section_path': self._build_section_path_enhanced(metadata)
                    })
                
                # Re-rank by combined score and return top_k
                context_chunks.sort(key=lambda x: x['combined_score'], reverse=True)
                context_chunks = context_chunks[:top_k]
            
            print(f"🔍 Retrieved {len(context_chunks)} relevant chunks for query")
            return context_chunks
            
        except Exception as e:
            print(f"❌ Error retrieving context: {str(e)}")
            return []
    
    def _build_section_path_enhanced(self, metadata: Dict) -> str:
        """Build enhanced section path from metadata"""
        full_path = metadata.get('full_header_path', '')
        if full_path:
            return full_path
        
        section = metadata.get('section', '')
        subsection = metadata.get('subsection', '')
        
        if subsection and subsection != section:
            return f"{section} > {subsection}"
        return section
    
    def search_by_category(self, query: str, chunk_type: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for specific chunk types with enhanced filtering"""
        if self.collection is None:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"chunk_type": chunk_type}
            )
            
            context_chunks = []
            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    context_chunks.append({
                        'content': doc,
                        'metadata': metadata,
                        'distance': results['distances'][0][i] if results['distances'] else 0,
                        'section_path': self._build_section_path_enhanced(metadata)
                    })
            
            return context_chunks
            
        except Exception as e:
            print(f"❌ Error in category search: {str(e)}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the knowledge base"""
        if self.collection is None:
            return {"error": "Collection not found"}
        
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": self.config.COLLECTION_NAME,
                "embedding_model": self.config.EMBEDDING_MODEL,
                "version": "enhanced_v2"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_sections_overview(self) -> Dict[str, Any]:
        """Get comprehensive overview of knowledge base structure"""
        if self.collection is None:
            return {"error": "Collection not found"}
        
        try:
            # Get all documents to analyze structure
            results = self.collection.get()
            
            if not results['metadatas']:
                return {"error": "No metadata found"}
            
            # Analyze structure
            sections = {}
            chunk_types = {}
            header_levels = {}
            semantic_scores = []
            
            for metadata in results['metadatas']:
                section = metadata.get('section', 'Unknown')
                chunk_type = metadata.get('chunk_type', 'general')
                header_level = metadata.get('header_level', 1)
                semantic_score = metadata.get('semantic_score', 1.0)
                full_path = metadata.get('full_header_path', section)
                
                # Count sections
                if section not in sections:
                    sections[section] = {'total': 0, 'paths': set()}
                sections[section]['total'] += 1
                sections[section]['paths'].add(full_path)
                
                # Count chunk types
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
                
                # Count header levels
                header_levels[f"Level {header_level}"] = header_levels.get(f"Level {header_level}", 0) + 1
                
                # Collect semantic scores
                semantic_scores.append(semantic_score)
            
            # Convert sets to lists for JSON serialization
            for section_data in sections.values():
                section_data['paths'] = list(section_data['paths'])
            
            avg_semantic_score = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0
            
            return {
                "total_chunks": len(results['metadatas']),
                "sections": sections,
                "chunk_types": chunk_types,
                "header_levels": header_levels,
                "average_semantic_score": round(avg_semantic_score, 3),
                "collection_name": self.config.COLLECTION_NAME,
                "version": "enhanced_v2"
            }
            
        except Exception as e:
            return {"error": str(e)}