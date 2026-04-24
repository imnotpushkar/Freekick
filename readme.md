# Football Analytics System

A modular football analytics pipeline that collects match data, processes player stats, and generates AI-powered performance summaries.

## Contributors

| Name | Role |
|------|------|
| Pushkar Gupta | Developer |
| Shavya Sharma | Developer |
| Prateek Singh | Developer |

---

## Versions

| Version | Name | Status |
|---------|------|--------|
| V1 | Player Performance Tracker | ✅ Current |
| V2 | Match Momentum Dashboard | Upcoming |
| V3 | Tactical Comparisons | Upcoming |
| V4 | Fan Sentiment Analyzer | Upcoming |
| V5 | Predictive Analytics | Upcoming |

---

## Project Structure

```
backend/        # Python pipeline (scrapers, processors, API, summarizer)
frontend/       # React dashboard (V2+)
n8n/            # Automation workflow exports
data/           # Raw and processed data (gitignored)
tests/          # Unit tests
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js & npm
- Git

### Installation

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

# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

---

## Running the Application

### Backend

Start the Python API server from the project root:

```bash
python -m backend.api.app
```

### Frontend

Navigate to the frontend directory and start the dev server:

```bash
cd frontend
npm run dev
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required keys before running either service. Refer to `.env.example` for the full list of required variables.
