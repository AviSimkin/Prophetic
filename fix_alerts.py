#!/usr/bin/env python
"""Fix alert tracking to use event_id only instead of window-based keys."""

with open('app.py', 'r') as f:
    content = f.read()

# Replace window-based tracking with event_id-only tracking
replacements = [
    ('alert_key = f"{event_id}_{days_before}days"', '# Track by event_id only to prevent repeats across windows'),
    ('if alert_key not in st.session_state.alerts_checked:', 'if event_id not in st.session_state.alerts_checked:'),
    ('nudge_counted_key = f"{alert_key}_counted"', 'nudge_counted_key = f"{event_id}_alert_nudge_counted"'),
]

for old, new in replacements:
    content = content.replace(old, new)

# Fix button references
content = content.replace(
    'if st.button(f"✓ Mark as Reviewed", key=f"reviewed_{alert_key}"):',
    'if st.button(f"✓ Mark as Reviewed", key=f"reviewed_{event_id}"):',
)
content = content.replace(
    'st.session_state.alerts_checked.add(alert_key)',
    'st.session_state.alerts_checked.add(event_id)',
)

with open('app.py', 'w') as f:
    f.write(content)

print('✅ Alert tracking fixed: event_id only (no per-window duplicates)')
