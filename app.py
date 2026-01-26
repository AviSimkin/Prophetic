"""
Prophetic - Calendar Event Management with Predictive Alerts
"""
import os
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.calendar_parser import parse_calendar_file, create_sample_calendar, create_israeli_calendar
from src.llm_module import LLMModule
from src.web_scraper import WebScraper
from src.timeline_simulator import TimelineSimulator
from src.prophetic_logger import get_logger, log_event, log_info, log_error


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

if 'alerts_generated' not in st.session_state:
    st.session_state.alerts_generated = set()  # event_ids that have had issue checks run

if 'details_ignored' not in st.session_state:
    st.session_state.details_ignored = set()  # event_ids that user chose to ignore detail requests

if 'detail_request_timestamps' not in st.session_state:
    st.session_state.detail_request_timestamps = {}  # event_id -> timestamp when first shown

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

if 'user_addresses' not in st.session_state:
    st.session_state.user_addresses = [
        {'name': 'Home', 'address': '', 'saved': True},
        {'name': 'Work', 'address': '', 'saved': True}
    ]

if 'address_edit_mode' not in st.session_state:
    st.session_state.address_edit_mode = False

if 'nudge_counters' not in st.session_state:
    st.session_state.nudge_counters = {'daily': {}, 'weekly': {}}

if 'transportation_methods' not in st.session_state:
    st.session_state.transportation_methods = ['Car', 'Public Transit', 'Walking', 'Bike', 'Other']


