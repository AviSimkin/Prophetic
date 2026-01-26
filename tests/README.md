# Test Suite Documentation

## Overview
This directory contains tests for the Prophetic calendar alerting system. Tests are organized by scope and purpose.

## Test Files

### `smoke_test.py`
Basic smoke tests that verify core module functionality:
- **Logger**: Session logging and event tracking
- **Calendar Parser**: Sample and Israeli calendar generation/parsing
- **LLM Module**: Question generation for missing event details
- **Web Scraper**: Issue checking functionality (mock and API modes)
- **Timeline**: Basic alert and date calculation functionality

**Run**: `python tests/smoke_test.py` or `pytest tests/smoke_test.py`

**Purpose**: Quick sanity check that all modules import and basic APIs work. Should run in <10 seconds.

---

### `test_alerts.py`
Comprehensive integration tests for the alert pipeline:

#### Test Coverage:
1. **`test_alert_window_1_day`**
   - Verifies that events 0-1 days away trigger alerts in the 1-day window
   - Ensures events >1 day away do NOT appear

2. **`test_alert_window_7_days`**
   - Verifies that events 0-7 days away trigger alerts in the 7-day window
   - Ensures events >7 days away do NOT appear

3. **`test_days_until_calculation`**
   - Validates that `days_until_event()` accurately calculates days remaining
   - Tests multiple time offsets (0, 1, 3, 7, 10 days)

4. **`test_real_world_scenario`**
   - **Critical test for user-reported bug**: Simulates Jan 26 → Jan 29/31 events
   - Confirms Business Meeting (Jan 29) and Lunch (Jan 31) appear in 7-day alerts
   - Confirms they do NOT appear in 1-day alerts (correctly filtered)

5. **`test_time_independence`**
   - Ensures alerts work regardless of current time-of-day
   - Tests midnight, morning, afternoon, and end-of-day times
   - Critical for date-only matching vs datetime matching bugs

**Run**: `python tests/test_alerts.py` or `pytest tests/test_alerts.py -v`

**Purpose**: Verify the alert pipeline correctly identifies events needing alerts. These tests caught the original bug where alerts only triggered on exact day matches, not within time windows.

---

## Running All Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_alerts.py

# Run specific test function
pytest tests/test_alerts.py::test_real_world_scenario
```

## Test Philosophy

### What These Tests Catch:
✅ Alert logic bugs (e.g., exact date match vs. window-based)  
✅ Date calculation errors (time-of-day interference)  
✅ Module integration issues  
✅ Import/dependency problems  

### What These Tests Don't Catch (Yet):
❌ Streamlit UI rendering  
❌ LLM API response quality  
❌ Web scraping accuracy  
❌ End-to-end user workflows  

### Future Test Additions:
- Tests for event detail collection flow
- Tests for nudge counter tracking
- Tests for alert deduplication logic
- Performance/load tests for large calendars
- Mock LLM response validation

## Debugging Failed Tests

If a test fails:

1. **Read the assertion message** - it tells you exactly what was expected vs actual
2. **Check the printed output** - tests print intermediate values for debugging
3. **Run the specific test** - `pytest tests/test_alerts.py::test_name -v -s`
   - `-v`: verbose output
   - `-s`: show print statements
4. **Check the date logic** - most bugs involve date/datetime confusion

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:
- No external dependencies required (works in mock mode)
- Deterministic outcomes (uses fixed dates, not `datetime.now()`)
- Fast execution (<10s total)
- Clear pass/fail signals

Example GitHub Actions workflow:
```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest tests/ -v
```
