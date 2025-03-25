from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.utils import sanitize_text, split_text_into_chunks
from app.db.repositories.documents import DocumentRepository
from app.services.model_factory import ModelFactory


class DocumentProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.document_repo = DocumentRepository(db)

    async def process_document(self, document_id: UUID, user_id: UUID):
        """
        Process a document by extracting text, splitting it into chunks, generating embeddings,
        and storing the chunks in the database.
        """
        try:
            # Get document with user preferences and API keys
            document = await self.document_repo.get_document_with_user(document_id)
            if not document or document.user_id != user_id:
                logger.error(f"Document {document_id} not found or access denied")
                return

            # Ensure user, model_preferences, and API keys exist
            if not document.user or not document.user.model_preferences or not document.user.api_keys:
                logger.error(f"User, model preferences, or API keys not found for document {document_id}")
                return

            # Get the API key for the provider
            provider = document.user.model_preferences.provider
            api_key = next(
                (key.decrypted_key for key in document.user.api_keys if key.provider == provider),
                None
            )
            if not api_key:
                logger.error(f"No API key found for provider: {provider}")
                return

            # Update document status to "processing"
            await self.document_repo.update_status(document_id, "processing")

            # Extract text from the document
            try:
                text = await self._parse_document(document.file_path, document.file_type)
            except Exception as e:
                logger.error(f"Failed to parse document {document_id}: {str(e)}")
                await self.document_repo.update_status(document_id, "failed")
                return

            # Split text into chunks
            chunks = split_text_into_chunks(text)

            # Get embedding model
            embedding_model = ModelFactory.get_embedding_model(
                provider=provider,
                api_key=api_key,
                model_name=document.user.model_preferences.embedding_model
            )

            # Generate embeddings for each chunk
            try:
                embeddings = await embedding_model.aembed_documents(chunks)
            except Exception as e:
                logger.error(f"Failed to generate embeddings for document {document_id}: {str(e)}")
                await self.document_repo.update_status(document_id, "failed")
                return

            # Store chunks and embeddings in the database
            try:
                await self.document_repo.bulk_create_chunks(
                    document_id=document_id,
                    chunks=chunks,
                    embeddings=embeddings
                )
            except Exception as e:
                logger.error(f"Failed to store chunks for document {document_id}: {str(e)}")
                await self.document_repo.update_status(document_id, "failed")
                return

            # Update document status to "processed"
            await self.document_repo.update_status(document_id, "processed")
            logger.info(f"Document {document_id} processed successfully")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            await self.document_repo.update_status(document_id, "failed")
            raise

    async def _parse_document(self, file_path: str, file_type: str) -> str:
        """
        Parse document content based on file type.
        """
        if file_type == "text/plain":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif file_type == "application/pdf":
            text = self._parse_pdf(file_path)
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = self._parse_docx(file_path)
        else:
            raise ValueError("Unsupported file type")

        return sanitize_text(text)

    def _parse_pdf(self, file_path: str) -> str:
        """
        Extract text from a PDF file.
        """
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            text = "\n".join(page.extract_text() for page in reader.pages)
            return text
        except Exception as e:
            logger.error(f"Failed to parse PDF: {str(e)}")
            raise

    def _parse_docx(self, file_path: str) -> str:
        """
        Extract text from a DOCX file.
        """
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text
        except Exception as e:
            logger.error(f"Failed to parse DOCX: {str(e)}")
            raise
