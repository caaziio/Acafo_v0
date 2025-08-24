from flask import Flask, render_template, request, session, redirect, url_for, send_file, make_response, flash, g, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.routing import BuildError
import os
import uuid
import hashlib
import time
import json
from datetime import datetime, timedelta
from functools import wraps
from config import settings
from services.ai_client import AIClient
from services.supabase_client import get_supabase_client
from services.database_client import lazy_db
from validators import sanitize_text, validate_story, validate_answer, validate_experience_type, validate_bullets_list, sanitize_bullets_for_save
from google_log import log_to_google_sheet

# Initialize Flask app
app = Flask(__name__)
app.secret_key = settings.APP_SECRET_KEY

# Configure session type
app.config['SESSION_TYPE'] = settings.SESSION_TYPE

# Configure persistent sessions with production security
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 days

# Production security settings
if settings.IS_PRODUCTION:
    app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_DOMAIN'] = None  # Set if you have a specific domain
else:
    app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP in development
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'



# Helper function to safely generate URLs without crashing on missing endpoints
def safe_url_for(endpoint, **values):
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return "#"

# Make safe_url_for available in templates
app.jinja_env.globals["safe_url_for"] = safe_url_for

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT]
)

# Initialize AI client lazily to avoid import-time errors
ai_client = None

def get_ai_client():
    """Get or create the AI client instance."""
    global ai_client
    if ai_client is None:
        ai_client = AIClient()
    return ai_client

# Enhanced authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if not session.get('user_id'):
            return redirect(url_for('login'))
        
        # In production, validate the access token with Supabase
        if settings.IS_PRODUCTION and session.get('access_token'):
            supabase = get_supabase_client()
            user = supabase.auth_get_user(session['access_token'])
            
            if not user:
                # Token is invalid, clear session and redirect to login
                session.clear()
                flash("Your session has expired. Please sign in again.", "error")
                return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Session helpers
def get_experience_list():
    """Safely get and initialize the in-session persistent experience list."""
    lst = session.get("experience_list")
    
    # If session has experiences, return them (existing behavior)
    if lst:
        return lst
    
    # If session is empty, try to load from database (lazy loading)
    try:
        db_experiences = lazy_db.load_experiences(session)
        if db_experiences is not None:
            # Store in session for future use
            session["experience_list"] = db_experiences
            return db_experiences
    except Exception as e:
        print(f"Failed to load experiences from database: {e}")
    
    # Fallback to empty list (existing behavior)
    lst = []
    session["experience_list"] = lst
    return lst

@app.before_request
def before_request():
    """Set request_id for tracking and logging."""
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()
    
    # Force HTTPS redirects in production
    if settings.IS_PRODUCTION:
        if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

def log_ai_call(method_name, experience_type, text_length, text_hash, elapsed_ms, success=True, error=None):
    """Log AI call details for monitoring and debugging."""
    log_data = {
        'request_id': g.request_id,
        'session_id': session.get('session_id', 'unknown'),
        'method': method_name,
        'experience_type': experience_type,
        'text_length': text_length,
        'text_hash': text_hash,
        'elapsed_ms': elapsed_ms,
        'success': success,
        'timestamp': datetime.now().isoformat()
    }
    
    if error:
        log_data['error'] = str(error)
    
    # Try to save to database first (lazy database call)
    try:
        lazy_db.save_ai_log(log_data, session)
    except Exception as e:
        print(f"Failed to save AI log to database: {e}")
    
    # Log to Google Sheets (keep existing functionality)
    try:
        log_to_google_sheet(**log_data)
    except Exception as e:
        print(f"Failed to log to Google Sheets: {e}")
    
    # Also print to console for development
    print(f"AI Call Log: {log_data}")

# In-memory storage for career goals (temporary until database is implemented)
career_goals = {}

