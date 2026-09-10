# KFMS - Knowledge Flow Management System

Natural language to SQL query service with PostgreSQL and Excel support, powered by LLM (Ollama + Groq).

## 🚀 Features

- **Natural Language → SQL**: Ask questions in plain language, get SQL-powered answers
- **Multi-Database Support**: Connect and query multiple PostgreSQL databases
- **Excel Integration**: Upload Excel files and query them like database tables
- **Dual LLM Support**: Switch between Ollama (local, free) and Groq (cloud, fast)
- **Read-Only Mode**: Safe query execution with validation and confirmation
- **Smart Visualization**: LLM-recommended charts (Bar, Line, Pie)
- **Query History**: Searchable history with re-run capability

## 🏗️ Architecture

```
Frontend (Vue 3)  ←→  REST API  ←→  Backend (FastAPI)
                                      ↓
                            LLM Providers (Ollama/Groq)
                                      ↓
                      PostgreSQL (metadata + user databases)
```

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Ollama (optional, for local LLM)
- Groq API Key (optional, for cloud LLM)

## 🛠️ Installation

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and API keys

# Run database migrations
alembic upgrade head

# Start server
python -m app.main
# or
uvicorn app.main:app --reload
```

Backend will run at: `http://localhost:8000`

API Documentation: `http://localhost:8000/api/docs`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env if backend URL is different

# Start development server
npm run dev
```

Frontend will run at: `http://localhost:5173`

## 📚 API Endpoints

### Query Operations
- `POST /api/v1/query/generate` - Generate SQL from natural language
- `POST /api/v1/query/validate` - Validate SQL safety
- `POST /api/v1/query/execute` - Execute query with confirmation

### Database Management
- `GET /api/v1/databases` - List connections
- `POST /api/v1/databases` - Add connection
- `GET /api/v1/databases/{id}/schema` - Get schema
- `DELETE /api/v1/databases/{id}` - Remove connection

### Excel Processing
- `POST /api/v1/excel/upload` - Upload Excel file
- `GET /api/v1/excel/uploads` - List uploads
- `DELETE /api/v1/excel/{id}` - Delete upload

### History
- `GET /api/v1/history` - Query history with filters
- `GET /api/v1/history/{id}` - Single record
- `DELETE /api/v1/history/{id}` - Delete record

## 🔧 Configuration

### Environment Variables (Backend)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kfms_meta

# LLM Provider ('ollama' or 'groq')
LLM_PROVIDER=ollama

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Groq (Cloud)
GROQ_API_KEY=your_api_key
GROQ_MODEL=mixtral-8x7b-32768

# Security
FERNET_KEY=your_fernet_key_here
```

Generate Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm run test
```

## 📦 Project Structure

```
kfms/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── api/      # REST endpoints
│   │   ├── services/ # Business logic
│   │   ├── llm/      # LLM provider abstraction
│   │   ├── db/       # Database models and repositories
│   │   └── utils/    # SQL validation, scheduler
│   ├── alembic/      # Database migrations
│   └── tests/
├── frontend/         # Vue 3 application
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/   # Pinia state management
│   │   └── services/ # API client
│   └── public/
├── docs/             # PDCA documentation
└── README.md
```

## 🔐 Security

- **Read-Only Mode**: Enforced by default, blocks destructive SQL
- **Query Validation**: User confirmation before execution
- **Encrypted Credentials**: Database passwords encrypted with Fernet
- **CORS Protection**: Configured allowed origins
- **Input Validation**: Pydantic models for request validation

## 🎯 Roadmap

- [x] Week 1: Foundation (Backend + Frontend skeleton)
- [ ] Week 2: Database management + LLM integration
- [ ] Week 3: Core query flow with validation
- [ ] Week 4: Excel processing + Visualization
- [ ] Week 5: History + Polish

## 🤝 Contributing

This is a personal project. For major changes, please open an issue first.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- FastAPI for the amazing async framework
- Vue.js for the reactive UI framework
- Ollama for local LLM capabilities
- Groq for blazing-fast cloud inference
