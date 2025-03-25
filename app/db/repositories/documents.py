from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logger import logger
from app.core.utils import sanitize_text
from app.db.models import Document, DocumentChunk, User


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_documents_by_user(self, user_id: UUID, status: str = None):
        query = select(Document).filter(Document.user_id == user_id)
        if status:
            query = query.filter(Document.status == status)
        query = query.order_by(Document.uploaded_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_document_with_user(self, document_id: UUID):
        """
        Fetch a document with its associated user and preferences.
        """
        result = await self.db.execute(
            select(Document)
            .options(
                selectinload(Document.user)
                .selectinload(User.model_preferences),
                selectinload(Document.user)
                .selectinload(User.api_keys)
            )
            .filter(Document.id == document_id)
        )
        return result.scalars().first()

    async def create_document(self, filename: str, file_type: str, user_id: UUID, file_path: str):
        """
        Create a new document record.
        """
        new_document = Document(
            filename=filename,
            file_type=file_type,
            user_id=user_id,
            file_path=file_path,
            status="pending"
        )
        self.db.add(new_document)
        await self.db.commit()
        await self.db.refresh(new_document)
        return new_document

    async def update_status(self, document_id: UUID, status: str):
        """
        Update the status of a document.
        """
        document = await self.db.get(Document, document_id)
        if document:
            document.status = status
            await self.db.commit()

    async def bulk_create_chunks(self, document_id: UUID, chunks: list[str], embeddings: list[list[float]]):
        """
        Insert multiple chunks into the database with error handling.
        """
        chunk_objects = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                clean_chunk = sanitize_text(chunk)
                if not clean_chunk:
                    continue

                chunk_objects.append({
                    "document_id": document_id,
                    "chunk_text": clean_chunk,
                    "embedding": embedding,
                    "chunk_index": idx
                })
            except Exception as e:
                logger.error(f"Error processing chunk {idx}: {str(e)}")
                continue

        if chunk_objects:
            await self.db.execute(DocumentChunk.__table__.insert(), chunk_objects)
            await self.db.commit()

    async def delete_document(self, document_id: UUID):
        """
        Delete a document and its associated chunks.
        """
        await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self.db.execute(
            delete(Document).where(Document.id == document_id)
        )
        await self.db.commit()
        return True
