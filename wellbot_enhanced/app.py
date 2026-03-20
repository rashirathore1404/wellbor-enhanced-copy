import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from translations import TRANSLATIONS
from groq import Groq
import random
import io
client = Groq(api_key="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")

# ── ML MODEL INTEGRATION ──────────────────────────────────────────────────────
# Import our custom machine learning module
try:
    from ml_model import predict_wellness, get_models
    # Pre-train models when Flask starts so first request is fast
    get_models()
    ML_AVAILABLE = True
    print("[WellBot] ML models loaded successfully!")
except Exception as ml_err:
    print(f"[WellBot] ML models not available: {ml_err}")
    ML_AVAILABLE = False

app = Flask(__name__)
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id='258260405503-ouhvu3edvkc244evjga84jvc120cafao.apps.googleusercontent.com',
    client_secret='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',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)
app.secret_key = 'wellbot_secret_key_2024_wellness_production'

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(_BASE_DIR, 'database', 'wellbot.db')

# ─── CATEGORY SYSTEM PROMPTS ──────────────────────────────────────────────────
CATEGORY_PROMPTS = {
    'general': """You are WellBot, a warm and knowledgeable AI wellness assistant. 
    You help users with all aspects of health and wellness. Be friendly, supportive, and practical.
    Keep responses concise (under 150 words) but impactful. Use emojis sparingly for warmth.""",

    'mental_health': """You are Dr. Serenity, a compassionate AI mental health companion trained in CBT, 
    mindfulness, and emotional wellness. You provide empathetic support, coping strategies, and 
    psychoeducation. You are NOT a replacement for professional therapy. Always validate feelings first, 
    then offer practical techniques. Keep responses under 200 words. If crisis is detected, urge 
    professional help immediately.""",

    'fitness': """You are Coach Apex, an elite AI fitness coach with expertise in strength training, 
    cardio, HIIT, flexibility, and sports performance. You create personalized workout advice, 
    correct form cues, and progressive training plans. Be motivating, energetic, and scientific. 
    Ask about fitness level, goals, and equipment when relevant. Keep responses under 180 words.""",

    'nutrition': """You are Nouri, a certified AI nutritionist specializing in evidence-based dietary 
    advice, meal planning, macro/micronutrient guidance, and healthy eating habits. You consider 
    dietary restrictions, cultural food preferences, and health goals. Be practical and non-judgmental. 
    Avoid extreme diets. Keep responses under 180 words.""",

    'motivation': """You are Spark, an energetic AI life coach and motivational mentor. You help users 
    overcome obstacles, build confidence, set goals, develop resilience, and unlock their potential. 
    Draw from psychology, neuroscience, and real-world success principles. Be bold, inspiring, and 
    action-oriented. Keep responses under 150 words.""",

    'stress': """You are Zen, a calm and grounded AI stress management specialist trained in mindfulness, 
    breathwork, somatic techniques, and stress physiology. You guide users through relaxation exercises, 
    help identify stressors, and build resilience. Your tone is always calm, reassuring, and peaceful. 
    Keep responses under 180 words."""
}

CATEGORY_AVATARS = {
    'general': '🤖', 'mental_health': '🧠', 'fitness': '💪',
    'nutrition': '🥗', 'motivation': '🔥', 'stress': '🌿'
}