@app.route("/api/goal", methods=["GET"])
@login_required
def api_goal_get():
    """Get user's career goal"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": "not_logged_in"}), 401

    # Try to load from Supabase
    goal = lazy_db.load_career_goal(session)
    if goal:
        return jsonify({"ok": True, "goal": goal})

    # Fallback to in-memory (legacy)
    goal = career_goals.get(user_id)
    if not goal:
        return jsonify({"ok": True, "goal": None})
    return jsonify({"ok": True, "goal": goal})

@app.route("/api/goal", methods=["POST"])
@login_required
def api_goal_post():
    """Create or update user's career goal"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": "not_logged_in"}), 401
    try:
        data = request.get_json(force=True) or {}
        target_role = (data.get("target_role") or "").strip()
        if not target_role:
            return jsonify({"ok": False, "error": "missing_target_role"}), 400
        industry = (data.get("industry") or "").strip() or None
        location = (data.get("location") or "").strip() or None
        timeline = data.get("timeline") or "ASAP"
        korean_level = data.get("korean_level") or "Beginner"
        other_languages_raw = data.get("other_languages") or ""
        if isinstance(other_languages_raw, str):
            other_languages = [lang.strip() for lang in other_languages_raw.split(",") if lang.strip()]
        else:
            other_languages = other_languages_raw or []
        # Store in Supabase
        goal_data = {
            "target_role": target_role,
            "industry": industry,
            "location": location,
            "timeline": timeline,
            "korean_level": korean_level,
            "other_languages": other_languages
        }
        lazy_db.save_career_goal(goal_data, session)
        # Also update in-memory (legacy)
        career_goals[user_id] = goal_data
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error saving career goal: {e}")
        return jsonify({"ok": False, "error": "server_error"}), 500

@app.route("/start")
@login_required
def start():
    """Start a new experience without deleting saved experiences."""
    # Preserve saved data
    preserved_experience_list = session.get('experience_list')
    preserved_all_experiences = session.get('all_experiences')
    preserved_session_id = session.get('session_id')

    # Clear only volatile workflow keys
    volatile_keys = [
        'current_experience',
        'life_experience',
        'experience_type',
        'experience_title',
        'answers',
        'questions',
        'bullet_points',
        'skills',
        'question_index',
        'suggestions',
        'improvement',
    ]
    for key in volatile_keys:
        session.pop(key, None)

    # Restore preserved data
    if preserved_experience_list is not None:
        session['experience_list'] = preserved_experience_list
    if preserved_all_experiences is not None:
        session['all_experiences'] = preserved_all_experiences
    if preserved_session_id is not None:
        session['session_id'] = preserved_session_id

    # Use the main entry page with voice input and JSON init flow
    return render_template("index.html")

