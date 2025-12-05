import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Add path to morphik SDK
sys.path.append("/home/husaynirfan/sse-ai-v2/morphik-core/sdks/python")

from agents import PlanningAgent

# Load environment variables
load_dotenv()

def test_planning_agent():
    print("Testing PlanningAgent with ReAct/Think mode...")
    
    # Initialize LLM
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Skipping test: OPENROUTER_API_KEY not found.")
        return

    llm = ChatOpenAI(
        model="x-ai/grok-4.1-fast:free", # Use a cheap/free model for testing
        temperature=0,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1"
    )
    
    # Initialize PlanningAgent
    agent = PlanningAgent(morphik_uri="http://localhost:8080", llm=llm)
    
    # Test queries
    queries = [
        "I need to fix a vibration issue in the motion system.",
        "The screen is flickering and the touch panel is unresponsive.",
        "Check for any security vulnerabilities in the network.",
        "I need a diagram of the system architecture.",
        "What is the stock level for the actuator?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        agents = agent.route_query(query)
        print(f"Selected Agents: {agents}")

if __name__ == "__main__":
    test_planning_agent()
