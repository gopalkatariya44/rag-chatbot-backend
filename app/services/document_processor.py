from typing import List
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.db.models import Document
from app.models.users import UserOut
from app.services.vector_store import get_vector_store
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def process_document(document: Document, db: AsyncSession, user: UserOut):
    """Process a document: load, split into chunks, create embeddings"""
    try:
        print(f"\n=== Processing Document ===")
        print(f"Document ID: {document.id}")
        print(f"User ID: {user.id}")
        print(f"Filename: {document.filename}")
        print(f"File type: {document.file_type}")
        
        # Load document based on file type
        if document.file_type == "application/pdf":
            loader = PyPDFLoader(document.file_path)
        elif document.file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            loader = Docx2txtLoader(document.file_path)
        else:
            loader = TextLoader(document.file_path)
            
        pages = loader.load()
        print(f"Loaded {len(pages)} pages from document")
        
        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(pages)
        print(f"Split into {len(chunks)} chunks")
        
        # Get vector store
        vector_store = await get_vector_store(db, user.id)
        
        # Debug: Print first chunk metadata
        print("\n=== Adding Chunks with Metadata ===")
        metadata_example = {
            "document_id": str(document.id),
            "chunk_index": 0,
            "source": document.filename,
            "user_id": str(user.id),
            "file_type": document.file_type
        }
        print(f"Example metadata: {metadata_example}")
        
        # Add chunks to vector store with metadata
        print("\nAdding chunks to vector store...")
        await vector_store.aadd_texts(
            texts=[chunk.page_content for chunk in chunks],
            metadatas=[{
                "document_id": str(document.id),
                "chunk_index": i,
                "source": document.filename,
                "user_id": str(user.id),
                "file_type": document.file_type
            } for i, chunk in enumerate(chunks)]
        )
        print(f"Successfully added {len(chunks)} chunks to vector store")
        
        # Verify chunks were added
        result = await db.execute(
            text("""
                SELECT COUNT(*), array_agg(DISTINCT cmetadata->>'document_id') as doc_ids
                FROM langchain_pg_embedding 
                WHERE cmetadata->>'document_id' = :doc_id
            """),
            {"doc_id": str(document.id)}
        )
        row = result.fetchone()
        print(f"\n=== Verification ===")
        print(f"Found {row[0]} chunks in database for document {document.id}")
        print(f"Document IDs in metadata: {row[1]}")
        
        # Update document status
        document.processed = True
        document.status = "completed"
        await db.commit()
        print(f"\nDocument {document.id} processing completed successfully")
        
    except Exception as e:
        print(f"Error processing document {document.id}: {str(e)}")
        document.status = "failed"
        await db.commit()
        raise e 