@app.route("/api/experience/init", methods=["POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_AI)
def api_experience_init():
    """API endpoint for initializing experience processing."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400
        
        experience_type = data.get("experience_type", "")
        experience_text = data.get("experience_text", "")
        
        if not experience_type or not experience_text:
            return jsonify({"success": False, "error": "Missing required fields"}), 400
        
        # Sanitize and validate input
        experience_type = sanitize_text(experience_type)
        experience_text = sanitize_text(experience_text)
        
        # Validate experience type
        type_valid, type_error = validate_experience_type(experience_type)
        if not type_valid:
            return jsonify({"success": False, "error": type_error}), 400
        
        # Validate story text
        is_valid, error_message = validate_story(experience_text)
        if not is_valid:
            return jsonify({"success": False, "error": error_message}), 400
        
        # Check word count
        word_count = len(experience_text.strip().split())
        if word_count < 30:
            return jsonify({"success": False, "error": "Please write a bit more — try to share at least 3–4 full sentences about your experience."}), 400

        # Store in session
        session['life_experience'] = experience_text
        session['experience_type'] = experience_type
        
        # Generate session ID if not exists
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        # Process with AI
        start_time = time.time()
        try:
            result = get_ai_client().generate_initial(experience_type, experience_text)
            
            # Store in session under current_experience key
            session['current_experience'] = {
                'type': experience_type,
                'text': experience_text,
                'title': result['title'],
                'initial_bullets': result['bullet_points'],
                'questions': result['questions'],
                'answers': [],
                'skills': result['skills']
            }
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            text_hash = hashlib.md5(experience_text.encode()).hexdigest()
            
            # Log successful AI call
            log_ai_call(
                method_name="generate_initial",
                experience_type=experience_type,
                text_length=len(experience_text),
                text_hash=text_hash,
                elapsed_ms=elapsed_ms,
                success=True
            )
            
            return jsonify({
                "success": True,
                "ok": True,
                "redirect_url": url_for('followup'),
                "next": url_for('followup')
            })
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            text_hash = hashlib.md5(experience_text.encode()).hexdigest()
            
            # Log failed AI call
            log_ai_call(
                method_name="generate_initial",
                experience_type=experience_type,
                text_length=len(experience_text),
                text_hash=text_hash,
                elapsed_ms=elapsed_ms,
                success=False,
                error=str(e)
            )
            
            return jsonify({
                "success": False,
                "ok": False,
                "error": "AI service temporarily unavailable. Please try again."
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "ok": False,
            "error": "An unexpected error occurred. Please try again."
        }), 500

@app.route("/api/transcribe", methods=["POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_AI)
def api_transcribe():
    """API endpoint for transcribing audio when Web Speech API is not supported."""
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        # Validate file type
        if not audio_file.filename:
            return jsonify({"error": "No audio file selected"}), 400
        
        # Check content type
        content_type = audio_file.content_type
        if content_type not in ['audio/webm', 'audio/wav', 'audio/mpeg']:
            return jsonify({"error": "Unsupported audio format. Please use WebM, WAV, or MP3."}), 400
        
        # Check file size (10MB limit)
        audio_file.seek(0, 2)  # Seek to end
        file_size = audio_file.tell()
        audio_file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({"error": "Audio file too large. Maximum size is 10MB."}), 400
        
        # Use OpenAI Whisper for transcription
        try:
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Create a temporary file for the audio
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
                audio_file.save(temp_file.name)
                temp_file_path = temp_file.name
            
            try:
                with open(temp_file_path, 'rb') as audio:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio
                    )
                
                # Clean up temp file
                os.unlink(temp_file_path)
                
                return jsonify({"text": transcript.text})
                
            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                raise e
                
        except ImportError:
            return jsonify({"error": "OpenAI client not available"}), 500
        except Exception as e:
            return jsonify({"error": f"Transcription failed: {str(e)}"}), 500
            
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# This route is now handled by the comprehensive index function below

# Authentication routes
@app.route("/login")
def login():
    """Login page."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template("login.html")

@app.route("/signup")
def signup():
    """Signup page."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    """Logout user and clear session."""
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('login'))

@app.route("/auth/google")
def auth_google():
    """Initiate Google OAuth sign-in."""
    try:
        supabase = get_supabase_client()
        # Use dynamic redirect URL based on environment
        redirect_url = f"{settings.SITE_URL}/supabase_redirect.html"
        result = supabase.auth_sign_in_with_oauth("google", redirect_url)
        
        if result["success"]:
            return redirect(result["data"].url)
        else:
            flash(f"Google sign-in failed: {result['error']}", "error")
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Authentication error: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route("/auth/magic-link", methods=["POST"])
def auth_magic_link():
    """Send magic link to user's email."""
    try:
        email = request.form.get("email", "").strip()
        remember_me = request.form.get("remember_me") == "on"
        
        if not email:
            flash("Please provide a valid email address.", "error")
            return redirect(url_for('login'))
        
        # Store remember_me preference in session for later use
        session['remember_me'] = remember_me
        
        supabase = get_supabase_client()
        # Use the root route as redirect URL since Supabase will redirect there after verification
        redirect_url = f"{settings.SITE_URL}/"
        result = supabase.auth_sign_in_with_otp(email, redirect_url)
        
        if result["success"]:
            flash("Magic link sent! Check your email and click the link to sign in.", "success")
        else:
            flash(f"Failed to send magic link: {result['error']}", "error")
        
        return redirect(url_for('login'))
    except Exception as e:
        flash(f"Authentication error: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route("/supabase_redirect")
@app.route("/supabase_redirect.html")
def supabase_redirect():
    """Serve the Supabase redirect page for magic links."""
    return send_from_directory('.', 'supabase_redirect.html')

@app.route("/auth/magic-link-verify")
def magic_link_verify():
    """Handle magic link verification directly."""
    try:
        # Get token from URL parameters
        token = request.args.get('token') or request.args.get('access_token')
        email = request.args.get('email')
        
        print(f"Magic link verification - Token: {token}, Email: {email}")
        
        # If we have a token, try to verify it
        if token:
            # Verify the token with Supabase
            supabase = get_supabase_client()
            
            # Try to get user info directly from token
            user = supabase.auth_get_user(token)
            
            if user:
                # Store user info in session
                session['user_id'] = user.get('id') or user.get('sub')
                session['user_email'] = user.get('email')
                session['access_token'] = token
                
                # Set persistent session
                remember_me = session.pop('remember_me', True)
                session.permanent = remember_me
                
                print(f"Magic link user authenticated: {session['user_id']}")
                flash("Successfully signed in with magic link!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Magic link verification failed. Please try again.", "error")
                return redirect(url_for('login'))
        else:
            # No token found, this might be a redirect from Supabase verify endpoint
            # Check if we have any other authentication parameters
            print("No token found in magic link verification")
            flash("Invalid magic link format. Please request a new one.", "error")
            return redirect(url_for('login'))
            
    except Exception as e:
        print(f"Magic link verification error: {str(e)}")
        flash(f"Authentication error: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route("/")
@app.route("/index")
def index():
    """Handle the root route and redirect to appropriate page."""
    # Check if user is already logged in
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    
    # Check if there's a magic link token in the URL (from Supabase redirect)
    token = request.args.get('token') or request.args.get('access_token')
    if token:
        print(f"Found token in root route: {token}")
        # Try to authenticate the user
        try:
            supabase = get_supabase_client()
            user = supabase.auth_get_user(token)
            
            if user:
                # Store user info in session
                session['user_id'] = user.get('id') or user.get('sub')
                session['user_email'] = user.get('email')
                session['access_token'] = token
                
                # Set persistent session
                session.permanent = True
                
                print(f"User authenticated via root route: {session['user_id']}")
                flash("Successfully signed in!", "success")
                return redirect(url_for('dashboard'))
        except Exception as e:
            print(f"Authentication error in root route: {str(e)}")
    
    # If no token or authentication failed, show the start page
    return render_template("start.html")

@app.route("/auth/callback")
def auth_callback():
    """Handle authentication callback from Supabase."""
    try:
        # Debug: Log all query parameters and args
        print(f"Auth callback called with args: {dict(request.args)}")
        print(f"Request URL: {request.url}")
        
        # Get the access token from the URL fragment or query params
        access_token = request.args.get('access_token') or request.args.get('token')
        
        # For magic links, Supabase might send the token in different formats
        # Check for various possible token parameters
        if not access_token:
            access_token = request.args.get('access_token') or request.args.get('token') or request.args.get('auth_token')
        
        print(f"Extracted access_token: {access_token}")
        
        # If no token in query params, check if this is a fragment-based redirect
        if not access_token:
            # This might be a fragment-based redirect, redirect to a JavaScript handler
            print("No token found, rendering auth_callback.html")
            return render_template("auth_callback.html")
        
        # Get user information from Supabase
        supabase = get_supabase_client()
        user = supabase.auth_get_user(access_token)
        
        print(f"Supabase user response: {user}")
        
        if user:
            # Store user info in session
            session['user_id'] = user.get('id') or user.get('sub')
            session['user_email'] = user.get('email')
            session['access_token'] = access_token
            
            # Check if user wants persistent session (from magic link form)
            remember_me = session.pop('remember_me', True)
            session.permanent = remember_me
            
            print(f"User authenticated successfully: {session['user_id']}")
            flash("Successfully signed in!", "success")
            return redirect(url_for('dashboard'))
        else:
            print("Failed to get user from Supabase")
            flash("Authentication failed: Could not verify user.", "error")
            return redirect(url_for('login'))
            
    except Exception as e:
        print(f"Auth callback error: {str(e)}")
        flash(f"Authentication error: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route("/experience/followup", methods=["GET", "POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def followup():
    """Handle the follow-up questions flow."""
    if 'current_experience' not in session:
        flash("Please start by describing an experience.", "error")
        return redirect(url_for('index'))
    
    current_experience = session['current_experience']
    
    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        
        # Sanitize and validate answer
        answer = sanitize_text(answer)
        is_valid, error_message = validate_answer(answer)
        
        if not is_valid:
            current_q = current_experience['questions'][len(current_experience['answers'])]
            return render_template("followup.html", 
                                experience=current_experience,
                                current_question=current_q,
                                current_index=len(current_experience['answers']),
                                error=error_message,
                                answer_text=answer)
        
        # Add answer to session
        current_experience['answers'].append(answer)
        session['current_experience'] = current_experience
        
        # Check if all questions are answered
        if len(current_experience['answers']) >= 3:
            return redirect(url_for('finalize'))
        
        # Continue to next question
        return redirect(url_for('followup'))
    
    # GET request - show current question
    current_index = len(current_experience['answers'])
    
    if current_index >= 3:
        # All questions answered, redirect to finalize
        return redirect(url_for('finalize'))
    
    current_question = current_experience['questions'][current_index]
    
    return render_template("followup.html", 
                         experience=current_experience,
                         current_question=current_question,
                         current_index=current_index)

@app.route("/experience/finalize")
@login_required
@limiter.limit(settings.RATE_LIMIT_AI)
def finalize():
    """Finalize the experience by running AI refinement."""
    if 'current_experience' not in session:
        flash("Please start by describing an experience.", "error")
        return redirect(url_for('index'))
    
    current_experience = session['current_experience']
    
    if len(current_experience['answers']) < 3:
        flash("Please answer all follow-up questions first.", "error")
        return redirect(url_for('followup'))
    
    try:
        # Run final refinement
        start_time = time.time()
        result = get_ai_client().refine_bullets(current_experience['text'], current_experience['answers'])
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Validate and process bullets
        final_bullets, any_truncated = validate_bullets_list(result['final_bullets'])
        
        # Update session with final data from structured response
        current_experience.update({
            'final_bullets': final_bullets,
            'final_skills': result['final_skills'],
            'suggestions': result['suggestions'],
            'improved': False
        })
        
        session['current_experience'] = current_experience
        
        if any_truncated:
            flash("Some bullet points were automatically shortened to fit resume format requirements.", "info")
        
        # Always redirect to final_review on success
        return redirect(url_for('final_review'))
        
    except Exception as e:
        flash(f"Sorry, there was an error processing your request. Please try again. Error: {str(e)}", "error")
        # On error, redirect to index page instead of followup to avoid redirect loop
        return redirect(url_for('index'))

@app.route("/experience/final_review")
@login_required
def final_review():
    """Show the final review page."""
    if 'current_experience' not in session:
        flash("Please start by describing an experience.", "error")
        return redirect(url_for('index'))
    
    current_experience = session['current_experience']
    
    if 'final_bullets' not in current_experience:
        flash("Please complete the follow-up questions first.", "error")
        return redirect(url_for('followup'))
    
    return render_template("final_review.html", experience=current_experience)

@app.route("/experience/improve", methods=["POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_AI)
def improve():
    """Run improvement on the experience."""
    if 'current_experience' not in session:
        flash("Please start by describing an experience.", "error")
        return redirect(url_for('index'))
    
    current_experience = session['current_experience']
    
    # Check if already improved
    if current_experience.get('improved', False):
        flash("Improvement has already been applied to this experience.", "info")
        return redirect(url_for('final_review'))
    
    improvement = request.form.get("improvement", "").strip()
    
    if not improvement:
        flash("Please provide improvement details.", "error")
        return redirect(url_for('final_review'))
    
    try:
        # Sanitize improvement text
        improvement = sanitize_text(improvement)
        
        # Combine original text with improvement
        full_experience = current_experience['text'] + "\n" + improvement
        
        # Regenerate using AI
        start_time = time.time()
        result = get_ai_client().refine_bullets(full_experience, current_experience['answers'])
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Validate and process bullets
        final_bullets, any_truncated = validate_bullets_list(result['final_bullets'])
        
        # Update session with structured response
        current_experience.update({
            'final_bullets': final_bullets,
            'final_skills': result['final_skills'],
            'suggestions': result['suggestions'],
            'improved': True
        })
        
        session['current_experience'] = current_experience
        
        if any_truncated:
            flash("Some bullet points were automatically shortened to fit resume format requirements.", "info")
        
        flash("Experience improved successfully!", "success")
        return redirect(url_for('final_review'))
        
    except Exception as e:
        flash(f"Sorry, there was an error processing your request. Please try again. Error: {str(e)}", "error")
        return redirect(url_for('final_review'))

@app.route("/experience/save", methods=["POST"])
@login_required
def save():
    """Save the finalized experience."""
    if 'current_experience' not in session:
        flash("Please start by describing an experience.", "error")
        return redirect(url_for('index'))
    
    current_experience = session['current_experience']
    
    # Get form data
    title = request.form.get("title", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date_hidden") or request.form.get("end_date", "").strip()
    to_present = request.form.get("to_present")
    if to_present:
        end_date = 'present'
    # Support multiple field names; prefer 'final_bullets' which contains JSON array string
    final_bullets_raw = (
        request.form.get("final_bullets")
        or request.form.get("final_bullets_json")
        or request.form.get("final_bullets_text", "").strip()
    )
    skills = request.form.getlist("skills")
    
    if not title:
        flash("Please provide a title.", "error")
        return redirect(url_for('final_review'))
    if not start_date:
        flash("Please provide a start date.", "error")
        return redirect(url_for('final_review'))
    if not end_date and not to_present:
        flash("Please provide an end date or check 'To present'.", "error")
        return redirect(url_for('final_review'))
    
    # Parse bullets from JSON array
    try:
        final_bullets = []
        if final_bullets_raw:
            # If it looks like JSON array, parse it; else treat as newline-delimited text
            if isinstance(final_bullets_raw, str) and final_bullets_raw.strip().startswith('['):
                final_bullets = json.loads(final_bullets_raw)
            else:
                final_bullets = [b.strip() for b in final_bullets_raw.split('\n') if b.strip()]
        else:
            # Fallback to old textarea method
            final_bullets_text = request.form.get("final_bullets_text", "").strip()
            final_bullets = [bullet.strip() for bullet in final_bullets_text.split('\n') if bullet.strip()]
    except (json.JSONDecodeError, ValueError):
        flash("Invalid bullet points format. Please try again.", "error")
        return redirect(url_for('final_review'))
    
    if not final_bullets:
        flash("Please provide at least one bullet point.", "error")
        return redirect(url_for('final_review'))
    
    # Sanitize and validate bullets
    final_bullets = sanitize_bullets_for_save(final_bullets)
    
    if not final_bullets:
        flash("Please provide valid bullet points.", "error")
        return redirect(url_for('final_review'))
    
    # Create detailed experience object for legacy flow (kept for compatibility)
    experience_data = {
        'title': title,
        'story': current_experience['text'],
        'initial_bullets': current_experience['initial_bullets'],
        'questions': current_experience['questions'],
        'answers': current_experience['answers'],
        'final_bullets': final_bullets,
        'skills': skills,
        'suggestions': current_experience.get('suggestions', ''),
        'improved': current_experience.get('improved', False),
        'start_date': start_date,
        'end_date': end_date
    }
    
    # Initialize all_experiences if not exists
    if 'all_experiences' not in session:
        session['all_experiences'] = []
    
    # Add to experiences
    session['all_experiences'].append(experience_data)

    # New: persist a simplified record in session["experience_list"] for the Experience List page
    experience_list_item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "experience_text": current_experience['text'],
        "bullets": final_bullets,
        "skills": skills,
        "created_at": datetime.utcnow().isoformat(),
        "start_date": start_date,
        "end_date": end_date
    }
    lst = get_experience_list()
    lst.append(experience_list_item)
    session["experience_list"] = lst
    
    # Try to save to database (lazy database call)
    try:
        experience_data = {
            'title': title,
            'experience_text': current_experience['text'],
            'bullets': final_bullets,
            'skills': skills,
            'experience_type': current_experience.get('experience_type', ''),
            'start_date': start_date,
            'end_date': end_date
        }
        lazy_db.save_experience(experience_data, session)
    except Exception as e:
        print(f"Failed to save experience to database: {e}")
    
    # Log to Google Sheet (keep existing functionality)
    try:
        log_to_google_sheet(
            title=title,
            story=current_experience['text'],
            bullet_before=current_experience['initial_bullets'],
            answers=current_experience['answers'],
            bullet_after=final_bullets,
            skills=skills,
            suggestions=current_experience.get('suggestions', '')
        )
    except Exception as e:
        print(f"Failed to log to Google Sheets: {e}")
    

    
    # Clean up current experience
    session.pop('current_experience', None)
    
    flash("Experience saved successfully!", "success")
    # Redirect to the My Experiences page
    return redirect(url_for('my_experiences'))

@app.route("/experiences")
@login_required
def experiences_index():
    """Show all saved experiences as cards."""
    experiences = get_experience_list()
    # Keep old route working, render to new template for consistency
    return render_template("my_experiences.html", experiences=experiences)

@app.route("/experiences/delete/<item_id>", methods=["POST"])
@login_required
def experiences_delete(item_id):
    """Delete an experience list item by id."""
    lst = get_experience_list()
    lst = [item for item in lst if item.get("id") != item_id]
    session["experience_list"] = lst
    
    # Try to delete from database (lazy database call)
    try:
        lazy_db.delete_experience(item_id, session)
    except Exception as e:
        print(f"Failed to delete experience from database: {e}")
    
    flash("Experience deleted.", "success")
    return redirect(url_for('my_experiences'))

@app.route("/experiences/duplicate/<item_id>", methods=["POST"])
@login_required
def experiences_duplicate(item_id):
    """Duplicate an experience list item by id (new uuid and timestamp)."""
    lst = get_experience_list()
    for item in lst:
        if item.get("id") == item_id:
            duplicate_item = {
                "id": str(uuid.uuid4()),
                "title": item.get("title", ""),
                "experience_text": item.get("experience_text", ""),
                "bullets": list(item.get("bullets", [])),
                "skills": list(item.get("skills", [])),
                "created_at": datetime.utcnow().isoformat()
            }
            lst.append(duplicate_item)
            session["experience_list"] = lst
            flash("Experience duplicated.", "success")
            break
    return redirect(url_for('my_experiences'))

# New My Experiences routes (alias of experiences_* to satisfy UX/acceptance criteria)
@app.route("/my-experiences")
@login_required
def my_experiences():
    """Show saved experiences in the My Experiences page."""
    experiences = get_experience_list()
    return render_template("my_experiences.html", experiences=experiences)

@app.route("/my-experiences/delete/<item_id>", methods=["POST"])
@login_required
def my_experiences_delete(item_id):
    """Delete an experience by id (My Experiences endpoint)."""
    lst = get_experience_list()
    lst = [item for item in lst if item.get("id") != item_id]
    session["experience_list"] = lst
    
    # Try to delete from database (lazy database call)
    try:
        lazy_db.delete_experience(item_id, session)
    except Exception as e:
        print(f"Failed to delete experience from database: {e}")
    
    flash("Experience deleted.", "success")
    return redirect(url_for('my_experiences'))

@app.route("/my-experiences/duplicate/<item_id>", methods=["POST"])
@login_required
def my_experiences_duplicate(item_id):
    """Duplicate an experience by id (My Experiences endpoint)."""
    lst = get_experience_list()
    for item in lst:
        if item.get("id") == item_id:
            duplicate_item = {
                "id": str(uuid.uuid4()),
                "title": item.get("title", ""),
                "experience_text": item.get("experience_text", ""),
                "bullets": list(item.get("bullets", [])),
                "skills": list(item.get("skills", [])),
                "created_at": datetime.utcnow().isoformat()
            }
            lst.append(duplicate_item)
            session["experience_list"] = lst
            flash("Experience duplicated.", "success")
            break
    return redirect(url_for('my_experiences'))

@app.route("/resume_preview", methods=["GET", "POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def resume_preview():
    if request.method == "POST":
        improvement = request.form.get("improvement", "").strip()
        original_experience = session.get('life_experience', '')
        answers = session.get('answers', [])

        # Sanitize improvement text if provided
        if improvement:
            improvement = sanitize_text(improvement)
            # Validate improvement text (using answer validation since it's similar)
            is_valid, error_message = validate_answer(improvement)
            if not is_valid:
                            return render_template(
                "resume_preview.html",
                preview_title=session.get('experience_title'),
                preview_story=session.get('life_experience'),
                preview_bullets=session.get('bullet_points'),
                preview_skills=session.get('skills'),
                suggestions=session.get('suggestions'),
                error=error_message
            )

        full_experience = original_experience + "\n" + improvement if improvement else original_experience

        try:
            # Use AI client for bullet refinement
            updated_bullets = get_ai_client().refine_bullets(full_experience, answers)

            # ✅ Only update if there's improvement text
            if improvement:
                session['all_experiences'][-1] = {
                    'title': session.get('experience_title'),
                    'story': original_experience + "\n" + improvement,
                    'bullet_points': updated_bullets,
                    'skills': session.get('skills')
                }

                # Log the experience
                log_to_google_sheet(
                    title=session['experience_title'],
                    story=original_experience + "\n" + improvement,
                    bullet_before=session['bullet_points'],
                    answers=answers,
                    bullet_after=updated_bullets,
                    skills=session['skills'],
                    suggestions=session.get('suggestions', 'N/A')
                )

            # ✅ Clean up temporary variables
            session.pop('life_experience', None)
            session.pop('experience_title', None)
            session.pop('answers', None)
            session.pop('questions', None)
            session.pop('bullet_points', None)
            session.pop('skills', None)
            session.pop('question_index', None)

            return redirect(url_for('experience_complete'))
            
        except Exception as e:
            flash(f"Sorry, there was an error processing your request. Please try again. Error: {str(e)}", "error")
            return render_template(
                "resume_preview.html",
                preview_title=session.get('experience_title'),
                preview_story=session.get('life_experience'),
                preview_bullets=session.get('bullet_points'),
                preview_skills=session.get('skills'),
                suggestions=session.get('suggestions'),
                error="AI service temporarily unavailable. Please try again."
            )

    return render_template(
        "resume_preview.html",
        preview_title=session.get('experience_title'),
        preview_story=session.get('life_experience'),
        preview_bullets=session.get('bullet_points'),
        preview_skills=session.get('skills'),
        suggestions=session.get('suggestions')
    )

@app.route("/final_resume")
@login_required
@limiter.limit(settings.RATE_LIMIT_AI)
def final_resume():
    experience = session.get('life_experience', '')
    answers = session.get('answers', [])

    try:
        # Use AI client for final bullet refinement
        updated_bullets = get_ai_client().refine_bullets(experience, answers)

        # Parse the response to extract suggestions
        # Note: This is a simplified approach - in production you might want a more structured response
        suggestions = "Consider adding specific metrics and timeframes to make your experience more impactful."

        session['bullet_points'] = updated_bullets
        session['suggestions'] = suggestions

        # Save to all_experiences only ONCE
        if 'all_experiences' not in session:
            session['all_experiences'] = []

        session['all_experiences'].append({
            'title': session.get('experience_title'),
            'story': experience,
            'bullet_points': updated_bullets,
            'skills': session.get('skills')
        })

        # Log to Google Sheet
        log_to_google_sheet(
            title=session['experience_title'],
            story=experience,
            bullet_before=session['bullet_points'],
            answers=answers,
            bullet_after=updated_bullets,
            skills=session['skills'],
            suggestions=suggestions
        )

        return redirect(url_for('resume_preview'))
        
    except Exception as e:
        flash(f"Sorry, there was an error processing your request. Please try again. Error: {str(e)}", "error")
        return redirect(url_for('resume_preview'))

@app.route("/experience_complete")
@login_required
def experience_complete():
    all_experiences = session.get('all_experiences', [])
    latest_experience = all_experiences[-1] if all_experiences else {}
    total = len(all_experiences)
    return render_template("experience_complete.html", experience=latest_experience, total=total)

@app.route("/full_resume")
@login_required
def full_resume():
    """Display the full resume with all experiences."""
    try:
        # Get all saved experiences from session
        experiences = session.get('all_experiences', [])
        
        if not experiences:
            flash("No experiences found. Please add some experiences first.", "warning")
            return redirect(url_for("index"))
        
        return render_template("full_resume.html", experiences=experiences)
        
    except Exception as e:
        print(f"Error in full_resume: {e}")
        flash("An error occurred while loading the resume.", "error")
        return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard page - starting point for the application."""
    return render_template("dashboard.html")

@app.route("/experience", methods=["GET", "POST"])
@login_required
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def experience():
    """Experience builder page for generating bullet points and extracting skills."""
    # Redirect to index page since experience.html template was deleted
    return redirect(url_for('index'))

@app.route("/coaching")
def coaching():
    """Coaching page - redirect to 404 for now."""
    return render_template("not_found.html"), 404

@app.route("/audit")
def audit():
    """Resume audit page - redirect to 404 for now."""
    return render_template("not_found.html"), 404

# @app.route("/build-resume")
# @login_required
# def build_resume():
#     return render_template("layout.html", content_template="template_cv_embed.html")

@app.route("/best-fit-jobs")
@login_required
def best_fit_jobs():
    # Check requirements from user data
    user_id = session.get('user_id')
    # Experiences
    experiences = lazy_db.load_experiences(session) or []
    has_experiences = len(experiences) >= 5
    # Languages (assume stored in career goal or profile)
    goal = lazy_db.load_career_goal(session)
    has_languages = bool(goal and goal.get('other_languages') and len(goal['other_languages']) > 0)
    # Education (assume stored in career goal or profile for now)
    has_education = bool(goal and goal.get('education')) if goal else False
    education_action_href = url_for('dashboard') + '#goalSummary'
    # Career goal
    has_goal = bool(goal and goal.get('target_role'))
    requirements = [
        {
            'key': 'experiences',
            'label': 'Add 5+ Experiences',
            'desc': 'Add at least 5 experiences to get accurate job matches.',
            'complete': has_experiences,
            'action': { 'text': 'Add', 'href': url_for('start') }
        },
        {
            'key': 'languages',
            'label': 'Enter All Languages',
            'desc': 'List all languages you speak for better job matching.',
            'complete': has_languages,
            'action': { 'text': 'Edit', 'href': url_for('dashboard') + '#goalSummary' }
        },
        {
            'key': 'education',
            'label': 'Fill Education Section',
            'desc': 'Education helps match you to jobs with degree requirements.',
            'complete': has_education,
            'action': { 'text': 'Edit', 'href': education_action_href }
        },
        {
            'key': 'goal',
            'label': 'Set Career Goal',
            'desc': 'Let us know your career goal for more relevant suggestions.',
            'complete': has_goal,
            'action': { 'text': 'Edit', 'href': url_for('dashboard') + '#goalSummary' }
        }
    ]
    return render_template("best_fit_jobs.html", requirements=requirements)

@app.errorhandler(404)
def not_found(error):
    """Custom 404 error handler."""
    return render_template("not_found.html"), 404

@app.route('/api/me')
def api_me():
    user_id = session.get('user_id')
    return jsonify({'user_id': user_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, host="0.0.0.0", port=port)