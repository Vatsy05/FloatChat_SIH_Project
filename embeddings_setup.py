"""
Enhanced Embeddings Setup Script for ARGO FloatChat AI
This script creates embeddings from the knowledge base using MarkdownHeaderTextSplitter
"""
import os
import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rag_system import ArgoRAGSystem
from config.settings import Config

def setup_embeddings(knowledge_base_path: str = "./data/improved_knowledge_base.md", 
                    force_rebuild: bool = False):
    """Setup embeddings for the knowledge base with enhanced processing"""
    
    print("🚀 Starting ARGO FloatChat AI Enhanced Embeddings Setup")
    print("=" * 60)
    
    try:
        # Validate configuration
        print("📋 Validating configuration...")
        config = Config()
        config.validate_config()
        
        # Initialize RAG system
        print("🔧 Initializing enhanced RAG system...")
        rag_system = ArgoRAGSystem()
        
        # Check if embeddings already exist
        stats = rag_system.get_collection_stats()
        
        if "total_chunks" in stats and stats["total_chunks"] > 0 and not force_rebuild:
            print(f"✅ Embeddings already exist ({stats['total_chunks']} chunks)")
            print(f"   Version: {stats.get('version', 'legacy')}")
            print("   Use --force-rebuild to recreate embeddings with enhanced processing")
            
            # Show overview
            show_knowledge_base_overview(rag_system)
            
            # Test retrieval
            print("\n🔍 Testing retrieval system...")
            test_retrieval_enhanced(rag_system)
            return True
        
        # Check if knowledge base file exists
        if not os.path.exists(knowledge_base_path):
            print(f"❌ Knowledge base file not found: {knowledge_base_path}")
            print("   Please ensure the improved_knowledge_base.md file is in the data/ directory")
            return False
        
        print(f"📚 Processing knowledge base: {knowledge_base_path}")
        
        # Show file stats
        with open(knowledge_base_path, 'r', encoding='utf-8') as f:
            content = f.read()
            line_count = content.count('\n')
            char_count = len(content)
            word_count = len(content.split())
        
        print(f"   📊 File stats: {line_count:,} lines, {word_count:,} words, {char_count:,} characters")
        
        # Create embeddings with enhanced processing
        print("🔄 Creating embeddings with MarkdownHeaderTextSplitter...")
        print("   This process includes:")
        print("   • Header-aware document splitting")
        print("   • Intelligent chunking with overlap")
        print("   • Semantic importance scoring")
        print("   • Enhanced metadata extraction")
        print()
        
        num_chunks = rag_system.create_embeddings_from_file(knowledge_base_path)
        
        print(f"\n✅ Successfully created embeddings for {num_chunks} knowledge chunks")
        
        # Verify embeddings with detailed stats
        print("\n🔍 Verifying enhanced embeddings...")
        stats = rag_system.get_collection_stats()
        print(f"   Total chunks: {stats.get('total_chunks', 0)}")
        print(f"   Collection: {stats.get('collection_name', 'Unknown')}")
        print(f"   Embedding model: {stats.get('embedding_model', 'Unknown')}")
        print(f"   Version: {stats.get('version', 'enhanced_v2')}")
        
        # Show knowledge base structure
        show_knowledge_base_overview(rag_system)
        
        # Test enhanced retrieval system
        print("\n🧪 Testing enhanced retrieval system...")
        test_retrieval_enhanced(rag_system)
        
        print("\n🎉 Enhanced embeddings setup completed successfully!")
        print("\nFeatures enabled:")
        print("  ✓ Header-aware document parsing")
        print("  ✓ Semantic importance scoring") 
        print("  ✓ Enhanced metadata tracking")
        print("  ✓ Intelligent chunk categorization")
        print("  ✓ Multi-level content hierarchy")
        print("\nNext step: Run the application with: streamlit run app.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during embeddings setup: {str(e)}")
        print(f"   Full error: {repr(e)}")
        return False

