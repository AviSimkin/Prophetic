"""
Prophetic - Calendar Event Management with Predictive Alerts
"""
import os
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from calendar_parser import parse_calendar_file, create_sample_calendar, create_israeli_calendar
from llm_module import LLMModule
from web_scraper import WebScraper
from timeline_simulator import TimelineSimulator
from prophetic_logger import get_logger, log_event, log_info


# Page configuration
st.set_page_config(
    page_title="Prophetic Calendar",
    page_icon="🔮",
    layout="wide"
)

# Load environment variables once
load_dotenv()
ENV_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize session state
if 'logger' not in st.session_state:
    # Create a richer session name for UI runs
    session_name = f"ui-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    st.session_state.logger = get_logger(session_name=session_name)
    log_info("Application started")

if 'timeline' not in st.session_state:
    st.session_state.timeline = TimelineSimulator()

if 'events' not in st.session_state:
    st.session_state.events = []

if 'event_details' not in st.session_state:
    st.session_state.event_details = {}

if 'alerts_checked' not in st.session_state:
    st.session_state.alerts_checked = set()

if 'permission_calendar' not in st.session_state:
    st.session_state.permission_calendar = False

if 'issues_cache' not in st.session_state:
    st.session_state.issues_cache = {}

if 'api_key' not in st.session_state:
    st.session_state.api_key = ENV_API_KEY

if 'llm_module' not in st.session_state:
    st.session_state.llm_module = LLMModule(api_key=st.session_state.api_key)

if 'scraper' not in st.session_state:
    st.session_state.scraper = WebScraper(api_key=st.session_state.api_key)

if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = True


