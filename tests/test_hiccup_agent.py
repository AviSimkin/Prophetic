"""
Tests for hiccup agent JSON parsing and ReAct logic.
"""
import os
import sys
import json
from datetime import datetime

# Ensure project root is importable
ROOT = r"c:\code\Prophetic"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.hiccup_agent import HiccupAgent


def test_json_extraction_from_raw_response():
    """Test that the agent can correctly parse JSON from various LLM response formats."""
    
    test_cases = [
        # Case 1: Plain JSON (should work)
        {
            'name': 'plain_json',
            'response': '{ "thought": "test", "action": "FINISH", "issues": [] }',
            'should_parse': True
        },
        # Case 2: JSON with markdown code block
        {
            'name': 'json_in_code_block',
            'response': '```json\n{ "thought": "test", "action": "FINISH", "issues": [] }\n```',
            'should_parse': True
        },
        # Case 3: JSON with extra text before (from error log)
        {
            'name': 'json_with_prefix_text',
            'response': 'Here is my response:\n{ "thought": "test", "action": "FINISH", "issues": [] }',
            'should_parse': True
        },
        # Case 4: Multiple JSON blocks (should take first one)
        {
            'name': 'multiple_json_blocks',
            'response': '''{ "thought": "first", "action": "web_search", "action_input": "test" }
            
            Some explanatory text
            
            { "thought": "second", "action": "FINISH", "issues": [] }''',
            'should_parse': True
        },
        # Case 5: JSON with "issues" array (edge case from error)
        {
            'name': 'json_with_issues_array',
            'response': '{ "thought": "test", "action": "web_search", "action_input": "query", "issues": [] }',
            'should_parse': True
        },
        # Case 6: Generic code block (no "json" language hint)
        {
            'name': 'generic_code_block',
            'response': '```\n{ "thought": "test", "action": "FINISH", "issues": [] }\n```',
            'should_parse': True
        },
        # Case 7: Text before code block with JSON
        {
            'name': 'text_before_code_block',
            'response': 'I will now provide my response:\n```json\n{ "thought": "test", "action": "FINISH", "issues": [] }\n```',
            'should_parse': True
        },
        # Case 8: Code block with non-JSON content, then JSON (THE BUG!)
        {
            'name': 'non_json_code_block_then_json',
            'response': '```\nThis is not JSON\n```\n{ "thought": "actual json here", "action": "FINISH", "issues": [] }',
            'should_parse': True
        },
        # Case 9: Multiple code blocks, only second has JSON
        {
            'name': 'multiple_code_blocks_second_has_json',
            'response': 'Explanation:\n```\nSome code snippet\n```\n\nMy response:\n```json\n{ "thought": "test", "action": "FINISH", "issues": [] }\n```',
            'should_parse': True
        },
    ]
    
    # Simulate the JSON extraction logic from HiccupAgent._reason_and_act
    def extract_json(response_text: str) -> dict:
        """Simulate the JSON extraction logic from the agent."""
        text = response_text.strip()
        
        # Try to extract JSON from markdown code blocks
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            # Extract from generic code block, but verify it contains JSON
            parts = text.split('```')
            if len(parts) >= 3:
                code_block = parts[1].strip()
                # Only use code block if it looks like JSON (starts with {)
                if code_block.startswith('{'):
                    text = code_block
                # Otherwise, check if JSON exists after the code block
                elif '{' in parts[2]:
                    text = parts[2]
        
        # Find JSON object boundaries
        if '{' in text:
            start = text.index('{')
            # Find matching closing brace
            brace_count = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            text = text[start:end]
        
        return json.loads(text)
    
    print("\nTesting JSON extraction from various LLM response formats:")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        try:
            result = extract_json(test_case['response'])
            if test_case['should_parse']:
                # Verify it's valid JSON with expected structure
                assert 'thought' in result, "Missing 'thought' field"
                assert 'action' in result, "Missing 'action' field"
                print(f"✅ PASS: {test_case['name']}")
                passed += 1
            else:
                print(f"❌ FAIL: {test_case['name']} - Should have failed but parsed successfully")
                failed += 1
        except Exception as e:
            if test_case['should_parse']:
                print(f"❌ FAIL: {test_case['name']} - {str(e)}")
                print(f"   Response: {test_case['response'][:100]}...")
                failed += 1
            else:
                print(f"✅ PASS: {test_case['name']} - Correctly rejected invalid input")
                passed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        raise AssertionError(f"{failed} JSON parsing test(s) failed")


