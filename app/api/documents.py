import os
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.repositories.documents import DocumentRepository
from app.db.session import get_db
from app.models.documents import DocumentOut
from app.models.users import UserOut
from app.tasks.document_tasks import process_document_task
from app.services.document_processor import process_document

router = APIRouter(tags=["Documents"])

# Add file size limit
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/upload")
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    try:
        # Check file size
        file_size = 0
        contents = await file.read()
        file_size = len(contents)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE/1024/1024}MB"
            )
        
        # Reset file pointer
        await file.seek(0)

        # Validate file type
        allowed_types = ["text/plain", "application/pdf",
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type",
            )

        # Save file
        file_path = f"uploads/{file.filename}"
        os.makedirs("uploads", exist_ok=True)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create document record
        doc_repo = DocumentRepository(db)
        document = await doc_repo.create_document(
            filename=file.filename,
            file_type=file.content_type,
            file_path=file_path,
            user_id=current_user.id
        )
        
        # Process document (split into chunks and create embeddings)
        await process_document(document, db, current_user)
        
        return {"message": "Document uploaded successfully", "document_id": document.id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(
        document_id: UUID,
        db: AsyncSession = Depends(get_db),
        current_user: UserOut = Depends(get_current_user),
):
    doc_repo = DocumentRepository(db)
    deleted = await doc_repo.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return {"detail": "Document deleted successfully"}


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
        status: str = Query(None, description="Filter by document status"),
        db: AsyncSession = Depends(get_db),
        current_user: UserOut = Depends(get_current_user),

):
    """
    List all documents for the authenticated user.
    """
    doc_repo = DocumentRepository(db)
    documents = await doc_repo.get_documents_by_user(current_user.id, status=status)
    return documents
