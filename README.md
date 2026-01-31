# Prophetic 🔮

Streamlit app for proactive event prep: import calendars, collect missing details, and flag travel or location hiccups before they happen.

## Features

- 🎮 Demo vs production modes: simulated timeline controls for demos, real time for production.
- 📅 Calendar intake: .ics upload plus sample and Israeli demo calendars (permission gate before upload).
- 🧭 Address book: save common addresses and reuse them when filling event departure locations.
- 📝 Detail collection: capture location, arrival/departure times, departure location, and transport method; optional Gemini prompts; validation for time inputs.
- 🚨 Alerts: 7-day and 1-day alerts with ReAct agent for intelligent hiccup detection (uses web search + Maps API to verify weather, traffic, events); mark reviewed.
- 📊 Nudge Stats: counts how often the app prompts for details or alerts.
- 🪵 Debug Logs: per-session activity log and LLM call history with token counts.

## Setup

```bash
git clone https://github.com/AviSimkin/Prophetic.git
cd Prophetic
pip install -r requirements.txt
```

Optional `.env` (or sidebar input):
- `GOOGLE_API_KEY=<your-key>` - Required for LLM reasoning and prompts
- `SERPAPI_KEY=<your-key>` - Required for Maps directions and traffic data
- `TAVILY_API_KEY=<your-key>` - Required for web search (weather, events, closures)
- `GEMINI_MODEL=gemini-2.5-flash-lite` (default) 

Without keys the app runs in mock mode. With keys it uses:
- **Gemini** for prompts, event filtering, alert validation, and ReAct reasoning
- **SerpAPI** for Google Maps directions and traffic analysis
- **Tavily** for web search (weather, local events, road closures)

## Run

```bash
streamlit run app.py
```
Opens at http://localhost:8501

## Workflow

- Choose mode in the sidebar (demo default). Demo exposes timeline controls; production uses real time.
- Grant calendar permission when prompted, then upload an .ics file or load the sample/Israeli calendars (demo mode only).
- In **Setup**, add and save common addresses for quick selection.
- In **Event Details**, complete missing fields for events within 7 days (location, arrival/departure times, departure location, transport method). Time inputs are validated; prompts use Gemini when a key is set.
- In **Alerts**, review 7-day/1-day alerts, view issue checks, and mark items as reviewed.
- In **Nudge Stats** (demo mode), see daily/weekly prompt counts.
- In **Debug Logs** (demo mode), inspect activity events and LLM calls.

## Testing

```bash
pytest tests/smoke_test.py
```