LANGUAGES = {
    'en': 'English', 'hi': 'हिन्दी (Hindi)', 'te': 'తెలుగు (Telugu)',
    'mr': 'मराठी (Marathi)', 'ta': 'தமிழ் (Tamil)',
    'kn': 'ಕನ್ನಡ (Kannada)'
}

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(os.path.join(_BASE_DIR, 'database')):
        os.makedirs(os.path.join(_BASE_DIR, 'database'))
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        google_id TEXT UNIQUE,
        full_name TEXT,
        height REAL,
        weight REAL,
        goal TEXT,
        language TEXT DEFAULT 'en',
        theme TEXT DEFAULT 'dark',
        workout_streak INTEGER DEFAULT 0,
        last_workout_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT DEFAULT 'general',
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        language TEXT DEFAULT 'en',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS mood_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        mood_score INTEGER NOT NULL,
        note TEXT,
        date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS workout_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        workout_type TEXT,
        duration_minutes INTEGER,
        calories_burned INTEGER,
        date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS nutrition_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        meal_name TEXT,
        calories INTEGER,
        protein REAL,
        carbs REAL,
        fat REAL,
        date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def get_user(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def build_language_instruction(lang_code):
    lang_name = LANGUAGES.get(lang_code, 'English')
    if lang_code == 'en':
        return ""
    return f"\n\nIMPORTANT: Respond ONLY in {lang_name}. Do not use English unless absolutely necessary for technical terms."

def get_conversation_history(user_id, category, limit=10):
    conn = get_db()
    rows = conn.execute(
        '''SELECT role, message FROM chat_history 
        WHERE user_id = ? AND category = ? 
        ORDER BY created_at DESC LIMIT ?''',
        (user_id, category, limit)
    ).fetchall()
    conn.close()
    history = [{"role": r['role'], "content": r['message']} for r in reversed(rows)]
    return history

def generate_ai_response(message, category, user_id, language='en'):

    try:

        system_prompt = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS['general'])

        # Add language instruction
        system_prompt += build_language_instruction(language)

        # Get conversation memory
        history = get_conversation_history(user_id, category, 10)

        messages = [{"role": "system", "content": system_prompt}]

        messages.extend(history)

        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()

    except Exception as e:

        print("Groq Error:", e)

        return "⚠️ AI service temporarily unavailable."

def get_productivity_scores(limit=60):
    """Return productivity scores from dataset for charts."""
    scores = []

    try:
        import csv
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):

                if i >= limit:
                    break

                try:
                    scores.append(int(row['productivity_score']))
                except:
                    pass

    except:
        pass

    return scores

def calculate_bmi(height_cm, weight_kg):

    try:
        height_cm = float(height_cm)
        weight_kg = float(weight_kg)
    except (TypeError, ValueError):
        return None, None

    if height_cm <= 0 or weight_kg <= 0:
        return None, None

    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"

    return round(bmi, 1), category

def get_dashboard_stats(user_id):
    conn = get_db()
    
    total_chats = conn.execute(
        'SELECT COUNT(*) as c FROM chat_history WHERE user_id = ? AND role = "user"', 
        (user_id,)
    ).fetchone()['c']
    
    top_category = conn.execute(
        '''SELECT category, COUNT(*) as c FROM chat_history 
        WHERE user_id = ? AND role = "user" 
        GROUP BY category ORDER BY c DESC LIMIT 1''',
        (user_id,)
    ).fetchone()
    
    # Weekly chat activity (last 7 days)
    weekly = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        label = (datetime.now() - timedelta(days=i)).strftime('%a')
        count = conn.execute(
            '''SELECT COUNT(*) as c FROM chat_history 
            WHERE user_id = ? AND DATE(created_at) = ? AND role = "user"''',
            (user_id, day)
        ).fetchone()['c']
        weekly.append({'day': label, 'count': count})
    
    # Mood trend (last 7 days)
    mood_data = conn.execute(
        '''SELECT date, AVG(mood_score) as avg_mood FROM mood_tracking 
        WHERE user_id = ? AND date >= DATE('now', '-7 days')
        GROUP BY date ORDER BY date''',
        (user_id,)
    ).fetchall()
    
    # Avg feedback rating
    avg_rating = conn.execute(
        'SELECT AVG(rating) as r FROM feedback WHERE user_id = ?', (user_id,)
    ).fetchone()['r']
    
    # Total calories this week
    total_calories = conn.execute(
        '''SELECT SUM(calories) as c FROM nutrition_log 
        WHERE user_id = ? AND date >= DATE('now', '-7 days')''',
        (user_id,)
    ).fetchone()['c']
    
    # Recent chat history
    recent_chats = conn.execute(
        '''SELECT category, message, created_at FROM chat_history 
        WHERE user_id = ? AND role = "user" 
        ORDER BY created_at DESC LIMIT 5''',
        (user_id,)
    ).fetchall()
    
    # Workout this week
    workouts_this_week = conn.execute(
        '''SELECT COUNT(*) as c, SUM(calories_burned) as cal FROM workout_tracking 
        WHERE user_id = ? AND date >= DATE('now', '-7 days')''',
        (user_id,)
    ).fetchone()

    conn.close()
    return {
        'total_chats': total_chats,
        'top_category': top_category['category'] if top_category else 'general',
        'weekly_activity': weekly,
        'mood_data': [{'date': r['date'], 'mood': round(r['avg_mood'], 1)} for r in mood_data],
        'avg_rating': round(avg_rating, 1) if avg_rating else 0,
        'total_calories_week': total_calories or 0,
        'recent_chats': [{'category': r['category'], 'message': r['message'][:60]+'...', 'time': r['created_at']} for r in recent_chats],
        'workouts_this_week': workouts_this_week['c'] or 0,
        'workout_calories': workouts_this_week['cal'] or 0
    }

# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    """Landing page — shown to visitors before login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login')
def login_page():
    """Login / Register page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html', languages=LANGUAGES)

@app.route('/auth/google/callback')
def google_callback():

    token = google.authorize_access_token()

    resp = google.get('https://www.googleapis.com/oauth2/v2/userinfo')
    user_info = resp.json()

    google_id = user_info['id']
    email = user_info['email']
    name = user_info.get('name')

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE google_id=? OR email=?",
        (google_id, email)
    ).fetchone()

    if not user:
        conn.execute(
            """INSERT INTO users (username,email,google_id,full_name)
               VALUES (?,?,?,?)""",
            (email.split("@")[0], email, google_id, name)
        )
        conn.commit()

        user = conn.execute(
            "SELECT * FROM users WHERE google_id=?",
            (google_id,)
        ).fetchone()

    conn.close()

    session['user_id'] = user['id']
    session['username'] = user['username']

    return redirect('/dashboard')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user = get_user(session['user_id'])

    # Convert height and weight safely
    height = float(user['height']) if user['height'] else None
    weight = float(user['weight']) if user['weight'] else None

    bmi, bmi_cat = calculate_bmi(height, weight)

    stats = get_dashboard_stats(session['user_id'])

    return render_template(
        'dashboard.html',
        user=user,
        stats=stats,
        bmi=bmi,
        bmi_cat=bmi_cat,
        languages=LANGUAGES,
        now=datetime.now()
    )

@app.route('/chat')
@app.route('/chat/<category>')
def chat(category='general'):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if category not in CATEGORY_PROMPTS:
        category = 'general'
    user = get_user(session['user_id'])
    history = get_conversation_history(session['user_id'], category, 20)
    return render_template('chat.html', user=user, category=category, 
                          history=history, languages=LANGUAGES,
                          avatar=CATEGORY_AVATARS.get(category, '🤖'),
                          categories=list(CATEGORY_PROMPTS.keys()))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ─── API ROUTES ───────────────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()

        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

        password_hash = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)',
                (username, email, password_hash, full_name)
            )
            conn.commit()
            user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()
            session['user_id'] = user_id
            session['username'] = username
            return jsonify({'success': True, 'redirect': '/dashboard'})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or not password:
            return jsonify({'success': False, 'message': 'Credentials required'}), 400
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        conn.close()
        if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'success': True, 'redirect': '/dashboard'})
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        category = data.get('category', 'general')
        
        if not message:
            return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
        
        user = get_user(session['user_id'])
        language = data.get('language', user['language'] or 'en')
        
        # Store user message
        conn = get_db()
        conn.execute(
            'INSERT INTO chat_history (user_id, category, role, message, language) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], category, 'user', message, language)
        )
        conn.commit()
        conn.close()

        # Generate AI response
        response = generate_ai_response(message, category, session['user_id'], language)

        # Store AI response
        conn = get_db()
        conn.execute(
            'INSERT INTO chat_history (user_id, category, role, message, language) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], category, 'assistant', response, language)
        )
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'response': response,
            'category': category,
            'avatar': CATEGORY_AVATARS.get(category, '🤖'),
            'timestamp': datetime.now().strftime('%I:%M %p')
        })
    except Exception as e:
        print("Chat Error:", e)
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/profile/update', methods=['POST'])
def update_profile():

    if 'user_id' not in session:
        return jsonify({'success': False}), 401

    data = request.get_json()

    try:
        # Convert height and weight properly
        height = float(data.get('height')) if data.get('height') else None
        weight = float(data.get('weight')) if data.get('weight') else None

        conn = get_db()

        conn.execute(
            '''UPDATE users 
               SET full_name=?, height=?, weight=?, goal=?, language=?, theme=? 
               WHERE id=?''',
            (
                data.get('full_name'),
                height,
                weight,
                data.get('goal'),
                data.get('language', 'en'),
                data.get('theme', 'dark'),
                session['user_id']
            )
        )

        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mood', methods=['POST'])
def log_mood():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO mood_tracking (user_id, mood_score, note) VALUES (?, ?, ?)',
        (session['user_id'], data.get('mood_score'), data.get('note', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/workout', methods=['POST'])
def log_workout():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO workout_tracking (user_id, workout_type, duration_minutes, calories_burned) VALUES (?, ?, ?, ?)',
        (session['user_id'], data.get('workout_type'), data.get('duration'), data.get('calories'))
    )
    # Update streak
    user = get_user(session['user_id'])
    today = datetime.now().strftime('%Y-%m-%d')
    last = user['last_workout_date']
    streak = user['workout_streak'] or 0
    if last == (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'):
        streak += 1
    elif last != today:
        streak = 1
    conn.execute('UPDATE users SET workout_streak=?, last_workout_date=? WHERE id=?',
                 (streak, today, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'streak': streak})

@app.route('/api/nutrition', methods=['POST'])
def log_nutrition():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO nutrition_log (user_id, meal_name, calories, protein, carbs, fat) VALUES (?, ?, ?, ?, ?, ?)',
        (session['user_id'], data.get('meal_name'), data.get('calories'), 
         data.get('protein'), data.get('carbs'), data.get('fat'))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute(
        'INSERT INTO feedback (user_id, rating, comment) VALUES (?, ?, ?)',
        (session['user_id'], data.get('rating'), data.get('comment', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/dashboard/stats')
def dashboard_stats():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    stats = get_dashboard_stats(session['user_id'])
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/export/chat/<category>')
def export_chat(category):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    conn = get_db()
    rows = conn.execute(
        '''SELECT role, message, created_at FROM chat_history 
        WHERE user_id = ? AND category = ? ORDER BY created_at''',
        (session['user_id'], category)
    ).fetchall()
    conn.close()
    
    content = f"WellBot Chat Export - {category.title().replace('_',' ')}\n"
    content += f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    content += "=" * 60 + "\n\n"
    for row in rows:
        role = "You" if row['role'] == 'user' else "WellBot"
        content += f"[{row['created_at'][:16]}] {role}:\n{row['message']}\n\n"
    
    buf = io.BytesIO(content.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='text/plain', 
                    download_name=f'wellbot_{category}_{datetime.now().strftime("%Y%m%d")}.txt',
                    as_attachment=True)

@app.route('/api/language', methods=['POST'])
def update_language():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    data = request.get_json()
    lang = data.get('language', 'en')
    conn = get_db()
    conn.execute('UPDATE users SET language=? WHERE id=?', (lang, session['user_id']))
    conn.commit()
    conn.close()
    session['language'] = lang
    return jsonify({'success': True})
@app.route('/api/ml/predict', methods=['POST'])
def ml_predict():

    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    if not ML_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'ML models not available. Please install scikit-learn and pandas.'
        }), 503

    try:
        data = request.get_json(force=True) or {}

        required = ['sleep_hours', 'work_hours', 'exercise_minutes']

        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Missing field: {field}'}), 400

        input_data = {
            'sleep_hours': float(data.get('sleep_hours', 7)),
            'work_hours': float(data.get('work_hours', 8)),
            'exercise_minutes': float(data.get('exercise_minutes', 30)),
            'screen_time': float(data.get('screen_time', 4)),
            'caffeine_intake': float(data.get('caffeine_intake', 2)),
            'breaks_taken': float(data.get('breaks_taken', 4)),
            'steps': float(data.get('steps', 7000)),
            'water_intake': float(data.get('water_intake', 2)),
        }

        # Run ML model
        result = predict_wellness(input_data)

        # Generate wellness tips
        tips = []

        if input_data['sleep_hours'] < 6:
            tips.append("Try to get at least 7 hours of sleep.")

        if input_data['exercise_minutes'] < 20:
            tips.append("Add a short workout or walk today.")

        if input_data['water_intake'] < 2:
            tips.append("Drink more water to stay hydrated.")

        if input_data['steps'] < 6000:
            tips.append("Try reaching at least 6000 steps today.")

        if input_data['screen_time'] > 6:
            tips.append("Reduce screen time before sleep.")

        result['tips'] = tips
        result['success'] = True

        return jsonify(result)

    except ValueError as ve:
        return jsonify({'success': False, 'message': f'Invalid number: {ve}'}), 400

    except Exception as e:
        print("ML Prediction Error:", e)
        return jsonify({'success': False, 'message': 'Prediction failed'}), 500


# ─── ADMIN CREDENTIALS ────────────────────────────────────────────────────────
ADMIN_EMAIL    = 'admin@wellbot.com'
ADMIN_PASSWORD = 'admin123'
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wellness_data.csv')

# ─── ADMIN HELPERS ────────────────────────────────────────────────────────────
def admin_required(f):
    """Decorator: only let admins through."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def get_admin_stats():
    """Collect summary stats for the admin dashboard cards."""
    conn = get_db()

    total_users   = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
    total_records = conn.execute('SELECT COUNT(*) as c FROM chat_history').fetchone()['c']

    conn.close()

    # Dataset averages from CSV
    avg_sleep  = 0.0
    avg_stress = 'N/A'
    try:
        import csv
        sleep_vals   = []
        stress_count = {}
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sleep_vals.append(float(row['sleep_hours']))
                except (ValueError, KeyError):
                    pass
                sl = row.get('stress_level', '').lower()
                stress_count[sl] = stress_count.get(sl, 0) + 1
        if sleep_vals:
            avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 1)
        if stress_count:
            avg_stress = max(stress_count, key=stress_count.get).capitalize()
    except Exception:
        pass

    return {
        'total_users':   total_users,
        'total_records': total_records,
        'avg_sleep':     avg_sleep,
        'avg_stress':    avg_stress,
    }

