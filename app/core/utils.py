from ftfy import fix_text
from langchain.text_splitter import RecursiveCharacterTextSplitter


def sanitize_text(text: str) -> str:
    """
    Clean text by removing null bytes, non-printable characters, and fixing encoding issues.
    """
    # Fix text encoding issues
    text = fix_text(text)
    # Remove null bytes and other problematic characters
    text = text.replace('\x00', ' ')
    # Remove other non-printable characters
    text = ''.join(c for c in text if c.isprintable() or c in {'\n', '\t'})
    return text.strip()


def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """
    Split text into chunks using LangChain's text splitter.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)