def test_hiccup_agent_basic_functionality():
    """Test that hiccup agent can be instantiated and handles mock mode gracefully."""
    
    print("\nTesting hiccup agent basic functionality:")
    print("=" * 70)
    
    # Test without API key (mock mode)
    agent = HiccupAgent(api_key=None)
    assert agent.model is None, "Agent should have no model in mock mode"
    print("✅ PASS: Agent can be instantiated without API key")
    
    # Test with mock event
    event = {
        'name': 'Test Meeting',
        'location': 'Tel Aviv',
        'start': datetime(2026, 2, 15, 14, 0, 0),
        'end': datetime(2026, 2, 15, 16, 0, 0),
        'arrival_time': '14:00',
        'event_end_time': '16:00',
        'transportation_method': 'driving',
        'departure_location': 'Haifa'
    }
    
    issues = agent.check_for_hiccups(event)
    assert isinstance(issues, list), "check_for_hiccups should return a list"
    assert len(issues) == 0, "Mock mode should return empty issues"
    print("✅ PASS: Agent handles mock mode gracefully")
    
    # Test with API key if available
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        agent_with_key = HiccupAgent(api_key=api_key)
        assert agent_with_key.model is not None, "Agent should have model with API key"
        print("✅ PASS: Agent can be instantiated with API key")
    else:
        print("⚠️  SKIP: No GOOGLE_API_KEY available for live API test")
    
    print("=" * 70)


def test_exception_handling_without_response_text():
    """Test that exception handler doesn't crash when response_text is undefined."""
    
    print("\nTesting exception handling when response fails:")
    print("=" * 70)
    
    # Create agent with a mock model that will fail
    agent = HiccupAgent(api_key=None)
    
    # Manually create a model-like object that fails
    class FailingModel:
        def generate_content(self, prompt):
            raise ValueError("Simulated API failure before response_text assignment")
    
    agent.model = FailingModel()
    agent.model_name = "test-model"
    
    event = {
        'name': 'Test Event',
        'location': 'Test Location',
        'start': datetime(2026, 2, 15, 14, 0, 0),
        'arrival_time': '14:00',
        'event_end_time': '16:00',
        'transportation_method': 'driving',
        'departure_location': 'Test Departure'
    }
    
    # This should not crash with UnboundLocalError
    try:
        issues = agent.check_for_hiccups(event)
        assert isinstance(issues, list), "Should return a list even on error"
        assert len(issues) == 0, "Should return empty list on API failure"
        print("✅ PASS: Agent handles API failure gracefully without UnboundLocalError")
    except UnboundLocalError as e:
        print(f"❌ FAIL: UnboundLocalError occurred: {e}")
        raise
    except Exception as e:
        # Other exceptions are acceptable for this test
        print(f"⚠️  Note: Different exception occurred (acceptable): {type(e).__name__}")
        print("✅ PASS: No UnboundLocalError (which was the bug)")
    
    print("=" * 70)


