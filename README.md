# SkillCoach

An AI-powered coaching platform that delivers personalized coaching sessions using Claude AI, with comprehensive skill tracking, quota management, and analytics capabilities.

**Version:** 0.6.0 (Phase 6)

## Overview

SkillCoach is a FastAPI-based web application designed to help coaching organizations deliver structured, AI-enhanced coaching experiences. It supports multiple user roles (Head Coach, Coach, Client), manages coaching sessions, tracks skill development, and provides detailed reporting and analytics.

The platform integrates with Anthropic's Claude AI to deliver intelligent coaching responses based on predefined coaching skillsets and philosophies.

## Features

- **AI-Powered Coaching**: Interactive coaching sessions powered by Claude AI
- **User Management**: Role-based access control (Head Coach, Coach, Client)
- **Skill Tracking**: Organize and manage coaching skills across multiple categories
- **Quota Management**: Track token usage and manage coaching credits
- **Pricing Models**: Support for multiple AI models with configurable pricing
- **Reporting**: Generate comprehensive coaching reports and analytics
- **Coach Branding**: Customize coach profiles with logos, names, and branding
- **Web Interface**: Responsive HTML/CSS/JavaScript frontend
- **Authentication**: Secure JWT-based authentication
- **Database**: PostgreSQL for persistent data storage

## Tech Stack

- **Backend**: FastAPI 0.115.6
- **Server**: Uvicorn
- **Database**: PostgreSQL with SQLAlchemy ORM
- **AI**: Anthropic Claude API
- **Authentication**: Python-Jose with JWT
- **Frontend**: HTML5, CSS3, JavaScript
- **Containerization**: Docker

## Project Structure

```
skillcoach/
├── main.py                    # FastAPI app entry point, DB initialization
├── auth.py                    # Authentication and password hashing
├── database.py                # SQLAlchemy models and DB connection
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
├── .env.example               # Environment variables template
├── routers/                   # API route modules
│   ├── auth_routes.py         # Login, registration, token management
│   ├── admin_routes.py        # Admin operations
│   ├── coach_routes.py        # Coach dashboard and management
│   ├── chat_routes.py         # Chat and coaching session endpoints
│   └── reports_routes.py      # Report generation and analytics
├── services/                  # Business logic services
│   ├── claude_service.py      # Claude AI integration
│   ├── pricing_service.py     # Pricing calculations
│   └── quota_service.py       # Token and quota management
└── static/                    # Frontend assets
    ├── login.html             # Login page
    ├── client.html            # Client dashboard
    ├── coach.html             # Coach dashboard
    ├── headcoach.html         # Head Coach admin interface
    ├── css/style.css          # Styling
    └── js/                    # JavaScript files
        ├── api.js             # API communication
        ├── chat.js            # Chat interface
        ├── headcoach_bulk.js  # Bulk operations
        └── reports.js         # Reporting interface
```

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Anthropic API key

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd skillcoach
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your configuration:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/skillcoach
   ANTHROPIC_API_KEY=your_api_key_here
   HEADCOACH_EMAIL=headcoach@example.com
   HEADCOACH_PASSWORD=secure_password
   HEADCOACH_NAME=Head Coach
   ```

5. **Initialize database**
   ```bash
   python main.py
   ```

## Running the Application

### Development

```bash
uvicorn main:app --reload
```

The app will be available at `http://127.0.0.1:8000`

- API Documentation: `http://127.0.0.1:8000/docs` (Swagger UI)
- ReDoc: `http://127.0.0.1:8000/redoc`

### Production

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker

```bash
docker build -t skillcoach .
docker run -p 8000:8000 --env-file .env skillcoach
```

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - Login and get JWT token
- `POST /auth/logout` - Logout
- `POST /auth/refresh` - Refresh JWT token

### Coaching
- `POST /coach/chat` - Send a coaching message
- `GET /coach/sessions` - Get coaching session history
- `GET /coach/skills` - List available coaching skills
- `GET /coach/profile` - Get coach profile

### Admin
- `GET /admin/users` - List all users
- `POST /admin/users` - Create new user
- `PUT /admin/users/{user_id}` - Update user
- `DELETE /admin/users/{user_id}` - Delete user

### Reports
- `GET /reports/coaching` - Generate coaching report
- `GET /reports/analytics` - Get analytics and metrics
- `GET /reports/export` - Export reports

## Database Schema

### Core Tables
- **users** - User accounts with roles (head_coach, coach, client)
- **skills** - Coaching skills and their categorization
- **categories** - Skill categories (Strategy, Culture, Operations, etc.)
- **chat_sessions** - Coaching chat session history
- **coaching_reports** - Generated coaching reports
- **model_options** - AI model configurations and pricing
- **quotas** - User token quotas and usage

## Available AI Models

1. **Haiku** (Default)
   - Fast and economical
   - Input: 1.0/MTok, Output: 5.0/MTok

2. **Sonnet**
   - Balanced intelligence and speed
   - Input: 3.0/MTok, Output: 15.0/MTok

## Coaching Skillsets

The platform includes structured coaching skillsets based on coaching philosophies:

- **Hiring A Digital Marketing Agency** - Guidance on selecting and managing marketing agencies
- **Irresistible Offers AI Coaching** - Coaching on creating compelling offers

Each skillset contains 20 guided questions that build towards a personalized coaching report.

## User Roles

### Head Coach
- Full admin access
- Manage all coaches and clients
- View platform analytics
- Configure system settings

### Coach
- Manage assigned clients
- Conduct coaching sessions
- Track client progress
- Generate personalized reports

### Client
- Participate in coaching sessions
- Track personal progress
- View coaching reports
- Manage profile

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `HEADCOACH_EMAIL` | Initial head coach email | Yes |
| `HEADCOACH_PASSWORD` | Initial head coach password | Yes |
| `HEADCOACH_NAME` | Head coach display name | No |
| `JWT_SECRET_KEY` | JWT signing key | Yes |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) | No |

## Development

### Running Tests
```bash
pytest
```

### Code Style
The project uses standard Python conventions. Format code with:
```bash
black .
```

### Database Migrations
Database schema is initialized automatically on startup via `init_db()`.

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check `DATABASE_URL` is correct
- Verify user credentials and permissions

### Missing AI Responses
- Verify `ANTHROPIC_API_KEY` is set correctly
- Check user's token quota
- Review Claude API status

### Authentication Errors
- Ensure `JWT_SECRET_KEY` is configured
- Check token hasn't expired
- Verify user account is active

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

[Add your license information here]

## Support

For issues, questions, or feature requests, please contact the development team.

---

**Built with ❤️ using FastAPI + Claude AI by aitamate Solutions** (www.aitamate.com)
