# ⚽ Football Analytics System

A modular football analytics platform that collects match data, processes player statistics, and generates AI-powered performance insights.

---

## 👥 Contributors

| Name | Role |
|------|------|
| Pushkar Gupta | Developer |
| Shavya Sharma | Developer |
| Prateek Singh | Developer |

---

## 🚀 Project Roadmap

| Version | Name | Status |
|---------|------|--------|
| **V1** | Player Performance Tracker | ✅ Current |
| **V2** | Match Momentum Dashboard | Upcoming |
| **V3** | Tactical Comparisons | Upcoming |
| **V4** | Fan Sentiment Analyzer | Upcoming |
| **V5** | Predictive Analytics | Upcoming |

---

## 🛠️ Tech Stack

- **Backend:** Python (Flask-based API & data pipeline)  
- **Frontend:** React (Vite)  
- **Automation:** n8n  
- **Data Processing:** Custom scripts  

---

## 📦 Project Structure

```text
football-analytics/
│
├── backend/        # Python pipeline (scrapers, processors, API, summarizer)
├── frontend/       # React dashboard (V2+)
├── n8n/            # Automation workflow exports
├── data/           # Raw & processed data (gitignored)
├── tests/          # Unit tests
└── README.md
```

---

## ⚙️ Setup Instructions

### 🔧 Prerequisites
- Python 3.11+
- Node.js & npm
- Git

---

### 📥 Installation

```bash
# Clone the repository
git clone <repo-url>
cd football-analytics

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

---

### 🔐 Environment Variables

```bash
# Copy example file
cp .env.example .env
```

Edit the `.env` file and add the required keys (refer to `.env.example` for the full list):
* `FOOTBALL_DATA_API_KEY`
* `GROQ_API_KEY`
* `RAPID_API_KEY`

---

## ▶️ Running the Application

### 🧠 Start Backend Server

Start the Python API server from the project root:

```bash
# Ensure virtual environment is activated
python -m backend.api.app
```

---

### 🎨 Start Frontend Server

Navigate to the frontend directory and start the dev server:

```bash
cd frontend
npm install
npm run dev
```

---

## 📌 Notes

* Start the backend before the frontend
* Frontend runs on: [http://localhost:5173](http://localhost:5173)
* Backend port depends on your Flask configuration

---

## 🌱 Future Scope

This project is designed to evolve into a full-fledged football intelligence suite with:

* Advanced analytics
* Real-time match tracking
* AI-driven predictions
