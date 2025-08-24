# Flask Resume Builder

A secure, production-ready Flask application for building professional resumes using AI assistance.

## 🚀 New Features & Security Improvements

### 🔐 User Authentication (NEW!)
- **Supabase Auth integration** with email magic links and Google OAuth
- **Secure session management** with Flask sessions
- **Route protection** - all pages except landing, login, and signup require authentication
- **Automatic redirects** for unauthenticated users
- **Clean separation** of auth logic for easy database integration later

### 1. Centralized Configuration (`config.py`)
- **Environment-based configuration** using `python-dotenv`
- **Fallback to system environment variables** for production deployments
- **Centralized settings** for all API keys, secrets, and configuration values
- **Automatic validation** of required environment variables

### 2. Enhanced Security
- **Input sanitization** to prevent XSS attacks
- **Input validation** with configurable limits
- **Rate limiting** using Flask-Limiter
  - Default routes: 100 requests per minute
  - AI routes: 10 requests per minute
- **Secure session management** with configurable secret keys

### 3. AI Client Service (`services/ai_client.py`)
- **Intelligent caching** with 10-minute TTL
- **Automatic retries** with exponential backoff and jitter
- **Error handling** and graceful degradation
- **Configurable timeouts** and token limits
- **JSON schema enforcement** for consistent responses

### 4. Enhanced Logging System
- **Dual logging**: Google Sheets + Local JSON files
- **Graceful fallback** when Google Sheets credentials are unavailable
- **Structured JSON logs** with timestamps
- **Automatic log directory creation**

### 5. Input Validation (`validators.py`)
- **Text sanitization** for XSS prevention
- **Story validation**: 80-2000 characters
- **Answer validation**: 1-500 characters
- **Experience type validation** with predefined categories

### 6. User Authentication (`services/supabase_client.py`)
- **Supabase Auth integration** with email magic links and Google OAuth
- **Secure session management** with Flask sessions
- **Route protection** for authenticated users only
- **Automatic redirects** for unauthenticated users
- **Clean separation** of auth logic for easy database integration later

## 📁 Project Structure

```
resume-builder/
├── app.py                 # Main Flask application
├── config.py             # Configuration management
├── validators.py         # Input validation and sanitization
├── google_log.py         # Logging system (Google Sheets + JSON)
├── services/
│   ├── ai_client.py     # AI service wrapper with caching
│   └── supabase_client.py # Supabase authentication client
├── templates/            # HTML templates
│   ├── login.html        # Login page
│   ├── signup.html       # Signup page
│   └── ...               # Other templates
├── logs/                 # JSON log files
├── requirements.txt      # Python dependencies
├── README_AUTH.md        # Authentication setup guide
└── README.md            # This file
```

## 🛠️ Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and configure your environment variables:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```env
# Required
APP_SECRET_KEY=your-super-secret-key-change-in-production
OPENAI_API_KEY=your-openai-api-key-here
SUPABASE_URL=your-supabase-project-url-here
SUPABASE_ANON_KEY=your-supabase-anon-key-here

# Optional (with defaults)
OPENAI_MODEL=gpt-4o-mini
AI_MAX_TOKENS=2000
AI_TIMEOUT_SECONDS=30
SESSION_TYPE=filesystem
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/your-sheet-id-here/edit
GOOGLE_CREDENTIALS_PATH=credentials.json
RATE_LIMIT_DEFAULT=100 per minute
RATE_LIMIT_AI=10 per minute
LOGS_DIR=logs
```

### 3. Google Sheets Setup (Optional)
1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a service account
4. Download credentials JSON file
5. Share your Google Sheet with the service account email
6. Set `GOOGLE_CREDENTIALS_PATH` and `GOOGLE_SHEET_URL` in `.env`

### 4. Authentication Setup
The application now includes user authentication using Supabase Auth. See [README_AUTH.md](README_AUTH.md) for detailed setup instructions.

**Quick Setup:**
1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Add your Supabase URL and anon key to `.env`
3. Configure Google OAuth in Supabase (optional)
4. Set a secure `APP_SECRET_KEY` in `.env`

### 5. Test Configuration
```bash
python test_config.py
```

### 5. Run the Application
```bash
python app.py
```

## 🔒 Security Features

### Rate Limiting
- **Default routes**: 100 requests per minute per IP
- **AI processing routes**: 10 requests per minute per IP
- **Configurable limits** via environment variables

### Input Validation
- **XSS Prevention**: HTML escaping and script removal
- **Length Limits**: Configurable min/max character limits
- **Content Sanitization**: Removal of malicious content

### Error Handling
- **Graceful degradation** when AI services are unavailable
- **User-friendly error messages** without exposing system details
- **Comprehensive logging** for debugging and monitoring

## 📊 Logging & Monitoring

### JSON Logs
- **Location**: `./logs/{YYYY-MM-DD_HHMMSS}.json`
- **Format**: Structured JSON with timestamps
- **Content**: All user interactions and AI responses

### Google Sheets Logs
- **Fallback**: Automatically falls back to JSON if unavailable
- **Data**: User experiences, AI responses, and follow-up answers
- **Format**: Structured spreadsheet with timestamps

## 🚀 Production Deployment

### Environment Variables
- **Never commit** `.env` files to version control
- **Use system environment variables** in production
- **Rotate secrets** regularly
- **Use strong secret keys** for production

### Security Checklist
- [ ] Set strong `APP_SECRET_KEY`
- [ ] Configure production `OPENAI_API_KEY`
- [ ] Set strong `SUPABASE_ANON_KEY` and verify `SUPABASE_URL`
- [ ] Configure Google OAuth in Supabase (if using)
- [ ] Set appropriate rate limits
- [ ] Enable HTTPS in production
- [ ] Configure proper logging levels
- [ ] Set up monitoring and alerting
- [ ] Review Supabase authentication logs regularly

### Performance Considerations
- **AI Client Caching**: 10-minute TTL reduces API calls
- **Rate Limiting**: Prevents abuse and ensures fair usage
- **Error Handling**: Graceful degradation maintains user experience

## 🔧 Configuration Options

### OpenAI Settings
- `OPENAI_MODEL`: AI model to use (default: gpt-4o-mini)
- `AI_MAX_TOKENS`: Maximum tokens per request (default: 2000)
- `AI_TIMEOUT_SECONDS`: Request timeout (default: 30)

### Rate Limiting
- `RATE_LIMIT_DEFAULT`: Default rate limit (default: 100 per minute)
- `RATE_LIMIT_AI`: AI route rate limit (default: 10 per minute)

### Logging
- `LOGS_DIR`: Directory for JSON logs (default: logs)
- `GOOGLE_CREDENTIALS_PATH`: Path to Google service account credentials
- `GOOGLE_SHEET_URL`: Google Sheets URL for logging

## 🐛 Troubleshooting

### Common Issues

1. **Configuration Errors**
   ```bash
   python test_config.py
   ```

2. **Missing Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Google Sheets Issues**
   - Check credentials file path
   - Verify sheet sharing permissions
   - Check API quotas

4. **Rate Limiting**
   - Check current limits in configuration
   - Monitor logs for rate limit errors

## 📝 Changelog

### v2.0.0 - Security & Configuration Overhaul
- ✅ Centralized configuration management
- ✅ Input validation and sanitization
- ✅ Rate limiting with Flask-Limiter
- ✅ Enhanced AI client with caching and retries
- ✅ Dual logging system (Google Sheets + JSON)
- ✅ Comprehensive error handling
- ✅ Production-ready security features

### v1.0.0 - Initial Release
- Basic Flask resume builder
- OpenAI integration
- Google Sheets logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