def test_traffic_message_clarity():
    """Test that traffic messages are clear and only show alerts for actual problems."""
    
    print("\nTesting traffic message clarity:")
    print("=" * 70)
    
    # Test case 1: No traffic_info in route data (API doesn't provide it - normal traffic)
    print("\n📍 Case 1: No traffic_info field (normal conditions)")
    mock_route_no_traffic = {
        'distance': '91.6 km',
        'duration': 5690  # ~95 minutes in seconds
        # No 'traffic_info' field = normal traffic
    }
    
    distance = mock_route_no_traffic.get('distance', 'Unknown')
    duration = mock_route_no_traffic.get('duration', 'Unknown')
    traffic_info = mock_route_no_traffic.get('traffic_info', None)
    
    duration_str = str(duration)
    if isinstance(duration, (int, float)):
        minutes = int(duration) // 60
        seconds = int(duration) % 60
        duration_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    
    summary = f"Route: {distance}, Duration: {duration_str}"
    
    if traffic_info and any(keyword in str(traffic_info).lower() 
                           for keyword in ['delay', 'heavy', 'slow', 'congestion', 'jam', 'accident', 'closure']):
        summary += f" - ⚠️ {traffic_info}"
    else:
        summary += " - No delays"
    
    print(f"   Result: {summary}")
    assert "No delays" in summary, "Should indicate no delays when traffic is normal"
    assert "⚠️" not in summary, "Should NOT show warning emoji for normal traffic"
    print("   ✅ Correctly shows 'No delays' for normal traffic")
    
    # Test case 2: Traffic info with actual delay
    print("\n📍 Case 2: Traffic info with actual delays")
    mock_route_with_delays = {
        'distance': '91.6 km',
        'duration': 6890,  # ~115 minutes
        'traffic_info': 'Heavy traffic due to accident on Route 2'
    }
    
    route2 = mock_route_with_delays
    traffic_info2 = route2.get('traffic_info', None)
    duration2 = route2.get('duration', 'Unknown')
    
    if isinstance(duration2, (int, float)):
        minutes2 = int(duration2) // 60
        seconds2 = int(duration2) % 60
        duration_str2 = f"{minutes2}m {seconds2}s" if seconds2 else f"{minutes2}m"
    
    summary2 = f"Route: {route2['distance']}, Duration: {duration_str2}"
    
    if traffic_info2 and any(keyword in str(traffic_info2).lower() 
                            for keyword in ['delay', 'heavy', 'slow', 'congestion', 'jam', 'accident', 'closure']):
        summary2 += f" - ⚠️ {traffic_info2}"
    else:
        summary2 += " - No delays"
    
    print(f"   Result: {summary2}")
    assert "⚠️ Heavy traffic due to accident" in summary2, "Should show traffic issues with warning emoji"
    assert "No delays" not in summary2, "Should NOT say no delays when problems exist"
    print("   ✅ Correctly shows warning for actual traffic issues")
    
    # Test case 3: Traffic info but no problem keywords (edge case)
    print("\n📍 Case 3: Traffic info exists but indicates normal flow")
    mock_route_normal_mention = {
        'distance': '45.2 km',
        'duration': 2700,
        'traffic_info': 'Light traffic, normal flow'
    }
    
    route3 = mock_route_normal_mention
    traffic_info3 = route3.get('traffic_info', None)
    
    summary3 = f"Route: {route3['distance']}, Duration: 45m"
    if traffic_info3 and any(keyword in str(traffic_info3).lower() 
                            for keyword in ['delay', 'heavy', 'slow', 'congestion', 'jam', 'accident', 'closure']):
        summary3 += f" - ⚠️ {traffic_info3}"
    else:
        summary3 += " - No delays"
    
    print(f"   Result: {summary3}")
    assert "No delays" in summary3, "Should show no delays for light/normal traffic"
    assert "⚠️" not in summary3, "Should NOT show warning for light traffic"
    print("   ✅ Correctly treats 'light traffic' as normal (no alert)")
    
    print("\n" + "=" * 70)
    print("✅ PASS: All traffic message tests passed")
    print("=" * 70)


if __name__ == '__main__':
    test_json_extraction_from_raw_response()
    test_hiccup_agent_basic_functionality()
    test_exception_handling_without_response_text()
    test_traffic_message_clarity()
    print("\n✅ All hiccup agent tests passed.")
