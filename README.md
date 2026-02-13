# Prophetic 🔮

An intelligent calendar assistant that reviews your schedule and proactively surfaces potential hiccups around upcoming events. Prophetic analyzes calendar items using temporal, spatial, and contextual information, fills in missing details through targeted questions, and uses external signals like traffic, weather, and local events to produce grounded, actionable notifications.

**[Try the live demo →](https://prophetic-zevnlm55ta8gzq.streamlit.app/)**  
*Note: The app may spin down due to inactivity. If the page is unavailable, click "Get the app back up" to wake it.*

## Key Features

- **🤖 Agentic Intelligence**: ReAct-based agents proactively scan your calendar for potential issues using web search, Maps API, and weather forecasts
- **📅 Smart Calendar Intake**: Upload .ics files or use demo calendars for quick testing
- **📝 Context Collection**: Guided prompts to fill missing event details (departure location, transport method, timing) using Gemini when available
- **🚨 Proactive Alerts**: 7-day and 1-day advance warnings for traffic, weather disruptions, nearby events, or missing information (Only shows alerts when actual issues are detected; events with no issues are automatically suppressed)
- **🧭 Address Book**: Save common locations for quick reuse across events
- **🔕 Suppression Transparency**: View all filtered events and suppressed alerts with detailed reasons

Back-end features that are only relevant for development and course submission:
- **🎮 Demo Mode**: Simulated timeline controls for demonstrations and testing; production mode uses real-time
- **📊 Nudge Analytics**: Track how often the system prompts you, balancing proactive help with cognitive load
- **🪵 Comprehensive Logging**: Debug logs with LLM call history and token usage for transparency

## Setup

**Requirements:** Python 3.11

```bash
# Clone the repository
git clone https://github.com/AviSimkin/Prophetic.git
cd Prophetic

# (Recommended) Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### API Keys (Required)

Create a `.env` file in the project root with the following keys:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
SERPAPI_KEY=your_serpapi_key_here
TAVILY_API_KEY=your_tavily_api_key_here
OPEN_WEATHER=your_weatherapi_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

**Get API Keys** (all have free tiers):
- **Google Gemini** (Required): https://aistudio.google.com/apikey - For LLM reasoning, prompts, event filtering, alert validation, and ReAct agent
- **SerpAPI** (Required): https://serpapi.com/ - For Google Maps directions, traffic analysis, and stadium proximity checks
- **Tavily** (Required): https://tavily.com/ - For web search (local events, road closures)
- **WeatherAPI** (Required): https://www.weatherapi.com/ - For weather forecasts and alerts

## Run

```bash
streamlit run app.py
```
Opens at http://localhost:8501

## How It Works

Prophetic follows a human-AI collaborative approach grounded in HAI and nudging principles:

1. **Calendar Import**: Grant permission and upload your .ics file (or use demo calendars)
2. **Event Filtering**: An LLM analyzes each event to determine if it requires attention or additional details
3. **Context Gathering**: When needed, the system prompts you to fill missing event information through targeted questions
4. **Agent Analysis**: A ReAct agent analyzes events using real-time external data (web search, Maps API, weather forecasts, stadium proximity checks)
5. **Alert Validation**: Potential issues pass through an LLM gate that validates findings and balances whether nudging is beneficial, preventing hallucinations and unnecessary prompts

### Navigation

- **Setup**: Manage your address book with common locations
- **Calendar Upload**: Upload .ics files or load demo calendars
- **Notifications**: Review proactive warnings about traffic, weather, nearby events, or missing details; complete event information when needed
  - Detail requests automatically disappear after submission
  - Alerts only appear when issues are detected
- **Suppressed**: View all filtered events and alerts that were suppressed, with explanations:
  - Events filtered as non-actionable (holidays, reminders, all-day events)
  - Events where all checks passed with no issues found
- **Nudge Stats** (demo mode): Monitor how often the system prompts you
- **Debug Logs** (demo mode): Inspect system activity and LLM calls for transparency

## Testing

```bash
# Run everything
pytest

# Quick sanity check
pytest tests/smoke_test.py

# Alert window / pipeline tests
pytest tests/test_alerts.py -v
```

For more detail, see `tests/README.md` (automated tests) and `TESTING.md` (manual test runs).