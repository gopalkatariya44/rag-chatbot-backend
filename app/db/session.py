from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from langchain_community.vectorstores.pgvector import PGVector
import psycopg2

from app.core.config import settings

# Create an async database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

# Create a session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
Base = declarative_base()


async def init_db():
    """Initialize database with required extensions and tables."""
    async with engine.begin() as conn:
        # Create pgvector extension if it doesn't exist
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
        
        # Convert async URL to sync URL for PGVector
        connection_string = str(settings.DATABASE_URL)
        if connection_string.startswith('postgresql+asyncpg://'):
            connection_string = connection_string.replace('postgresql+asyncpg://', 'postgresql://')
        
        # Create tables using raw SQL
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cur:
                # Create the collection table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS langchain_vectors (
                        id BIGSERIAL PRIMARY KEY,
                        collection_id TEXT,
                        embedding vector(1536),
                        document TEXT,
                        metadata JSONB,
                        cmetadata JSONB,
                        custom_id TEXT
                    );
                    CREATE INDEX IF NOT EXISTS langchain_vectors_collection_id_idx 
                        ON langchain_vectors (collection_id);
                    CREATE INDEX IF NOT EXISTS langchain_vectors_embedding_idx 
                        ON langchain_vectors USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100);
                """)
                conn.commit()

async def get_db():
    """Dependency to get an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