def is_actionable_event(event: dict) -> bool:
    """Heuristic: only prompt for details on events people likely attend."""
    name = event.get('name', '').lower()
    auto_keywords = [
        'holiday', 'observance', 'observed', 'day off', 'reminder',
        'birthday', 'anniversary', 'payday', 'bill', 'invoice'
    ]
    if any(keyword in name for keyword in auto_keywords):
        return False
    start = event.get('start')
    end = event.get('end')
    if isinstance(start, datetime) and isinstance(end, datetime):
        duration = end - start
        # Treat all-day style entries as non-actionable
        if start.hour == 0 and start.minute == 0 and duration >= timedelta(hours=23):
            return False
    return True


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
            st.metric("Current Simulated Time", current_sim_date.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Day controls
            st.markdown("**Days:**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏩ +1 Day"):
                    st.session_state.timeline.advance_days(1)
                    st.rerun()
            
            with col2:
                if st.button("⏩ +7 Days"):
                    st.session_state.timeline.advance_days(7)
                    st.rerun()
            
            # Hour and minute controls
            st.markdown("**Hours & Minutes:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("⏩ +1 Hour"):
                    st.session_state.timeline.advance_hours(1)
                    st.rerun()
            with col2:
                if st.button("⏩ +15 Min"):
                    st.session_state.timeline.advance_minutes(15)
                    st.rerun()
            with col3:
                if st.button("⏩ +1 Min"):
                    st.session_state.timeline.advance_minutes(1)
                    st.rerun()
            
            # Set specific time
            st.markdown("**Set Specific Time:**")
            col1, col2 = st.columns(2)
            with col1:
                set_hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=current_sim_date.hour, key="set_hour")
            with col2:
                set_minute = st.number_input("Minute (0-59)", min_value=0, max_value=59, value=current_sim_date.minute, key="set_minute")
            
            if st.button("🕐 Set Time"):
                st.session_state.timeline.set_time(set_hour, set_minute)
                st.rerun()
            
            if st.button("🔄 Reset to Now"):
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
    tabs_list = ["🏠 Setup", "📅 Calendar Upload", "� Notifications"]
    if st.session_state.demo_mode:
        tabs_list.append("📊 Nudge Stats")
        tabs_list.append("📊 Debug Logs")
    
    tabs = st.tabs(tabs_list)
    tab_setup = tabs[0]
    tab1 = tabs[1]
    tab_notifications = tabs[2]
    tab_nudges = tabs[3] if st.session_state.demo_mode else None
    tab_debug = tabs[4] if st.session_state.demo_mode else None
    
    with tab_setup:
        st.header("Setup Your Addresses")
        st.markdown("*Configure your common locations for easier event planning*")
        
        # Display all addresses
        for idx, addr_info in enumerate(st.session_state.user_addresses):
            with st.container():
                col1, col2, col3 = st.columns([2, 3, 1])
                
                with col1:
                    name = st.text_input(
                        "Name",
                        value=addr_info['name'],
                        key=f"addr_name_{idx}",
                        placeholder="e.g., Mom's house, Gym"
                    )
                    addr_info['name'] = name
                
                with col2:
                    address = st.text_input(
                        "Address",
                        value=addr_info['address'],
                        key=f"addr_address_{idx}",
                        placeholder="Enter full address"
                    )
                    addr_info['address'] = address
                
                with col3:
                    st.write("")  # Spacer
                    st.write("")  # Spacer
                    if st.button("🗑️", key=f"remove_addr_{idx}", help="Remove this address"):
                        st.session_state.user_addresses.pop(idx)
                        st.rerun()
                
                # Show saved status
                if addr_info.get('saved', False) and addr_info['name'] and addr_info['address']:
                    st.caption(f"✅ Saved")
                st.divider()
        
        # Add new address button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("➕ Add New Address"):
                st.session_state.user_addresses.append({'name': '', 'address': '', 'saved': False})
                st.rerun()
        
        with col2:
            if st.button("💾 Save All Addresses", type="primary"):
                # Mark all addresses as saved and log
                saved_count = 0
                for addr_info in st.session_state.user_addresses:
                    if addr_info['name'] and addr_info['address']:
                        addr_info['saved'] = True
                        saved_count += 1
                        log_event('address_saved', addr_info['name'], {'address': addr_info['address']})
                
                if saved_count > 0:
                    st.success(f"✅ Saved {saved_count} address(es)!")
                else:
                    st.warning("⚠️ No addresses to save. Please fill in name and address fields.")
                st.rerun()
        
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
            if st.session_state.demo_mode:
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
    
    with tab_notifications:
        st.header("🔔 Notifications")
        st.markdown("*Event details and alerts in chronological order*")
        
        if not st.session_state.events:
            st.info("👆 Please upload a calendar file first!")
        else:
            # Get events within the next 7 days (this is when we start notifying)
            current_date = st.session_state.timeline.get_current_date()
            events_within_7days = [
                event for event in st.session_state.events
                if event.get('start')
                and event['start'] >= current_date
                and st.session_state.timeline.days_until_event(event) <= 7
                and is_actionable_event(event)
            ]
            
            # Sort chronologically by event date
            events_within_7days.sort(key=lambda e: e['start'])
            
            if not events_within_7days:
                st.info("No upcoming events within the next 7 days.")
            else:
                st.success(f"📋 {len(events_within_7days)} event(s) within 7 days")
                
                for event in events_within_7days:
                    event_id = f"{event['name']}_{event['start']}"
                    days_until = st.session_state.timeline.days_until_event(event)
                    details = st.session_state.event_details.get(event_id, {})
                    
                    # Check if detail request should be auto-ignored (24 hours passed)
                    if event_id in st.session_state.detail_request_timestamps:
                        request_time = st.session_state.detail_request_timestamps[event_id]
                        hours_since_request = (datetime.now() - request_time).total_seconds() / 3600
                        if hours_since_request >= 24 and event_id not in st.session_state.details_ignored:
                            st.session_state.details_ignored.add(event_id)
                            log_event('details_auto_ignored', event['name'], {'reason': '24_hours_passed'})
                    
                    required_fields = ['location', 'arrival_time', 'departure_time', 'departure_location', 'transportation_method']
                    details_complete = all(details.get(field) for field in required_fields)
                    details_ignored = event_id in st.session_state.details_ignored
                    alert_generated = event_id in st.session_state.alerts_generated
                    alert_dismissed = event_id in st.session_state.alerts_checked
                    
                    # Determine notification type
                    if not details_complete and not details_ignored:
                        # Show detail request
                        notification_type = "detail_request"
                        icon = "📝"
                        title = f"{icon} Details Needed: {event['name']}"
                    elif (details_complete or details_ignored) and alert_generated and not alert_dismissed:
                        # Show alert (only after issue check has been run)
                        notification_type = "alert"
                        icon = "⚠️"
                        title = f"{icon} Alert: {event['name']}"
                    elif (details_complete or details_ignored) and not alert_generated:
                        # Details just saved/ignored, need to generate alert on next check
                        notification_type = "pending_alert"
                    else:
                        # Already dismissed, skip
                        continue
                    
                    # For pending alerts, generate them now (run issue check)
                    if notification_type == "pending_alert":
                        location = details.get('location') or event.get('location', '')
                        if location:
                            cache_key = f"{event_id}_{location}_{event['start'].strftime('%Y%m%d')}_{details.get('transportation_method','na')}"
                            if cache_key not in st.session_state.issues_cache:
                                # Run the issue check in the background
                                event_with_details = {**event, **details, 'location': location}
                                issues = st.session_state.scraper.check_for_issues(event_with_details)
                                st.session_state.issues_cache[cache_key] = issues
                            # Mark alert as generated
                            st.session_state.alerts_generated.add(event_id)
                        # Skip showing notification this cycle - it will appear on next rerun
                        continue
                    
                    # Record when detail request first shown
                    if notification_type == "detail_request" and event_id not in st.session_state.detail_request_timestamps:
                        st.session_state.detail_request_timestamps[event_id] = datetime.now()
                    
                    with st.expander(f"{title} - {event['start'].strftime('%Y-%m-%d')}", expanded=True):
                        st.write(f"**Event is in {days_until} day(s)** • {event['start'].strftime('%Y-%m-%d %H:%M')}")
                        
                        if notification_type == "detail_request":
                            # Detail request form
                            st.markdown("### Please provide event details")
                            
                            # Nudge counter
                            missing_fields = [f for f in required_fields if not details.get(f)]
                            current_date_str = current_date.strftime('%Y-%m-%d')
                            current_week_str = current_date.strftime('%Y-W%W')
                            detail_nudge_key = f"{event_id}_details_prompted"
                            if detail_nudge_key not in st.session_state:
                                if current_date_str not in st.session_state.nudge_counters['daily']:
                                    st.session_state.nudge_counters['daily'][current_date_str] = 0
                                if current_week_str not in st.session_state.nudge_counters['weekly']:
                                    st.session_state.nudge_counters['weekly'][current_week_str] = 0
                                st.session_state.nudge_counters['daily'][current_date_str] += 1
                                st.session_state.nudge_counters['weekly'][current_week_str] += 1
                                st.session_state[detail_nudge_key] = True
                                log_event('nudge_details_prompted', event['name'], {'missing_fields': missing_fields, 'date': current_date_str})
                            
                            # Departure location
                            st.markdown("**Departure Information:**")
                            address_options = []
                            for addr_info in st.session_state.user_addresses:
                                if addr_info.get('saved', False) and addr_info['name'] and addr_info['address']:
                                    address_options.append((addr_info['name'], addr_info['address']))
                            address_options.append(('✏️ Custom', 'custom'))
                            
                            current_departure = details.get('departure_location', '')
                            departure_labels = [label for label, _ in address_options]
                            selected_departure_idx = 0
                            if current_departure:
                                for idx, (label, addr) in enumerate(address_options):
                                    if addr == current_departure:
                                        selected_departure_idx = idx
                                        break
                            
                            departure_selection = st.selectbox(
                                "Departing from:",
                                departure_labels,
                                index=selected_departure_idx,
                                key=f"{event_id}_departure_selector"
                            )
                            
                            selected_idx = departure_labels.index(departure_selection)
                            selected_address = address_options[selected_idx][1]
                            
                            if selected_address == 'custom':
                                custom_departure = st.text_input(
                                    "Enter custom departure address:",
                                    value=current_departure if current_departure not in [addr for _, addr in address_options[:-1]] else '',
                                    key=f"{event_id}_custom_departure"
                                )
                                if custom_departure:
                                    details['departure_location'] = custom_departure
                            else:
                                details['departure_location'] = selected_address
                            
                            st.divider()
                            st.markdown("**Event Details:**")
                            
                            # Location
                            current_location = details.get('location', event.get('location', ''))
                            location_value = st.text_input(
                                f"📍 Where is '{event['name']}' taking place?",
                                value=current_location,
                                placeholder="Enter the event address or venue name",
                                key=f"{event_id}_location"
                            )
                            if location_value and location_value != current_location:
                                details['location'] = location_value
                            
                            # Arrival time
                            current_arrival = details.get('arrival_time', '')
                            arrival_value = st.text_input(
                                f"⏰ What time do you need to arrive?",
                                value=current_arrival,
                                placeholder="HH:MM (e.g., 09:30)",
                                key=f"{event_id}_arrival_time"
                            )
                            if arrival_value and arrival_value != current_arrival:
                                try:
                                    parsed_value = st.session_state.llm_module.parse_response(arrival_value, 'arrival_time')
                                    details['arrival_time'] = parsed_value
                                except ValueError as e:
                                    st.error(str(e))
                            
                            # Departure time
                            current_departure_time = details.get('departure_time', '')
                            departure_value = st.text_input(
                                f"🚀 What time will you leave?",
                                value=current_departure_time,
                                placeholder="HH:MM (e.g., 08:45)",
                                key=f"{event_id}_departure_time"
                            )
                            if departure_value and departure_value != current_departure_time:
                                try:
                                    parsed_value = st.session_state.llm_module.parse_response(departure_value, 'departure_time')
                                    details['departure_time'] = parsed_value
                                except ValueError as e:
                                    st.error(str(e))
                            
                            # Transportation
                            current_transport = details.get('transportation_method', '')
                            transport_options = [''] + st.session_state.transportation_methods
                            current_idx = transport_options.index(current_transport) if current_transport in transport_options else 0
                            transport_method = st.selectbox(
                                "🚗 How will you get there?",
                                transport_options,
                                index=current_idx,
                                key=f"{event_id}_transport"
                            )
                            if transport_method and transport_method != current_transport:
                                details['transportation_method'] = transport_method
                            
                            st.divider()
                            
                            # Action buttons
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"💾 Save Details", key=f"save_{event_id}"):
                                    if all(details.get(field) for field in required_fields):
                                        log_event('event_details_saved', event['name'], details)
                                        st.success("✅ Details saved!")
                                        st.rerun()
                                    else:
                                        missing = [f for f in required_fields if not details.get(f)]
                                        st.warning(f"⚠️ Please fill in: {', '.join(missing)}")
                            
                            with col2:
                                if st.button(f"🚫 Ignore", key=f"ignore_details_{event_id}"):
                                    st.session_state.details_ignored.add(event_id)
                                    log_event('details_ignored', event['name'], {'by_user': True})
                                    st.rerun()
                        
                        elif notification_type == "alert":
                            # Alert with issue checking
                            location = details.get('location') or event.get('location', '')
                            
                            if location:
                                st.write(f"**Location:** {location}")
                                if details.get('transportation_method'):
                                    st.write(f"**Transport:** {details['transportation_method']}")
                                
                                # Nudge counter for alerts
                                alert_nudge_key = f"{event_id}_alert_nudge_counted"
                                if alert_nudge_key not in st.session_state:
                                    current_date_str = current_date.strftime('%Y-%m-%d')
                                    current_week_str = current_date.strftime('%Y-W%W')
                                    if current_date_str not in st.session_state.nudge_counters['daily']:
                                        st.session_state.nudge_counters['daily'][current_date_str] = 0
                                    if current_week_str not in st.session_state.nudge_counters['weekly']:
                                        st.session_state.nudge_counters['weekly'][current_week_str] = 0
                                    st.session_state.nudge_counters['daily'][current_date_str] += 1
                                    st.session_state.nudge_counters['weekly'][current_week_str] += 1
                                    st.session_state[alert_nudge_key] = True
                                    log_event('nudge_shown', event['name'], {'days_before': days_until, 'date': current_date_str})
                                
                                # Check for issues
                                issues = None
                                ran_check = False
                                cache_key = f"{event_id}_{location}_{event['start'].strftime('%Y%m%d')}_{details.get('transportation_method','na')}"
                                
                                if cache_key in st.session_state.issues_cache:
                                    issues = st.session_state.issues_cache[cache_key]
                                    ran_check = True
                                else:
                                    with st.spinner("🔍 Checking for potential issues..."):
                                        event_with_details = {**event, **details, 'location': location}
                                        issues = st.session_state.scraper.check_for_issues(event_with_details)
                                        st.session_state.issues_cache[cache_key] = issues
                                        ran_check = True
                                
                                if ran_check and issues:
                                    for issue in issues:
                                        severity_icon = {
                                            'warning': '⚠️',
                                            'info': 'ℹ️',
                                            'critical': '🚨'
                                        }.get(issue['severity'], 'ℹ️')
                                        st.markdown(f"{severity_icon} {issue['message']}")
                                        if issue.get('details'):
                                            st.caption(f"ℹ️ {issue['details']}")
                                elif ran_check and issues == []:
                                    st.success("✅ No issues detected!")
                                
                                # Travel info
                                if details.get('arrival_time'):
                                    st.divider()
                                    st.markdown("**Travel Information**")
                                    st.info(f"💡 Suggested arrival time: {details['arrival_time']}")
                                    if details.get('departure_time'):
                                        st.info(f"🚗 Planned departure: {details['departure_time']}")
                            else:
                                st.warning("⚠️ No location available for this event")
                            
                            st.divider()
                            
                            if st.button(f"✓ Dismiss Alert", key=f"dismiss_{event_id}"):
                                st.session_state.alerts_checked.add(event_id)
                                st.rerun()
                
                # Summary of dismissed items
                dismissed_count = len(st.session_state.alerts_checked) + len(st.session_state.details_ignored)
                if dismissed_count > 0:
                    st.divider()
                    st.caption(f"✅ {dismissed_count} notification(s) dismissed")
    

    # Nudge Stats tab (only visible in demo mode)
    if st.session_state.demo_mode and tab_nudges:
        with tab_nudges:
            st.header("Nudge Statistics")
            st.markdown("*Aggregated nudges from alerts and detail requests*")
            st.info("Nudges track how often we prompt you. This tab keeps them out of the main flow.")
            col1, col2 = st.columns(2)
            with col1:
                current_date = st.session_state.timeline.get_current_date().strftime('%Y-%m-%d')
                daily_count = st.session_state.nudge_counters['daily'].get(current_date, 0)
                st.metric("Nudges Today", daily_count)
            with col2:
                current_week = st.session_state.timeline.get_current_date().strftime('%Y-W%W')
                weekly_count = st.session_state.nudge_counters['weekly'].get(current_week, 0)
                st.metric("Nudges This Week", weekly_count)
    
    # Debug Logs tab (only visible in demo mode)
    if st.session_state.demo_mode and tab_debug:
        with tab_debug:
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

            # Error log section
            st.subheader("⚠️ Errors")
            if logger.session_data.get('errors'):
                for err in logger.session_data['errors']:
                    timestamp = err['timestamp'].split('T')[1][:8] if 'T' in err['timestamp'] else err['timestamp']
                    msg = err.get('message', '')
                    detail = err.get('error') or ''
                    st.error(f"[{timestamp}] {msg}\n{detail}")
            else:
                st.info("No errors recorded")

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
