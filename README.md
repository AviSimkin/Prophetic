# Prophetic 🔮

A Streamlit-based calendar event management application with predictive alerts and proactive issue detection, powered by Google Gemini Flash 2.5 and browseruse.

## Features

- 📅 **Calendar Import**: Upload .ics calendar files to import your events
- 🇮🇱 **Israeli Calendar**: Pre-built sample calendar with typical Israeli events
- 🎮 **Demo Mode**: Toggle between demo mode (simulated time) and production mode (real time)
- ⏰ **Timeline Simulator**: Control time flow for demo purposes (when in demo mode)
- 🤖 **Gemini-Powered Questions**: Uses Google Gemini Flash 2.5 to intelligently collect missing event details
- 🌐 **Browseruse Integration**: Advanced web scraping with browseruse for real-time issue detection
- 🚨 **Proactive Alerts**: Notifies you 7 days and 1 day before events
- 💾 **Persistent State**: Maintains event details and alert status across sessions

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AviSimkin/Prophetic.git
cd Prophetic
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. The app will open in your browser at `http://localhost:8501`

### Basic Workflow

1. **Select Mode**:
   - Toggle **Demo Mode** ON for demonstrations with timeline control
   - Toggle **Demo Mode** OFF for production use with real current date

2. **Upload Calendar**: 
   - Upload your .ics calendar file
   - Or use the **Sample Calendar** button
   - Or use the **Israeli Calendar** button for Hebrew events
   
3. **Timeline Control** (Demo Mode only): 
   - Use the sidebar to simulate time passage
   - Advance by 1 day or 7 days to trigger alerts
   
4. **Complete Event Details**:
   - When you're 7 days before an event, the app will ask for missing details
   - Provide location, arrival time, and departure time
   
5. **Review Alerts**:
   - Check the Alerts tab for potential issues
   - The app scans for weather, traffic, and location problems using browseruse
   - Review and acknowledge alerts

### Demo Mode vs Production Mode

**Demo Mode (Default)**:
- Timeline simulator with manual controls (+1 Day, +7 Days)
- Perfect for classroom demonstrations and testing
- Allows you to quickly jump to dates where events need attention

**Production Mode**:
- Uses real current date automatically
- No timeline controls (always shows actual date)
- Suitable for real-world usage

## Components

### Calendar Parser (`calendar_parser.py`)
- Handles .ics file parsing and event extraction
- Includes Israeli calendar generator with 3 typical events

### LLM Module (`llm_module.py`)
- Uses **Google Gemini Flash 2.5** (free tier) for contextual questions
- Generates intelligent prompts to collect missing event information
- Supports both API mode and mock mode

### Web Scraper (`web_scraper.py`)
- Powered by **browseruse** for advanced web crawling
- Uses Gemini Flash 2.5 as the LLM backend
- Checks for potential issues:
  - Weather conditions
  - Traffic and transit problems
  - Location-specific alerts
- Falls back to mock mode when no API key provided

### Timeline Simulator (`timeline_simulator.py`)
- Controls simulated time flow in demo mode
- Automatically uses real time in production mode

## Configuration

### Google Gemini API Key (Optional)
You can provide a Google Gemini API key in the sidebar for:
- Enhanced LLM functionality for event questions
- Real-time web scraping with browseruse
- If not provided, the app runs in mock mode with simulated data

To get a free Gemini API key:
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Enter it in the sidebar

## Development

The application is built with:
- **Streamlit**: Web interface
- **icalendar**: Calendar file parsing
- **Google Gemini Flash 2.5**: LLM for questions and web analysis
- **browseruse**: Advanced web crawling and scraping
- **pandas**: Data handling

## Future Enhancements

- Integration with real weather APIs (OpenWeatherMap, Weather.gov)
- Integration with traffic APIs (Google Maps, Waze)
- Email/SMS notifications
- Calendar export functionality
- Multi-user support
- Historical alert tracking
- Machine learning for personalized recommendations

## License

MIT License