def main():
    """Main application"""
    st.title("🔮 Prophetic Calendar")
    st.markdown("*Predictive event management with proactive alerts*")
    
    # Sidebar for configuration
    with st.sidebar:
        # Demo mode toggle
        st.header("🎮 Mode")
        demo_mode = st.toggle("Demo Mode", value=st.session_state.demo_mode, help="Enable timeline controls for demonstrations")
        if demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = demo_mode
            st.session_state.timeline.set_demo_mode(demo_mode)
        
        st.divider()
        
        # Timeline control (only in demo mode)
        if st.session_state.demo_mode:
            st.header("⏰ Timeline Control")
            st.markdown("*Simulate time for demo purposes*")
            
            current_sim_date = st.session_state.timeline.get_current_date()
            st.metric("Current Simulated Date", current_sim_date.strftime("%Y-%m-%d"))
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏩ +1 Day"):
                    st.session_state.timeline.advance_days(1)
                    st.rerun()
            
            with col2:
                if st.button("⏩ +7 Days"):
                    st.session_state.timeline.advance_days(7)
                    st.rerun()
            
            if st.button("🔄 Reset to Today"):
                st.session_state.timeline.reset()
                st.session_state.alerts_checked = set()
                st.rerun()
            
            st.divider()
        else:
            st.info("💡 Timeline is set to real current date in production mode")
            st.divider()
        
            # Permissions
            st.header("🔐 Permissions")
            st.caption(f"Calendar access: {'Granted' if st.session_state.permission_calendar else 'Not granted'}")
            if st.button("Give permission to read calendar"):
                st.session_state.permission_calendar = True
                log_event('permission_granted', 'calendar_read', {'granted': True})
                st.success("Permission granted to read calendar")

            st.divider()
        
            # API Key configuration
            st.header("🔑 Gemini API Key (Optional)")

        env_key_present = bool(ENV_API_KEY)
        if env_key_present:
            st.caption("Using key from .env unless you override below.")

        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="Using .env value" if env_key_present else "Enter Google Gemini API key",
            help="Provide a Gemini API key for LLM features. Leave empty to use mock mode."
        )

        # Apply overrides only when user provides a non-empty input
        if api_key:
            st.session_state.api_key = api_key
            st.session_state.llm_module = LLMModule(api_key=api_key)
            st.session_state.scraper = WebScraper(api_key=api_key)
        elif st.session_state.api_key != ENV_API_KEY:
            # Reset to env key if user cleared the field
            st.session_state.api_key = ENV_API_KEY
            st.session_state.llm_module = LLMModule(api_key=ENV_API_KEY)
            st.session_state.scraper = WebScraper(api_key=ENV_API_KEY)
        
    # Main content
    tabs_list = ["📅 Calendar Upload", "📋 Event Details", "🚨 Alerts"]
    if st.session_state.demo_mode:
        tabs_list.append("📊 Debug Logs")
    
    tabs = st.tabs(tabs_list)
    tab1 = tabs[0]
    tab2 = tabs[1]
    tab3 = tabs[2]
    
    with tab1:
        st.header("Upload Calendar")
        if not st.session_state.permission_calendar:
            st.warning("Calendar access is not permitted yet.")
            if st.button("Grant permission now"):
                st.session_state.permission_calendar = True
                log_event('permission_granted', 'calendar_read', {'granted': True, 'source': 'tab1'})
                st.success("Permission granted to read calendar")
                st.rerun()
            else:
                st.info("Use the sidebar to grant permission.")
        
        if not st.session_state.permission_calendar:
            # Skip uploader and sample loaders until permission is granted
            st.stop()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Upload your .ics calendar file",
                type=['ics'],
                help="Upload an iCalendar (.ics) file to import your events"
            )
            
            if uploaded_file is not None:
                try:
                    file_content = uploaded_file.read()
                    events = parse_calendar_file(file_content)
                    st.session_state.events = events
                    log_event('calendar_upload', uploaded_file.name, {'event_count': len(events)})
                    st.success(f"✅ Successfully loaded {len(events)} events!")
                except Exception as e:
                    log_error(f"Error parsing calendar file: {uploaded_file.name}", e)
                    st.error(f"Error parsing calendar file: {str(e)}")
        
        with col2:
            st.markdown("### Or use sample data")
            if st.button("📝 Load Sample Calendar"):
                sample_calendar = create_sample_calendar()
                events = parse_calendar_file(sample_calendar)
                st.session_state.events = events
                log_event('calendar_load', 'Sample Calendar', {'event_count': len(events)})
                st.success(f"✅ Loaded {len(events)} sample events!")
                st.rerun()
            
            if st.button("🇮🇱 Load Israeli Calendar"):
                israeli_calendar = create_israeli_calendar()
                events = parse_calendar_file(israeli_calendar)
                st.session_state.events = events
                log_event('calendar_load', 'Israeli Calendar', {'event_count': len(events)})
                st.success(f"✅ Loaded {len(events)} Israeli events!")
                st.rerun()
        
        # Display loaded events
        if st.session_state.events:
            st.divider()
            st.subheader("Loaded Events")
            
            upcoming_events = st.session_state.timeline.get_upcoming_events(
                st.session_state.events,
                days_ahead=60
            )
            
            if upcoming_events:
                for event in upcoming_events:
                    days_until = st.session_state.timeline.days_until_event(event)
                    
                    with st.expander(f"📅 {event['name']} - {event['start'].strftime('%Y-%m-%d %H:%M')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Days until event:** {days_until}")
                            st.write(f"**Date:** {event['start'].strftime('%Y-%m-%d %H:%M')}")
                            if event.get('description'):
                                st.write(f"**Description:** {event['description']}")
                        
                        with col2:
                            if event.get('location'):
                                st.write(f"**Location:** {event['location']}")
                            
                            event_id = f"{event['name']}_{event['start']}"
                            if event_id in st.session_state.event_details:
                                details = st.session_state.event_details[event_id]
                                if details.get('location'):
                                    st.write(f"**📍 Location:** {details['location']}")
                                if details.get('arrival_time'):
                                    st.write(f"**🕐 Arrival Time:** {details['arrival_time']}")
                                if details.get('departure_time'):
                                    st.write(f"**🚗 Departure Time:** {details['departure_time']}")
            else:
                st.info("No upcoming events in the next 60 days from current simulated date.")
    
    with tab2:
        st.header("Complete Event Details")
        st.markdown("*Provide additional information for your events*")
        
        if not st.session_state.events:
            st.info("👆 Please upload a calendar file first!")
        else:
            # Check for events needing details (within the next 7 days)
            current_date = st.session_state.timeline.get_current_date()
            events_needing_details = [
                event for event in st.session_state.events
                if event['start'] >= current_date and 
                   (event['start'] - current_date).days <= 7
            ]
            
            if events_needing_details:
                st.success(f"🔔 {len(events_needing_details)} event(s) within 7 days need details")
                
                for event in events_needing_details:
                    event_id = f"{event['name']}_{event['start']}"
                    
                    # Check if details already collected
                    if event_id not in st.session_state.event_details:
                        st.session_state.event_details[event_id] = {}
                    
                    details = st.session_state.event_details[event_id]
                    
                    with st.expander(f"📝 {event['name']} - {event['start'].strftime('%Y-%m-%d')}", expanded=True):
                        st.write(f"**Event Date:** {event['start'].strftime('%Y-%m-%d %H:%M')}")
                        
                        # Generate questions for missing info
                        questions = st.session_state.llm_module.generate_questions(
                            {**event, **details}
                        )
                        
                        if questions:
                            st.markdown("**Please provide the following information:**")
                            
                            for field, question in questions.items():
                                current_value = details.get(field, '')
                                
                                if field == 'location':
                                    value = st.text_input(
                                        question,
                                        value=current_value,
                                        key=f"{event_id}_{field}"
                                    )
                                elif field == 'transport_mode':
                                    options = ['car', 'train', 'bus', 'walk', 'bike', 'rideshare', 'other']
                                    value = st.selectbox(
                                        "Transportation method",
                                        options,
                                        index=(options.index(current_value) if current_value in options else 0),
                                        key=f"{event_id}_{field}"
                                    )
                                else:  # time fields
                                    value = st.text_input(
                                        question,
                                        value=current_value,
                                        placeholder="HH:MM (e.g., 09:30)",
                                        key=f"{event_id}_{field}"
                                    )
                                
                                if value and value != current_value:
                                    try:
                                        parsed_value = st.session_state.llm_module.parse_response(
                                            value,
                                            field
                                        )
                                        details[field] = parsed_value
                                    except ValueError as e:
                                        st.error(str(e))
                            
                            if st.button(f"💾 Save Details for {event['name']}", key=f"save_{event_id}"):
                                if all(details.get(field) for field in ['location', 'arrival_time', 'departure_time']):
                                    st.success("✅ Details saved successfully!")
                                    st.rerun()
                                else:
                                    st.warning("⚠️ Please fill in all fields")
                        else:
                            st.success("✅ All details completed for this event!")
            else:
                st.info("No events within the next 7 days. Advance the timeline or add events closer to today.")
    
    with tab3:
        st.header("Alerts & Potential Issues")
        st.markdown("*Proactive notifications about potential hiccups*")
        
        if not st.session_state.events:
            st.info("👆 Please upload a calendar file first!")
        else:
            # Check for alerts (7 days and 1 day before)
            alert_days = [7, 1]
            
            for days_before in alert_days:
                events_for_alert = st.session_state.timeline.get_events_needing_alert(
                    st.session_state.events,
                    days_before=days_before
                )
                
                if events_for_alert:
                    st.subheader(f"🔔 Alerts for {days_before} day(s) before event")
                    
                    for event in events_for_alert:
                        event_id = f"{event['name']}_{event['start']}"
                        alert_key = f"{event_id}_{days_before}days"
                        
                        # Check if we've already processed this alert
                        if alert_key not in st.session_state.alerts_checked:
                            with st.expander(f"⚠️ {event['name']} - {event['start'].strftime('%Y-%m-%d')}", expanded=True):
                                st.write(f"**Event is in {days_before} day(s)**")
                                
                                # Get event details
                                details = st.session_state.event_details.get(event_id, {})
                                
                                if details.get('location'):
                                    st.write(f"**Location:** {details['location']}")
                                    if details.get('transport_mode'):
                                        st.write(f"**Transport:** {details['transport_mode']}")
                                    
                                    # Check cache first to avoid duplicate LLM calls
                                    cache_key = f"{event_id}_{details.get('location')}_{event['start'].strftime('%Y%m%d')}_{details.get('transport_mode','na')}"
                                    
                                    if cache_key not in st.session_state.issues_cache:
                                        # Run web scraping for issues only if not cached
                                        with st.spinner("🔍 Checking for potential issues..."):
                                            event_with_details = {**event, **details}
                                            issues = st.session_state.scraper.check_for_issues(event_with_details)
                                            st.session_state.issues_cache[cache_key] = issues
                                    else:
                                        issues = st.session_state.issues_cache[cache_key]
                                    
                                    if issues:
                                        for issue in issues:
                                            severity_icon = {
                                                'warning': '⚠️',
                                                'info': 'ℹ️',
                                                'critical': '🚨'
                                            }.get(issue['severity'], 'ℹ️')
                                            
                                            # Short notification-style alert
                                            st.markdown(f"{severity_icon} {issue['message']}")
                                            
                                            # Optional: Add expandable details if available
                                            if issue.get('details'):
                                                with st.expander("🔍 See details"):
                                                    st.write(issue['details'])
                                    else:
                                        st.success("✅ No issues detected!")
                                    
                                    # Travel time estimate
                                    if details.get('arrival_time'):
                                        st.divider()
                                        st.markdown("**Travel Information**")
                                        # Mock travel estimate
                                        st.info(f"💡 Suggested arrival time: {details['arrival_time']}")
                                        if details.get('departure_time'):
                                            st.info(f"🚗 Planned departure: {details['departure_time']}")
                                else:
                                    st.warning("⚠️ Location details not yet provided. Please complete event details first.")
                                
                                if st.button(f"✓ Mark as Reviewed", key=f"reviewed_{alert_key}"):
                                    st.session_state.alerts_checked.add(alert_key)
                                    st.rerun()
            
            # Show reviewed alerts
            if st.session_state.alerts_checked:
                st.divider()
                st.subheader("✅ Reviewed Alerts")
                st.write(f"You have reviewed {len(st.session_state.alerts_checked)} alert(s)")
    
    # Debug Logs tab (only visible in demo mode)
    if st.session_state.demo_mode and len(tabs) > 3:
        with tabs[3]:
            st.header("Debug Logs")
            st.markdown("*Session activity and LLM interactions*")
            
            logger = st.session_state.logger
            summary = logger.get_session_summary()
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Actions", summary['events_count'])
            with col2:
                st.metric("LLM Calls", summary['llm_calls_count'])
            with col3:
                st.metric("Input Tokens", summary['total_tokens']['input'])
            with col4:
                st.metric("Output Tokens", summary['total_tokens']['output'])
            
            st.divider()
            
            # LLM calls section
            st.subheader("🤖 LLM Interactions")
            if logger.session_data['llm_calls']:
                for i, call in enumerate(logger.session_data['llm_calls']):
                    timestamp = call['timestamp'].split('T')[1][:8] if 'T' in call['timestamp'] else call['timestamp']
                    purpose = call['metadata'].get('purpose', 'N/A')
                    tokens = f"{call.get('input_tokens', '?')} in + {call.get('output_tokens', '?')} out"
                    
                    with st.expander(f"#{i+1} [{timestamp}] {purpose} ({tokens})", expanded=False):
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown("**📤 Prompt:**")
                            st.code(call['prompt'], language='text')
                        
                        with col2:
                            st.markdown("**📥 Response:**")
                            st.code(call['response'], language='text')
                        
                        if call.get('metadata'):
                            st.markdown("**Metadata:**")
                            st.json(call['metadata'])
            else:
                st.info("No LLM calls yet")
            
            st.divider()
            
            # Activity events section
            st.subheader("📋 Activity Log")
            if logger.session_data['events']:
                for event in logger.session_data['events']:
                    timestamp = event['timestamp'].split('T')[1][:8] if 'T' in event['timestamp'] else event['timestamp']
                    details_str = ""
                    if event.get('details'):
                        if isinstance(event['details'], dict):
                            details_str = f" | {', '.join(f'{k}: {v}' for k, v in event['details'].items())}"
                        else:
                            details_str = f" | {event['details']}"
                    st.text(f"[{timestamp}] {event['type']}: {event['name']}{details_str}")
            else:
                st.info("No activity yet")


if __name__ == "__main__":
    main()
