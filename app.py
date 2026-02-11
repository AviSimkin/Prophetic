"""
Prophetic - Calendar Event Management with Predictive Alerts
"""
import os
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.calendar_parser import parse_calendar_file, create_israeli_calendar
from src.llm_module import LLMModule
from src.timeline_simulator import TimelineSimulator
from src.prophetic_logger import get_logger, log_event, log_info, log_error
from src.agents import EventFilterAgent, AlertValidatorAgent, HiccupAgent


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

if 'hiccup_agent' not in st.session_state:
    st.session_state.hiccup_agent = HiccupAgent(api_key=st.session_state.api_key)

if 'event_filter_agent' not in st.session_state:
    st.session_state.event_filter_agent = EventFilterAgent(api_key=st.session_state.api_key)

if 'alert_validator_agent' not in st.session_state:
    st.session_state.alert_validator_agent = AlertValidatorAgent(api_key=st.session_state.api_key)

if 'nudge_history' not in st.session_state:
    st.session_state.nudge_history = []  # List of (event_id, timestamp) tuples

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

if 'suppressed_notifications' not in st.session_state:
    st.session_state.suppressed_notifications = []  # List of {event_id, event_name, date, reason, timestamp}



def is_actionable_event(event: dict) -> bool:
    """
    Use EventFilterAgent to determine if event should be processed.
    Falls back to heuristic if agent fails.
    Records suppression reason if event is filtered out.
    """
    try:
        decision = st.session_state.event_filter_agent.should_process_event(event)
        # Logging now happens inside the agent (only on cache miss)
        if decision.should_ignore:
            # Record suppression
            event_id = f"{event['name']}_{event['start']}"
            reason = decision.reason or "Event filtered as not actionable"
            _record_suppression(event_id, event['name'], event['start'], reason, 'event_filter')
        return not decision.should_ignore
    except Exception as e:
        # Fallback to original heuristic on error
        log_error(f"Event filter agent error: {e}")
        name = event.get('name', '').lower()
        auto_keywords = [
            'holiday', 'observance', 'observed', 'day off', 'reminder',
            'birthday', 'anniversary', 'payday', 'bill', 'invoice'
        ]
        if any(keyword in name for keyword in auto_keywords):
            event_id = f"{event['name']}_{event['start']}"
            _record_suppression(event_id, event['name'], event['start'], f"Event type not actionable (matched keyword)", 'heuristic_filter')
            return False
        start = event.get('start')
        end = event.get('end')
        if isinstance(start, datetime) and isinstance(end, datetime):
            duration = end - start
            if start.hour == 0 and start.minute == 0 and duration >= timedelta(hours=23):
                event_id = f"{event['name']}_{event['start']}"
                _record_suppression(event_id, event['name'], event['start'], "All-day event not requiring travel prep", 'heuristic_filter')
                return False
        return True


def _count_nudges_today() -> int:
    """Count how many nudges/alerts were shown today."""
    today = datetime.now().date()
    count = sum(1 for event_id, ts in st.session_state.nudge_history 
                if datetime.fromtimestamp(ts).date() == today)
    return count


def _count_nudges_this_week() -> int:
    """Count how many nudges/alerts were shown this week."""
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    count = sum(1 for event_id, ts in st.session_state.nudge_history 
                if datetime.fromtimestamp(ts) >= week_start)
    return count


def _record_nudge(event_id: str) -> None:
    """Record that a nudge/alert was shown for an event."""
    st.session_state.nudge_history.append((event_id, datetime.now().timestamp()))


def _record_suppression(event_id: str, event_name: str, event_date: datetime, reason: str, source: str) -> None:
    """Record a suppressed notification with its reason."""
    # Check if this suppression already exists
    existing = [s for s in st.session_state.suppressed_notifications if s['event_id'] == event_id and s['source'] == source]
    if not existing:
        st.session_state.suppressed_notifications.append({
            'event_id': event_id,
            'event_name': event_name,
            'event_date': event_date,
            'reason': reason,
            'source': source,
            'timestamp': datetime.now()
        })


