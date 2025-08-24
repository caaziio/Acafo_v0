# Authentication Setup Guide

This project now includes user authentication using Supabase Auth with the following features:

## Features
- Email magic link sign-in
- Google OAuth sign-in
- Secure Flask sessions
- Route protection for authenticated users
- Automatic redirects for unauthenticated users

## Required Environment Variables

Create a `.env` file in your project root with the following variables:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Flask Configuration
APP_SECRET_KEY=your_secure_secret_key_here_change_in_production
SESSION_TYPE=filesystem

# OpenAI API (existing)
OPENAI_API_KEY=your_openai_api_key_here

# Google Sheets (existing)
GOOGLE_SHEET_URL=your_google_sheet_url_here
GOOGLE_CREDENTIALS_PATH=credentials.json
```

## Supabase Setup

1. Go to [supabase.com](https://supabase.com) and create a new project
2. In your project dashboard, go to Settings > API
3. Copy your Project URL and anon/public key
4. In Authentication > Settings, configure your site URL and redirect URLs
5. Add `http://localhost:5000/auth/callback` to your redirect URLs for local development
6. In Authentication > Providers, enable Google OAuth and configure your Google OAuth credentials

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google+ API
4. Go to Credentials > Create Credentials > OAuth 2.0 Client IDs
5. Set application type to "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:5000/auth/callback` (for local development)
   - `https://yourdomain.com/auth/callback` (for production)
7. Copy the Client ID and Client Secret
8. Add these to your Supabase Google OAuth provider settings

## Installation

1. Install the new dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your environment variables in `.env`

3. Run the application:
```bash
python app.py
```

## How It Works

- **Public Routes**: `/`, `/login`, `/signup`, `/auth/callback`
- **Protected Routes**: All other routes require authentication
- **Session Storage**: User ID and email are stored in Flask sessions
- **Automatic Redirects**: Unauthenticated users are redirected to `/login`
- **Post-Login**: Users are redirected to `/dashboard` after successful authentication

## Security Notes

- Change `APP_SECRET_KEY` to a secure random string in production
- Use HTTPS in production
- Consider implementing CSRF protection for forms
- Monitor Supabase logs for suspicious authentication attempts

## Database Integration

The current implementation stores only user ID and email in sessions. For production use, you may want to:

1. Store additional user data in Supabase database
2. Implement user profiles and preferences
3. Add role-based access control
4. Implement session management and refresh tokens
