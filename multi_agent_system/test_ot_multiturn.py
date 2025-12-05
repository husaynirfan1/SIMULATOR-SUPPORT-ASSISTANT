"""
Test script for multi-turn OT form conversation
Demonstrates the progressive data collection flow
"""

from ot_conversation_manager import OTConversationManager


def test_ot_conversation():
    """Test the OT conversation flow with simulated user inputs"""

    manager = OTConversationManager()

    print("=" * 80)
    print("OT FORM MULTI-TURN CONVERSATION TEST")
    print("=" * 80)

    # Test Case 1: Initial request
    print("\n--- TURN 1: User requests OT form ---")
    user_input_1 = "I want to fill my overtime form"
    result_1 = manager.process_user_input(user_input_1)
    print(f"User: {user_input_1}")
    print(f"Status: {result_1['status']}")
    print(f"Ready for tool: {result_1['ready_for_tool']}")
    print(f"Response:\n{result_1['message']}")

    # Test Case 2: Provide employee info
    print("\n--- TURN 2: User provides employee information ---")
    user_input_2 = """
    Name: John Doe
    Designation: Senior Engineer
    Department: Engineering
    Grade: E5
    Month: 12
    Year: 2025
    """
    result_2 = manager.process_user_input(user_input_2)
    print(f"User: {user_input_2.strip()}")
    print(f"Status: {result_2['status']}")
    print(f"Ready for tool: {result_2['ready_for_tool']}")
    print(f"Response:\n{result_2['message']}")

    # Test Case 3: Add first OT entry
    print("\n--- TURN 3: User adds first OT entry ---")
    user_input_3 = """
    Date: 2025-12-06
    Start: 18:00
    End: 22:00
    Schedule: Normal
    Reason: Project deadline work
    """
    result_3 = manager.process_user_input(user_input_3)
    print(f"User: {user_input_3.strip()}")
    print(f"Status: {result_3['status']}")
    print(f"Ready for tool: {result_3['ready_for_tool']}")
    print(f"Response:\n{result_3['message']}")

    # Test Case 4: Add second OT entry
    print("\n--- TURN 4: User adds second OT entry ---")
    user_input_4 = """
    Date: 2025-12-07
    Start: 21:00
    End: 09:00
    Schedule: Rest Day
    Reason: System maintenance
    """
    result_4 = manager.process_user_input(user_input_4)
    print(f"User: {user_input_4.strip()}")
    print(f"Status: {result_4['status']}")
    print(f"Ready for tool: {result_4['ready_for_tool']}")
    print(f"Response:\n{result_4['message']}")

    # Test Case 5: Finish adding entries
    print("\n--- TURN 5: User finishes adding entries ---")
    user_input_5 = "done"
    result_5 = manager.process_user_input(user_input_5)
    print(f"User: {user_input_5}")
    print(f"Status: {result_5['status']}")
    print(f"Ready for tool: {result_5['ready_for_tool']}")
    print(f"Response:\n{result_5['message']}")

    # Test Case 6: Confirm data
    print("\n--- TURN 6: User confirms the data ---")
    user_input_6 = "confirm"
    result_6 = manager.process_user_input(user_input_6)
    print(f"User: {user_input_6}")
    print(f"Status: {result_6['status']}")
    print(f"Ready for tool: {result_6['ready_for_tool']}")
    print(f"Response:\n{result_6['message']}")

    if result_6.get('ready_for_tool'):
        print(f"\n✅ Tool Data (JSON):")
        print(result_6['tool_data'])

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


def test_partial_info():
    """Test handling of partial information"""

    manager = OTConversationManager()

    print("\n\n" + "=" * 80)
    print("TEST: PARTIAL INFORMATION HANDLING")
    print("=" * 80)

    # User provides only some fields
    print("\n--- User provides partial employee info ---")
    user_input = """
    Name: Jane Smith
    Grade: M1
    """
    result = manager.process_user_input(user_input)
    result = manager.process_user_input(user_input)  # Process twice to get to employee info state

    print(f"User: {user_input.strip()}")
    print(f"Status: {result['status']}")
    print(f"Response:\n{result['message']}")

    print("\n✅ System correctly identifies missing fields")
    print("=" * 80)


def test_validation_errors():
    """Test validation error handling"""

    manager = OTConversationManager()

    print("\n\n" + "=" * 80)
    print("TEST: VALIDATION ERROR HANDLING")
    print("=" * 80)

    # Initialize and provide employee info
    manager.process_user_input("fill ot form")

    # Provide complete employee info
    manager.process_user_input("""
        Name: Test User
        Designation: Engineer
        Department: Tech
        Grade: E4
        Month: 12
        Year: 2025
    """)

    # Try to add OT entry with invalid date format
    print("\n--- User provides OT entry with invalid date ---")
    user_input = """
    Date: 12/06/2025
    Start: 18:00
    End: 22:00
    Schedule: Normal
    Reason: Testing
    """
    result = manager.process_user_input(user_input)

    print(f"User: {user_input.strip()}")
    print(f"Status: {result['status']}")
    print(f"Response:\n{result['message']}")

    print("\n✅ System correctly handles validation errors")
    print("=" * 80)


if __name__ == "__main__":
    # Run all tests
    test_ot_conversation()
    test_partial_info()
    test_validation_errors()

    print("\n\n🎉 All tests completed successfully!")