def get_dataset_preview(limit=50):
    """Return first `limit` rows of wellness_data.csv as a list of dicts."""
    rows = []
    try:
        import csv
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append({
                    'sleep_hours':       row.get('sleep_hours', ''),
                    'work_hours':        row.get('work_hours', ''),
                    'stress_level':      row.get('stress_level', '').lower(),
                    'mood':              row.get('mood', '').lower(),
                    'productivity_score': row.get('productivity_score', ''),
                })
    except Exception:
        pass
    return rows

def get_mood_counts():
    """Return a dict of mood → count from the dataset."""
    counts = {}
    try:
        import csv
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mood = row.get('mood', 'unknown').lower()
                counts[mood] = counts.get(mood, 0) + 1
    except Exception:
        pass
    return counts

def get_stress_counts():
    """Return a dict of stress_level → count from the dataset."""
    counts = {}
    try:
        import csv
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sl = row.get('stress_level', 'unknown').lower()
                counts[sl] = counts.get(sl, 0) + 1
    except Exception:
        pass
    return counts


    """Return a list of productivity_score values from the dataset."""
    scores = []
    try:
        import csv
        with open(CSV_PATH, newline='') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                try:
                    scores.append(int(row['productivity_score']))
                except (ValueError, KeyError):
                    pass
    except Exception:
        pass
    return scores

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Simple admin login form (GET shows form, POST processes it)."""
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_email'] = email
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid admin credentials.'

    # Inline mini-form so no extra template is needed
    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>Admin Login – WellBot</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet"/>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:"Space Grotesk",sans-serif;background:#0d1117;color:#e6edf3;
         display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .card{{background:#161b22;border:1px solid #30363d;border-radius:16px;
           padding:40px 36px;width:100%;max-width:380px}}
    .logo{{font-size:22px;font-weight:700;margin-bottom:6px;color:#38bdf8}}
    .sub{{color:#8b949e;font-size:13px;margin-bottom:28px}}
    label{{display:block;font-size:13px;color:#8b949e;margin-bottom:6px}}
    input{{display:block;width:100%;background:#1e2530;border:1px solid #30363d;
           color:#e6edf3;padding:10px 14px;border-radius:8px;font-size:14px;
           font-family:inherit;outline:none;margin-bottom:16px}}
    input:focus{{border-color:#38bdf8}}
    .btn{{width:100%;padding:11px;background:#38bdf8;color:#000;border:none;
          border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;
          font-family:inherit}}
    .btn:hover{{background:#7dd3fc}}
    .error{{background:rgba(248,113,113,.1);color:#f87171;border:1px solid rgba(248,113,113,.25);
            border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:16px}}
    .back{{display:block;text-align:center;margin-top:16px;color:#8b949e;
           font-size:13px;text-decoration:none}}
    .back:hover{{color:#38bdf8}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">⚕ WellBot Admin</div>
    <div class="sub">Sign in to access the admin panel</div>
    {"<div class='error'>"+error+"</div>" if error else ""}
    <form method="POST">
      <label>Email</label>
      <input type="email" name="email" placeholder="admin@wellbot.com" required/>
      <label>Password</label>
      <input type="password" name="password" placeholder="••••••••" required/>
      <button class="btn" type="submit">Sign In</button>
    </form>
    <a class="back" href="/login">← Back to user login</a>
  </div>
</body>
</html>'''


@app.route('/admin')
@admin_required
def admin_dashboard():
    """Main admin panel page."""
    conn = get_db()
    users = conn.execute(
        'SELECT id, email, username, created_at FROM users ORDER BY created_at DESC'
    ).fetchall()
    conn.close()

    dataset      = get_dataset_preview(50)
    stats        = get_admin_stats()
    mood_counts  = get_mood_counts()
    stress_counts = get_stress_counts()
    prod_scores  = get_productivity_scores(60)
    predictions  = get_dataset_preview(30)

    return render_template(
        'admin.html',
        users         = users,
        dataset       = dataset,
        stats         = stats,
        mood_counts   = mood_counts,
        stress_counts = stress_counts,
        prod_scores   = prod_scores,
        predictions   = predictions,
    )


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Delete a user and all their data."""
    try:
        conn = get_db()
        conn.execute('DELETE FROM chat_history    WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM mood_tracking   WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM workout_tracking WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM nutrition_log   WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM feedback        WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users           WHERE id = ?',      (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/logout')
def admin_logout():
    """Log the admin out (keeps regular user session intact)."""
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    return redirect(url_for('admin_login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
