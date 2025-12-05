"""
Test just the confirmation step to verify tool_calls are created
"""
from ot_conversation_manager import OTConversationManager, OTConversationState
import json

# Create manager and set it to AWAITING_CONFIRMATION state with sample data
manager = OTConversationManager()

# Manually set up state as if user already provided all info
manager.collected_data = {
    "employee_info": {
        "name": "John Doe",
        "designation": "Engineer",
        "department": "Technical",
        "grade": "E4",
        "month": 12,
        "year": 2025
    },
    "ot_entries": [
        {
            "date": "2025-12-06",
            "start_time": "18:00",
            "end_time": "22:00",
            "work_schedule": "Normal",
            "reason": "Project work"
        }
    ]
}
manager.state = OTConversationState.AWAITING_CONFIRMATION

print("=== Testing Confirmation Step ===")
print(f"Current state: {manager.state}")
print(f"Collected data: {json.dumps(manager.collected_data, indent=2)}")

# Process "confirm"
print("\n--- Processing 'confirm' ---")
result = manager.process_user_input("confirm")

print(f"\nStatus: {result.get('status')}")
print(f"Ready for tool: {result.get('ready_for_tool')}")
print(f"Message: {result.get('message')}")
print(f"Tool data exists: {result.get('tool_data') is not None}")

if result.get('tool_data'):
    print(f"\nTool data (first 200 chars): {result.get('tool_data')[:200]}")

    # Verify it's valid JSON
    try:
        parsed = json.loads(result.get('tool_data'))
        print(f"✅ Tool data is valid JSON with keys: {list(parsed.keys())}")
    except:
        print("❌ Tool data is NOT valid JSON")

print(f"\nFinal state: {manager.state}")
print(f"Manager state: {manager.state == OTConversationState.COMPLETE}")

# Show what graph.py should do with this
if result.get('ready_for_tool'):
    print("\n=== What graph.py should do ===")
    print("1. See ready_for_tool=True")
    print("2. Create tool_call:")
    print(f"   {{")
    print(f"       'name': 'fill_overtime_form',")
    print(f"       'args': {{'ot_data_json': '<json_data>'}},")
    print(f"       'id': 'call_...'")
    print(f"   }}")
    print("3. Attach to AIMessage.tool_calls")
    print("4. Return current_step='tools_checked'")
    print("5. _should_use_tools() sees tool_calls → routes to 'use_tools'")
    print("6. _execute_tools_node() calls fill_overtime_form.invoke()")
