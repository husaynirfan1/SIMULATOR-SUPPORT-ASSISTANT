import asyncio
import os
from dotenv import load_dotenv
from morphik import Morphik
from morphik.client import QueryPromptOverrides, QueryPromptOverride

load_dotenv()

async def test_graph_query():
    print("Testing graph query...")
    
    # Initialize Morphik client
    client = Morphik(timeout=10000, is_local=True)
    
    graph_name = "interface_kb_graph"
    query = "What are the interface requirements?"
    
    try:
        print(f"Querying graph: {graph_name}")
        response = client.query_graph(
            query=query,
            graph_name=graph_name,
            hop_depth=2
        )
        print("✓ Query successful!")
        print(f"Answer: {response.completion[:100]}...")
    except Exception as e:
        print(f"✗ Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_graph_query())
