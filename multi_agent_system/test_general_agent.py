"""
Test script for General Agent integration
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_general_agent():
    """Test general agent responses"""
    from agents import GeneralAgent
    from langchain_openai import ChatOpenAI
    
    # Initialize with a simple LLM
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1"
    )
    
    agent = GeneralAgent(llm=llm)
    
    # Test general queries
    test_queries = [
        "Hello, how are you?",
        "What can you help me with?",
        "What is a flight simulator?",
        "Tell me about CAE"
    ]
    
    print("Testing General Agent:")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)
        answer = agent.answer_query(query)
        print(f"Answer: {answer[:200]}...")
        print()

if __name__ == "__main__":
    test_general_agent()