def show_knowledge_base_overview(rag_system: ArgoRAGSystem):
    """Show detailed overview of the knowledge base structure"""
    
    print("\n📋 Knowledge Base Structure Overview:")
    print("-" * 40)
    
    try:
        overview = rag_system.get_sections_overview()
        
        if "error" in overview:
            print(f"   ⚠️ Could not load overview: {overview['error']}")
            return
        
        print(f"   Total chunks: {overview.get('total_chunks', 0)}")
        
        # Show chunk type distribution
        chunk_types = overview.get('chunk_types', {})
        if chunk_types:
            print("   \n📊 Chunk Types:")
            for chunk_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / overview['total_chunks']) * 100
                print(f"     {chunk_type:12} {count:3d} chunks ({percentage:5.1f}%)")
        
        # Show header level distribution
        header_levels = overview.get('header_levels', {})
        if header_levels:
            print("   \n📑 Header Levels:")
            for level, count in sorted(header_levels.items()):
                percentage = (count / overview['total_chunks']) * 100
                print(f"     {level:8} {count:3d} chunks ({percentage:5.1f}%)")
        
        # Show semantic score info
        avg_score = overview.get('average_semantic_score', 0)
        if avg_score > 0:
            print(f"   \n⭐ Average semantic score: {avg_score}")
        
        # Show main sections
        sections = overview.get('sections', {})
        if sections:
            print("   \n📝 Main Sections:")
            for section, data in list(sections.items())[:5]:  # Show top 5 sections
                print(f"     {section:30} {data['total']:3d} chunks")
            
            if len(sections) > 5:
                print(f"     ... and {len(sections) - 5} more sections")
                
    except Exception as e:
        print(f"   ❌ Error showing overview: {str(e)}")

def test_retrieval_enhanced(rag_system: ArgoRAGSystem):
    """Enhanced testing of the retrieval system with detailed analysis"""
    
    test_queries = [
        ("Arabian Sea coordinates", "geography"),
        ("temperature salinity profiles", "examples"),
        ("BGC float parameters", "bgc"),
        ("SQL query examples", "examples"),
        ("database schema tables", "schema"),
        ("quality control flags", "quality"),
        ("array data handling", "rules")
    ]
    
    print("   Testing semantic retrieval with sample queries:")
    
    successful_retrievals = 0
    
    for query, expected_type in test_queries:
        try:
            results = rag_system.retrieve_context(query, top_k=3)
            if results:
                # Check if we got the expected type in top results
                top_types = [r['metadata'].get('chunk_type', 'unknown') for r in results[:2]]
                type_match = expected_type in top_types
                
                print(f"     {'✅' if type_match else '⚠️'} '{query}'")
                print(f"        → {len(results)} chunks, types: {top_types}")
                
                if results:
                    successful_retrievals += 1
            else:
                print(f"     ❌ '{query}' → No results")
        except Exception as e:
            print(f"     ❌ '{query}' → Error: {str(e)}")
    
    success_rate = (successful_retrievals / len(test_queries)) * 100
    print(f"   \n📊 Retrieval success rate: {success_rate:.1f}% ({successful_retrievals}/{len(test_queries)})")
    
    # Test category-specific search
    print("\n   Testing category-specific search:")
    categories = ["schema", "geography", "examples", "bgc", "rules"]
    
    category_success = 0
    
    for category in categories:
        try:
            results = rag_system.search_by_category("test query", category, top_k=2)
            if results:
                print(f"     ✅ Category '{category}' → {len(results)} chunks")
                category_success += 1
            else:
                print(f"     ⚠️ Category '{category}' → No results")
        except Exception as e:
            print(f"     ❌ Category '{category}' → Error: {str(e)}")
    
    category_success_rate = (category_success / len(categories)) * 100
    print(f"   \n📊 Category search success rate: {category_success_rate:.1f}% ({category_success}/{len(categories)})")

def reset_embeddings():
    """Reset/delete existing embeddings"""
    print("🗑️ Resetting embeddings...")
    
    try:
        config = Config()
        chroma_path = config.CHROMA_PERSIST_DIRECTORY
        
        if os.path.exists(chroma_path):
            import shutil
            shutil.rmtree(chroma_path)
            print(f"✅ Deleted existing ChromaDB at: {chroma_path}")
        else:
            print(f"ℹ️ No existing ChromaDB found at: {chroma_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting embeddings: {str(e)}")
        return False

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        ("chromadb", "chromadb"),
        ("sentence-transformers", "sentence_transformers"),
        ("langchain-text-splitters", "langchain_text_splitters"),
        ("numpy", "numpy")
    ]
    
    missing_packages = []
    
    for pip_name, import_name in required_packages:
        try:
            __import__(import_name.replace("-", "_"))
            print(f"   ✅ {pip_name}")
        except ImportError:
            print(f"   ❌ {pip_name} - Missing")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print("\n⚠️ Missing packages detected!")
        print("   Please install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All dependencies are installed")
    return True

