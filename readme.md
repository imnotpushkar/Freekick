# Football Analytics System

A modular football analytics pipeline that collects match data, processes player stats, and generates AI-powered performance summaries.

## Versions
- **V1:** Player Performance Tracker ← current
- **V2:** Match Momentum Dashboard
- **V3:** Tactical Comparisons
- **V4:** Fan Sentiment Analyzer
- **V5:** Predictive Analytics

## Setup

### Prerequisites
- Python 3.11+
- Git

### Installation
```bash
# Clone the repo
git clone <repo-url>
cd football-analytics

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

## Project Structure
```
backend/        # Python pipeline (scrapers, processors, API, summarizer)
frontend/       # React dashboard (V2+)
n8n/            # Automation workflow exports
data/           # Raw and processed data (gitignored)
tests/          # Unit tests
```


##Run Frontend Server
  \ncd frontend
  npm run dev

##Run Backend Server
  python -m backend.api.app
