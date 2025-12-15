"""
Prophetic - Calendar Event Management with Predictive Alerts
"""
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from calendar_parser import parse_calendar_file, create_sample_calendar, create_israeli_calendar
from llm_module import LLMModule
from web_scraper import WebScraper
from timeline_simulator import TimelineSimulator
import json


# Page configuration
st.set_page_config(
    page_title="Prophetic Calendar",
    page_icon="🔮",
    layout="wide"
)

# Initialize session state
if 'timeline' not in st.session_state:
    st.session_state.timeline = TimelineSimulator()

if 'events' not in st.session_state:
    st.session_state.events = []

if 'event_details' not in st.session_state:
    st.session_state.event_details = {}

if 'alerts_checked' not in st.session_state:
    st.session_state.alerts_checked = set()

if 'llm_module' not in st.session_state:
    st.session_state.llm_module = LLMModule()

if 'scraper' not in st.session_state:
    st.session_state.scraper = WebScraper()

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
        
        # API Key configuration
        st.header("🔑 Gemini API Key (Optional)")
        api_key = st.text_input("API Key", type="password", help="Enter Google Gemini API key for LLM features and browseruse. Leave empty to use mock mode")
        if api_key:
            st.session_state.llm_module = LLMModule(api_key=api_key)
            st.session_state.scraper = WebScraper(api_key=api_key)
        
    # Main content
    tab1, tab2, tab3 = st.tabs(["📅 Calendar Upload", "📋 Event Details", "🚨 Alerts"])
    
    with tab1:
        st.header("Upload Calendar")
        
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
                    st.success(f"✅ Successfully loaded {len(events)} events!")
                except Exception as e:
                    st.error(f"Error parsing calendar file: {str(e)}")
        
        with col2:
            st.markdown("### Or use sample data")
            if st.button("📝 Load Sample Calendar"):
                sample_calendar = create_sample_calendar()
                events = parse_calendar_file(sample_calendar)
                st.session_state.events = events
                st.success(f"✅ Loaded {len(events)} sample events!")
                st.rerun()
            
            if st.button("🇮🇱 Load Israeli Calendar"):
                israeli_calendar = create_israeli_calendar()
                events = parse_calendar_file(israeli_calendar)
                st.session_state.events = events
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
            # Check for events needing details (7 days before)
            events_needing_details = st.session_state.timeline.get_events_needing_alert(
                st.session_state.events,
                days_before=7
            )
            
            if events_needing_details:
                st.success(f"🔔 {len(events_needing_details)} event(s) need details (7 days ahead)")
                
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
                st.info("No events need details collection at the current simulated date. Advance the timeline to 7 days before an event.")
    
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
                                    
                                    # Run web scraping for issues
                                    with st.spinner("🔍 Checking for potential issues..."):
                                        event_with_details = {**event, **details}
                                        issues = st.session_state.scraper.check_for_issues(event_with_details)
                                    
                                    if issues:
                                        st.warning(f"Found {len(issues)} potential issue(s):")
                                        for issue in issues:
                                            severity_icon = {
                                                'warning': '⚠️',
                                                'info': 'ℹ️',
                                                'critical': '🚨'
                                            }.get(issue['severity'], 'ℹ️')
                                            
                                            st.markdown(f"{severity_icon} **{issue['type'].title()}**: {issue['message']}")
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


if __name__ == "__main__":
    main()
