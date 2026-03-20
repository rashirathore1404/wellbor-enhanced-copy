# WellBot — Production AI Wellness Platform

## 🌿 Features

### ✅ Dashboard
- User profile summary (name, email, height, weight, goals, language)
- BMI calculator with visual meter
- Total chat count, workout streak, calorie tracking
- Weekly chat activity graph (Chart.js bar chart)
- Mood tracking trend (Chart.js line chart)
- Average feedback rating display
- Recent chat history preview

### ✅ Separate Chat Specialists
| Category | AI Name | Role |
|---|---|---|
| General | WellBot | All-around wellness assistant |
| Mental Health | Dr. Serenity | CBT & mindfulness therapist |
| Fitness | Coach Apex | Elite fitness coach |
| Nutrition | Nouri | Certified nutritionist |
| Motivation | Spark | Life coach & motivator |
| Stress Relief | Zen | Mindfulness & stress expert |

Each has a unique system prompt and maintains conversation memory per category.

### ✅ Multi-Language Support (14 languages)
English, Hindi, Telugu, Gujarati, Marathi, Tamil, Kannada, Bengali, Spanish, French, German, Japanese, Chinese, Arabic

### ✅ Database Tables
- `users` — profile, height, weight, goals, language, streak
- `chat_history` — all messages with category & language tags
- `mood_tracking` — daily mood logs (1–5 scale)
- `workout_tracking` — workout type, duration, calories, streak
- `nutrition_log` — meal tracking with macros
- `feedback` — star ratings + comments

### ✅ Feedback System
- 1–5 star rating
- Feedback text box
- Average rating on dashboard

### ✅ Advanced UI
- Dark theme with Clash Display typography
- Gradient sidebar, smooth animations
- Typing indicator (bouncing dots)
- Auto-scroll messages
- Message timestamps
- AI avatar per specialist
- Hint chips for quick prompts
- Toast notifications

### ✅ OpenAI Integration
- GPT-4o-mini with specialist system prompts
- Language included in system instructions
- Full conversation history sent per category
- Fallback error handling

### ✅ Bonus Features
- Export chat as .txt file
- Voice input (Web Speech API) with 8 Indian language support
- Workout streak tracker
- Mood logging & trend chart
- Calorie/nutrition tracking

---

## 🚀 Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Your OpenAI API Key
Option A: Environment variable
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Option B: Edit `app.py` line 12:
```python
client = OpenAI(api_key="sk-your-key-here")
```

### 3. (Optional) Google OAuth
Edit `app.py`:
```python
app.config["GOOGLE_OAUTH_CLIENT_ID"] = "your-client-id"
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = "your-secret"
```

### 4. Run the App
```bash
python app.py
```

Visit: http://localhost:5000

---

## 📁 Folder Structure
```
wellbot/
├── app.py                  # Main Flask application
├── requirements.txt
├── README.md
├── database/
│   └── wellbot.db          # Auto-created SQLite database
└── templates/
    ├── login.html           # Login / Register page
    ├── dashboard.html       # Main dashboard
    └── chat.html            # Chat interface (all categories)
```

---

## 🔑 Routes

| Route | Description |
|---|---|
| `GET /` | Login page |
| `GET /dashboard` | Main dashboard |
| `GET /chat/<category>` | Chat panel |
| `POST /api/register` | User registration |
| `POST /api/login` | User login |
| `POST /api/chat` | Send message, get AI response |
| `POST /api/profile/update` | Update profile |
| `POST /api/mood` | Log mood |
| `POST /api/workout` | Log workout |
| `POST /api/nutrition` | Log nutrition |
| `POST /api/feedback` | Submit feedback |
| `POST /api/language` | Update language |
| `GET /api/export/chat/<cat>` | Export chat as text |
| `GET /api/dashboard/stats` | JSON dashboard stats |
