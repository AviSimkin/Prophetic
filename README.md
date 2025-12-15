# Prophetic 🔮

A Streamlit-based calendar event management application with predictive alerts and proactive issue detection.

## Features

- 📅 **Calendar Import**: Upload .ics calendar files to import your events
- ⏰ **Timeline Simulator**: Control time flow for demo purposes
- 🤖 **LLM-Powered Questions**: Intelligently collects missing event details (location, arrival/departure times)
- 🌐 **Web Scraping**: Checks for potential issues like weather, traffic, and location-specific problems
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

1. **Upload Calendar**: 
   - Upload your .ics calendar file or use the sample calendar
   
2. **Timeline Control**: 
   - Use the sidebar to simulate time passage
   - Advance by 1 day or 7 days to trigger alerts
   
3. **Complete Event Details**:
   - When you're 7 days before an event, the app will ask for missing details
   - Provide location, arrival time, and departure time
   
4. **Review Alerts**:
   - Check the Alerts tab for potential issues
   - The app scans for weather, traffic, and location problems
   - Review and acknowledge alerts

### Timeline Simulator

The timeline simulator allows you to control the "current date" for demo purposes:
- **+1 Day**: Advance one day forward
- **+7 Days**: Jump one week forward
- **Reset to Today**: Return to actual current date

This is useful for demonstrations as you can quickly jump to dates where events need attention.

## Components

### Calendar Parser (`calendar_parser.py`)
Handles .ics file parsing and event extraction.

### LLM Module (`llm_module.py`)
Generates contextual questions to collect missing event information. Supports both OpenAI API and mock mode.

### Web Scraper (`web_scraper.py`)
Checks for potential issues:
- Weather conditions
- Traffic and transit problems
- Location-specific alerts

*Note: Current implementation uses mock data for demonstration. In production, integrate with real APIs (OpenWeatherMap, Google Maps, etc.)*

### Timeline Simulator (`timeline_simulator.py`)
Controls simulated time flow for demo purposes.

## Configuration

### OpenAI API Key (Optional)
You can provide an OpenAI API key in the sidebar for enhanced LLM functionality. If not provided, the app runs in mock mode with pre-defined questions.

## Development

The application is built with:
- **Streamlit**: Web interface
- **icalendar**: Calendar file parsing
- **BeautifulSoup**: Web scraping foundation
- **OpenAI**: LLM integration (optional)

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