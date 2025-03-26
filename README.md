Here's the README.md without code blocks:

# RAG Chatbot

A powerful AI chatbot that uses Retrieval-Augmented Generation (RAG) to provide accurate, context-aware responses based on your documents.

## Features

- 📄 Document Processing (PDF, TXT, DOCX)
- 🤖 Intelligent Chat with RAG
- 🔌 Multiple AI Providers (OpenAI, Google)
- 🔒 Secure Authentication
- 🚀 REST API Support
- ⚡ Real-time Updates

## Prerequisites

- Python 3.9+
- PostgreSQL
- Poetry (Python dependency management)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rag-chatbot.git
   cd rag-chatbot
   ```

2. Install Poetry (if not installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies using Poetry:
   ```bash
   poetry install
   poetry shell
   ```

4. Create a .env file in the root directory:
   ```env
   # Database
   DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/rag_doc_chatbot
   
   # Security
   SECRET_KEY=your-secret-key-here
   FERNET_SECRET_KEY=your-fernet-key-here
   
   # Project Settings
   PROJECT_NAME=RAG Chatbot
   API_V1_STR=/api/v1
   ```

   To generate FERNET_SECRET_KEY, run this in Python:
   ```python
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   ```
   
   Or use this one-liner in terminal:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

5. Initialize the database:
   ```bash
   alembic upgrade head
   ```

## Running the Application

1. Start the FastAPI server:
   ```bash
   poetry run uvicorn main:app --reload --port 8080
   ```

2. Open your browser and navigate to:
   - Web Interface: http://localhost:8080
   - API Documentation: http://localhost:8080/docs

## API Configuration

### Setting up AI Providers

1. Get your API keys:
   - OpenAI: https://platform.openai.com/api-keys
   - Google AI: https://makersuite.google.com/app/apikey

2. Configure your API keys through:
   - API endpoint: POST /api/v1/auth/api-keys
   - Or through the web interface settings

## Usage

1. Register a new account
2. Log in to access the dashboard
3. Configure your AI provider preferences
4. Upload documents
5. Start chatting with context-aware responses


## API Endpoints

### Authentication
- POST `/api/v1/login` - User login
- POST `/api/v1/register` - User registration
- GET `/api/v1/me` - Get current user
- POST `/api/v1/api-keys` - Save API keys
- GET `/api/v1/api-keys` - Get API keys

### Documents
- POST `/api/v1/documents/upload` - Upload document
- GET `/api/v1/documents` - List documents
- DELETE `/api/v1/documents/{id}` - Delete document
- GET `/api/v1/documents/{id}/status` - Get processing status

### Chat
- POST `/api/v1/chat` - Send message
- GET `/api/v1/sessions` - List chat sessions
- DELETE `/api/v1/sessions/{id}` - Delete chat session


### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "migration_description"
```

Apply migrations:
```bash
alembic upgrade head
```

## Contributing

1. Fork the repository
2. Create your feature branch (git checkout -b feature/AmazingFeature)
3. Commit your changes (git commit -m 'Add some AmazingFeature')
4. Push to the branch (git push origin feature/AmazingFeature)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.



# Mac Installation
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustc --version
poetry run pip install --upgrade pip setuptools
poetry cache clear --all pypi
poetry install

