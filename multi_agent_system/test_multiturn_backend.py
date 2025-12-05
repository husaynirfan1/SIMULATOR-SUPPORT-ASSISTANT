"""
Test multi-turn OT form conversation through the backend
Simulates frontend sending previous_state
"""

from graph import MultiAgentSystem
import os
from dotenv import load_dotenv

load_dotenv()

def test_multiturn_with_backend():
    """Test complete multi-turn flow through MultiAgentSystem"""

    print("=" * 80)
    print("BACKEND MULTI-TURN TEST")
    print("=" * 80)

    # Initialize system
    morphik_uri = os.getenv("MORPHIK_URI", "http://localhost:8000")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    system = MultiAgentSystem(
        morphik_uri=morphik_uri,
        openrouter_api_key=openrouter_api_key
    )

    print("\n✅ System initialized\n")

    # Turn 1: Initial request
    print("=" * 80)
    print("TURN 1: Initial OT form request")
    print("=" * 80)
    query_1 = "I want to fill my overtime form"
    result_1 = system.query(query_1)

    print(f"Query: {query_1}")
    print(f"Active: {result_1.get('ot_conversation_active')}")
    print(f"State exists: {result_1.get('ot_conversation_state') is not None}")
    print(f"Response:\n{result_1['final_answer'][:500]}...")

    # Turn 2: Provide partial info (just name)
    print("\n" + "=" * 80)
    print("TURN 2: Provide just name")
    print("=" * 80)
    query_2 = "Name: John Doe"

    # Simulate frontend sending previous_state
    previous_state = {
        "ot_conversation_state": result_1.get("ot_conversation_state"),
        "ot_conversation_active": result_1.get("ot_conversation_active")
    }

    print(f"Query: {query_2}")
    print(f"Previous state active: {previous_state['ot_conversation_active']}")

    result_2 = system.query(query_2, previous_state)

    print(f"Active after: {result_2.get('ot_conversation_active')}")
    print(f"Agents consulted: {result_2.get('agents_consulted')}")
    print(f"Response:\n{result_2['final_answer'][:500]}...")

    # Turn 3: Provide rest of employee info
    print("\n" + "=" * 80)
    print("TURN 3: Provide rest of employee info")
    print("=" * 80)
    query_3 = """Designation: Engineer
Department: Technical
Grade: E4
Month: 12
Year: 2025"""

    previous_state_2 = {
        "ot_conversation_state": result_2.get("ot_conversation_state"),
        "ot_conversation_active": result_2.get("ot_conversation_active")
    }

    print(f"Query: {query_3}")
    print(f"Previous state active: {previous_state_2['ot_conversation_active']}")

    result_3 = system.query(query_3, previous_state_2)

    print(f"Active after: {result_3.get('ot_conversation_active')}")
    print(f"Response:\n{result_3['final_answer'][:500]}...")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    # Verify conversation stayed active
    if result_2.get('agents_consulted') and len(result_2.get('agents_consulted')) > 0:
        print("\n❌ FAILED: System consulted agents instead of continuing OT conversation")
        print(f"   Agents consulted: {result_2.get('agents_consulted')}")
    else:
        print("\n✅ SUCCESS: OT conversation stayed active through turns")


if __name__ == "__main__":
    test_multiturn_with_backend()