def create_data_directory():
    """Create data directory structure if it doesn't exist"""
    data_dir = Path("data")
    chroma_dir = Path("data/chroma_db")
    
    if not data_dir.exists():
        data_dir.mkdir()
        print(f"📁 Created data directory: {data_dir}")
    
    if not chroma_dir.exists():
        chroma_dir.mkdir(parents=True)
        print(f"📁 Created ChromaDB directory: {chroma_dir}")
    
    return True

def validate_knowledge_base(file_path: str):
    """Validate the knowledge base file structure"""
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for basic markdown structure
        if not content.strip():
            return False, "File is empty"
        
        # Check for headers
        header_count = content.count('#')
        if header_count < 5:
            return False, "Insufficient markdown headers found"
        
        # Check for key sections
        required_sections = ['Database Architecture', 'Schema Reference', 'Query Templates']
        missing_sections = []
        for section in required_sections:
            if section.lower() not in content.lower():
                missing_sections.append(section)
        
        if missing_sections:
            return False, f"Missing required sections: {', '.join(missing_sections)}"
        
        return True, "Knowledge base validation passed"
        
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def main():
    """Main function for enhanced embeddings setup"""
    parser = argparse.ArgumentParser(
        description="Setup embeddings for ARGO FloatChat AI with enhanced processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python embeddings_setup.py                    # Standard setup
  python embeddings_setup.py --force-rebuild    # Force rebuild embeddings
  python embeddings_setup.py --reset            # Reset and rebuild
  python embeddings_setup.py --check-deps       # Check dependencies only
        """
    )
    
    parser.add_argument(
        "--knowledge-base", 
        type=str, 
        default="./data/improved_knowledge_base.md",
        help="Path to knowledge base file"
    )
    
    parser.add_argument(
        "--force-rebuild", 
        action="store_true",
        help="Force rebuild embeddings even if they exist"
    )
    
    parser.add_argument(
        "--reset", 
        action="store_true",
        help="Reset/delete existing embeddings before creating new ones"
    )
    
    parser.add_argument(
        "--check-deps", 
        action="store_true",
        help="Check dependencies only"
    )
    
    parser.add_argument(
        "--validate-only", 
        action="store_true",
        help="Validate knowledge base file only"
    )
    
    args = parser.parse_args()
    
    print("🌊 ARGO FloatChat AI - Enhanced Embeddings Setup")
    print("=" * 60)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Setup aborted due to missing dependencies")
        return False
    
    if args.check_deps:
        print("\n✅ Dependencies check completed successfully!")
        return True
    
    # Validate knowledge base if requested
    if args.validate_only:
        valid, message = validate_knowledge_base(args.knowledge_base)
        if valid:
            print(f"✅ {message}")
            return True
        else:
            print(f"❌ Validation failed: {message}")
            return False
    
    # Create directory structure
    create_data_directory()
    
    # Validate knowledge base file
    print("🔍 Validating knowledge base file...")
    valid, message = validate_knowledge_base(args.knowledge_base)
    if not valid:
        print(f"❌ Knowledge base validation failed: {message}")
        return False
    else:
        print(f"✅ {message}")
    
    # Reset embeddings if requested
    if args.reset:
        if reset_embeddings():
            print("✅ Embeddings reset successfully!")
        else:
            print("❌ Failed to reset embeddings")
            return False
    
    # Setup embeddings
    success = setup_embeddings(
        knowledge_base_path=args.knowledge_base,
        force_rebuild=args.force_rebuild
    )
    
    if success:
        print("\n🎉 Enhanced setup completed successfully!")
        print("\nNew features available:")
        print("  • Better semantic chunking with header awareness")
        print("  • Enhanced retrieval with importance scoring")
        print("  • Improved metadata for better context")
        print("  • Optimized chunk distribution")
        print("\nNext steps:")
        print("1. Set up your environment variables in .env")
        print("2. Run the application: streamlit run app.py")
        print("3. Try asking complex questions about ARGO data!")
        return True
    else:
        print("\n❌ Setup failed!")
        print("\nTroubleshooting:")
        print("1. Check that the knowledge base file exists and is valid")
        print("2. Verify all environment variables are set")
        print("3. Ensure all dependencies are installed")
        print("4. Try running with --reset to start fresh")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)