def _get_effective_detail(event: dict, details: dict, field: str) -> str:
    """Return effective detail value, using event defaults if available."""
    if details.get(field):
        return details.get(field)

    if field == 'location':
        return event.get('location', '') or ''

    if field == 'arrival_time':
        start_dt = event.get('start')
        return start_dt.strftime('%H:%M') if start_dt else ''

    if field == 'event_end_time':
        end_dt = event.get('end')
        return end_dt.strftime('%H:%M') if end_dt else ''

    return ''


def main():
    """Main application"""
    st.title("🔮 Prophetic Calendar")
    st.markdown("*Predictive event management with proactive alerts*")
    
    # AI disclaimer - always visible
    with st.expander("ℹ️ About AI-Powered Alerts", expanded=False):
        st.info(
            "🤖 **About This System**\n\n"
            "This intelligent assistant analyzes your calendar to surface potential hiccups. The system:\n"
            "- 🔍 **Searches the web** for relevant information (weather, local events, road conditions)\n"
            "- 🗺️ **Checks travel times** using Google Maps to detect traffic and routing issues\n"
            "- 🔕 **Suppresses irrelevant notifications** to avoid over-burdening you with unnecessary alerts \n\n"
            "⚠️ **AI Disclaimer**: This system uses artificial intelligence which can make mistakes. "
            "**Please verify important information independently** before making travel decisions. "
            "Use these alerts as helpful guidance, not as definitive facts. It is advised to visit the suppressed notifications section to review them in case we missed something important."
        )
    
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
            st.header("🔑 API Keys (Optional)")

        # Google Gemini API
        env_key_present = bool(ENV_API_KEY)
        if env_key_present:
            st.caption("Using keys from .env unless you override below.")

        api_key = st.text_input(
            "Google Gemini API Key",
            type="password",
            placeholder="Using .env value" if env_key_present else "Enter Google Gemini API key",
            help="Provide a Gemini API key for LLM features. Leave empty to use mock mode."
        )
        
        # SerpAPI Key
        env_serpapi_key = os.getenv("SERPAPI_KEY")
        serpapi_key = st.text_input(
            "SerpAPI Key",
            type="password",
            placeholder="Using .env value" if env_serpapi_key else "Enter SerpAPI key",
            help="Required for Google Maps directions and traffic analysis"
        )
        
        # Tavily API Key
        env_tavily_key = os.getenv("TAVILY_API_KEY")
        tavily_key = st.text_input(
            "Tavily API Key",
            type="password",
            placeholder="Using .env value" if env_tavily_key else "Enter Tavily API key",
            help="Required for web search (weather, events, closures)"
        )

        # Apply overrides only when user provides a non-empty input
        if api_key:
            st.session_state.api_key = api_key
            st.session_state.llm_module = LLMModule(api_key=api_key)
            st.session_state.hiccup_agent = HiccupAgent(api_key=api_key)
            st.session_state.event_filter_agent = EventFilterAgent(api_key=api_key)
            st.session_state.alert_validator_agent = AlertValidatorAgent(api_key=api_key)
        elif st.session_state.api_key != ENV_API_KEY:
            # Reset to env key if user cleared the field
            st.session_state.api_key = ENV_API_KEY
            st.session_state.llm_module = LLMModule(api_key=ENV_API_KEY)
            st.session_state.hiccup_agent = HiccupAgent(api_key=ENV_API_KEY)
            st.session_state.event_filter_agent = EventFilterAgent(api_key=ENV_API_KEY)
            st.session_state.alert_validator_agent = AlertValidatorAgent(api_key=ENV_API_KEY)
        
        # Store SerpAPI and Tavily keys in session state
        if serpapi_key:
            st.session_state.serpapi_key = serpapi_key
        elif 'serpapi_key' not in st.session_state:
            st.session_state.serpapi_key = env_serpapi_key
            
        if tavily_key:
            st.session_state.tavily_key = tavily_key
        elif 'tavily_key' not in st.session_state:
            st.session_state.tavily_key = env_tavily_key
        
    # Main content
    tabs_list = ["🏠 Setup", "📅 Calendar Upload", "🔔 Notifications", "🔕 Suppressed"]
    if st.session_state.demo_mode:
        tabs_list.append("📊 Nudge Stats")
        tabs_list.append("📊 Debug Logs")
    
    tabs = st.tabs(tabs_list)
    tab_setup = tabs[0]
    tab1 = tabs[1]
    tab_notifications = tabs[2]
    tab_suppressed = tabs[3]
    tab_nudges = tabs[4] if st.session_state.demo_mode else None
    tab_debug = tabs[5] if st.session_state.demo_mode else None
    
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
                if st.button("🇮🇱 Load Demo Calendar"):
                    israeli_calendar = create_israeli_calendar()
                    events = parse_calendar_file(israeli_calendar)
                    st.session_state.events = events
                    log_event('calendar_load', 'Israeli Calendar', {'event_count': len(events)})
                    st.success(f"✅ Loaded {len(events)} demo events!")
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
                                if details.get('event_end_time'):
                                    st.write(f"**🏁 Event ends:** {details['event_end_time']}")
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
                if st.session_state.events:
                    st.info("ℹ️ No notifications are being shown to the user.")
                else:
                    st.info("👆 Please upload a calendar file first!")
            else:
                st.success(f"📋 {len(events_within_7days)} event(s) within 7 days")
                
                for event in events_within_7days:
                    event_id = f"{event['name']}_{event['start']}"
                    days_until = st.session_state.timeline.days_until_event(event)
                    
                    # Ensure event_details entry exists
                    if event_id not in st.session_state.event_details:
                        st.session_state.event_details[event_id] = {}
                        
                        # Pre-populate ONLY with data from calendar (not guesses)
                        # This allows browser auto-fill to work for the rest
                        if event.get('location'):
                            st.session_state.event_details[event_id]['location'] = event.get('location')
                        if event.get('start'):
                            st.session_state.event_details[event_id]['arrival_time'] = event.get('start').strftime('%H:%M')
                        if event.get('end'):
                            st.session_state.event_details[event_id]['event_end_time'] = event.get('end').strftime('%H:%M')
                        # Don't pre-fill transportation_method or departure_location
                        # Let user fill via browser auto-fill or manual entry
                    
                    details = st.session_state.event_details[event_id]
                    
                    # Check if detail request should be auto-ignored (24 hours passed)
                    if event_id in st.session_state.detail_request_timestamps:
                        request_time = st.session_state.detail_request_timestamps[event_id]
                        hours_since_request = (datetime.now() - request_time).total_seconds() / 3600
                        if hours_since_request >= 24 and event_id not in st.session_state.details_ignored:
                            st.session_state.details_ignored.add(event_id)
                            log_event('details_auto_ignored', event['name'], {'reason': '24_hours_passed'})
                    
                    required_fields = ['location', 'arrival_time', 'event_end_time', 'departure_location', 'transportation_method']
                    details_complete = all(_get_effective_detail(event, details, field) for field in required_fields)
                    details_ignored = event_id in st.session_state.details_ignored
                    alert_generated = event_id in st.session_state.alerts_generated
                    alert_dismissed = event_id in st.session_state.alerts_checked
                    
                    # Determine notification type
                    if not details_complete and not details_ignored:
                        # Show detail request
                        notification_type = "detail_request"
                        icon = "📝"
                        title = f"{icon} Details Needed: {event['name']}"
                    elif (details_complete or details_ignored):
                        # Details complete/ignored - check if we should show alert
                        # Mark as alert_generated so we run the check
                        if not alert_generated:
                            st.session_state.alerts_generated.add(event_id)
                            alert_generated = True
                        
                        if alert_dismissed:
                            # Already dismissed, skip
                            continue
                        
                        # If user ignored details, don't run hiccup check - just suppress
                        if details_ignored:
                            _record_suppression(event_id, event['name'], event['start'], 
                                              "User chose to ignore detail request", 'details_ignored_by_user')
                            continue
                        
                        # Check if we have cached issues or need to run check
                        location = details.get('location') or event.get('location', '')
                        cache_key = f"{event_id}_{location}_{event['start'].strftime('%Y%m%d')}_{details.get('transportation_method','na')}"
                        
                        # If not cached, run the check NOW before deciding to display
                        if cache_key not in st.session_state.issues_cache:
                            # Run the check silently to determine if we should show
                            event_with_details = {**event, **details, 'location': location}
                            raw_issues = st.session_state.hiccup_agent.check_for_hiccups(event_with_details)
                            
                            # Always validate
                            try:
                                nudges_today = _count_nudges_today()
                                nudges_this_week = _count_nudges_this_week()
                                
                                validation_result = st.session_state.alert_validator_agent.validate_alerts(
                                    event=event_with_details,
                                    issues=raw_issues,
                                    event_importance="medium",
                                    nudges_today=nudges_today,
                                    nudges_this_week=nudges_this_week,
                                    days_until_event=days_until
                                )
                                issues = [
                                    {
                                        'message': i.message,
                                        'details': i.details,
                                        'severity': i.severity,
                                        'source': i.source
                                    }
                                    for i in validation_result.filtered_issues
                                ]
                            except Exception as e:
                                log_error(f"Alert validation error: {e}")
                                issues = raw_issues if raw_issues else []
                            
                            # Cache the results
                            st.session_state.issues_cache[cache_key] = {
                                'issues': issues,
                                'validation': validation_result if 'validation_result' in locals() else None
                            }
                        
                        # Now check if we have issues
                        cached_data = st.session_state.issues_cache[cache_key]
                        if isinstance(cached_data, dict) and 'issues' in cached_data:
                            has_issues = len(cached_data['issues']) > 0
                        else:
                            has_issues = len(cached_data) > 0 if cached_data else False
                        
                        if has_issues:
                            # Show alert - we have issues to display
                            notification_type = "alert"
                            icon = "⚠️"
                            title = f"{icon} Alert: {event['name']}"
                        else:
                            # No issues found - suppress and track
                            _record_suppression(event_id, event['name'], event['start'], 
                                              "No issues detected - all checks passed", 'no_issues_after_check')
                            continue
                    else:
                        # Already dismissed, skip
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
                            missing_fields = [f for f in required_fields if not _get_effective_detail(event, details, f)]
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
                            
                            # Arrival time
                            current_arrival = details.get('arrival_time', '')
                            arrival_value = st.text_input(
                                f"⏰ What time do you need to arrive?",
                                value=current_arrival,
                                placeholder="HH:MM (e.g., 09:30)",
                                key=f"{event_id}_arrival_time"
                            )
                            
                            # Event end time
                            current_end_time = details.get('event_end_time', '')
                            end_time_value = st.text_input(
                                f"🏁 What time does the event end?",
                                value=current_end_time,
                                placeholder="HH:MM (e.g., 17:00)",
                                key=f"{event_id}_event_end_time"
                            )
                            
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
                            
                            st.divider()
                            
                            # Action buttons
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"💾 Save Details", key=f"save_{event_id}"):
                                    # Now save the form values to details
                                    if location_value:
                                        details['location'] = location_value
                                    if arrival_value:
                                        try:
                                            parsed_value = st.session_state.llm_module.parse_response(arrival_value, 'arrival_time')
                                            details['arrival_time'] = parsed_value
                                        except ValueError as e:
                                            st.error(f"Invalid arrival time format: {e}")
                                            st.stop()
                                    if end_time_value:
                                        try:
                                            parsed_value = st.session_state.llm_module.parse_response(end_time_value, 'event_end_time')
                                            details['event_end_time'] = parsed_value
                                        except ValueError as e:
                                            st.error(f"Invalid end time format: {e}")
                                            st.stop()
                                    if transport_method:
                                        details['transportation_method'] = transport_method
                                    
                                    # Check if all required fields are filled
                                    if all(_get_effective_detail(event, details, field) for field in required_fields):
                                        log_event('event_details_saved', event['name'], details)
                                        st.success("✅ Details saved!")
                                        st.rerun()
                                    else:
                                        missing = [f for f in required_fields if not _get_effective_detail(event, details, f)]
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
                                
                                # Get cached issues (they were already checked before deciding to show this alert)
                                issues = None
                                validation_result = None
                                cache_key = f"{event_id}_{location}_{event['start'].strftime('%Y%m%d')}_{details.get('transportation_method','na')}"
                                
                                # At this point, cache must exist because we checked before showing
                                if cache_key in st.session_state.issues_cache:
                                    cached_data = st.session_state.issues_cache[cache_key]
                                    if isinstance(cached_data, dict) and 'validation' in cached_data:
                                        issues = cached_data['issues']
                                        validation_result = cached_data['validation']
                                    else:
                                        issues = cached_data
                                
                                # Display validation priority if available
                                if validation_result:
                                    # Alert user if validator found problems
                                    if validation_result.removed_count > 0:
                                        st.warning(f"⚠️ Validator removed {validation_result.removed_count} potentially incorrect alert(s). Please verify remaining warnings.")
                                    
                                    if not validation_result.is_valid and issues:
                                        st.warning("⚠️ Alert validation flagged potential issues - please verify this information independently.")
                                
                                # Display issues (we know there are issues because we checked before showing)
                                if issues:
                                    # Record that we showed this alert
                                    _record_nudge(event_id)
                                    for issue in issues:
                                        severity_icon = {
                                            'warning': '⚠️',
                                            'info': 'ℹ️',
                                            'critical': '🚨'
                                        }.get(issue['severity'], 'ℹ️')
                                        st.markdown(f"{severity_icon} {issue['message']}")
                                        if issue.get('details'):
                                            st.caption(f"ℹ️ {issue['details']}")
                                
                                # Travel info
                                if details.get('arrival_time'):
                                    st.divider()
                                    st.markdown("**Your Schedule**")
                                    st.info(f"🕐 Arrival time: {details['arrival_time']}")
                                    if details.get('event_end_time'):
                                        st.info(f"🏁 Event ends: {details['event_end_time']}")
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
    
    # Suppressed Notifications tab
    if tab_suppressed:
        with tab_suppressed:
            st.header("🔕 Suppressed Notifications")
            st.markdown("*Events and alerts that were filtered out or found to have no issues*")
            st.info("This tab shows why certain events don't appear in your main Notifications feed.")
            
            if not st.session_state.suppressed_notifications:
                st.info("No suppressions yet. As events are filtered or checked, they'll appear here.")
            else:
                # Sort by timestamp, most recent first
                sorted_suppressions = sorted(
                    st.session_state.suppressed_notifications, 
                    key=lambda x: x['timestamp'], 
                    reverse=True
                )
                
                # Group by source for better organization
                by_source = {}
                for suppression in sorted_suppressions:
                    source = suppression['source']
                    if source not in by_source:
                        by_source[source] = []
                    by_source[source].append(suppression)
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Suppressed", len(sorted_suppressions))
                with col2:
                    event_filter_count = len(by_source.get('event_filter', [])) + len(by_source.get('heuristic_filter', []))
                    st.metric("Filtered Events", event_filter_count)
                with col3:
                    no_issues_count = len(by_source.get('no_issues', [])) + len(by_source.get('no_issues_after_check', []))
                    st.metric("No Issues Found", no_issues_count)
                
                st.divider()
                
                # Display by category
                source_labels = {
                    'event_filter': '🔍 Filtered by Event Filter Agent',
                    'heuristic_filter': '🔍 Filtered by Heuristic',
                    'no_issues': '✅ No Issues Detected (Cached)',
                    'no_issues_after_check': '✅ No Issues Detected (After Check)'
                }
                
                for source, label in source_labels.items():
                    if source in by_source:
                        with st.expander(f"{label} ({len(by_source[source])} events)", expanded=False):
                            for suppression in by_source[source]:
                                event_date_str = suppression['event_date'].strftime('%Y-%m-%d %H:%M')
                                timestamp_str = suppression['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                                
                                st.markdown(f"**{suppression['event_name']}** - {event_date_str}")
                                st.caption(f"📝 Reason: {suppression['reason']}")
                                st.caption(f"🕐 Suppressed at: {timestamp_str}")
                                st.divider()

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
                    agent = call['metadata'].get('agent', 'unknown')
                    event_name = call['metadata'].get('event_name', '')
                    tokens = f"{call.get('input_tokens', '?')} in + {call.get('output_tokens', '?')} out"
                    
                    # Build expander label with agent icon and event name
                    agent_icons = {
                        'event_filter': '🔍',
                        'alert_validator': '✅',
                        'hiccup_react': '🚨',
                        'question_generator': '❓'
                    }
                    agent_icon = agent_icons.get(agent, '🤖')
                    event_part = f" | Event: {event_name}" if event_name else ""
                    
                    with st.expander(f"#{i+1} {agent_icon} {agent} [{timestamp}]{event_part} ({tokens})", expanded=False):
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
