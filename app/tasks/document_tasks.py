from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.services.documents import DocumentProcessor


async def process_document_task(document_id: UUID, user_id: UUID):
    """
    Background task to process a document.
    """
    db = AsyncSessionLocal()
    try:
        processor = DocumentProcessor(db)
        await processor.process_document(document_id, user_id)
    except Exception as e:
        # Log the error
        print(f"Error processing document {document_id}: {str(e)}")
    finally:
        await db.close()
