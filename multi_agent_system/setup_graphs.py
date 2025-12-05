"""
Setup Knowledge Graphs for Each Agent Folder
Creates or gets a knowledge graph for each agent's folder
"""

import os
from dotenv import load_dotenv
from morphik import Morphik

load_dotenv()

# Agent folders
AGENT_FOLDERS = [
    "planning_kb",
    "interface_kb",
    "motion_kb",
    "vibration_kb",
    "visual_kb",
    "computer_kb",
    "redteam_kb",
    "dr_kb",
    "inventory_kb",
    "synthesis_kb",
]

def setup_graphs():
    """Create or get knowledge graphs for each agent folder"""
    
    # Initialize Morphik client
    client = Morphik(timeout=10000, is_local=True)
    
    print("Setting up knowledge graphs for agent folders...\n")
    
    for folder_name in AGENT_FOLDERS:
        graph_name = f"{folder_name}_graph"
        
        try:
            # Try to get existing graph
            try:
                graph = client.get_graph(graph_name)
                print(f"✓ Found existing graph: {graph_name}")
                print(f"  Entities: {len(graph.entities)}, Relationships: {len(graph.relationships)}\n")
            except:
                # Create new graph for this folder
                print(f"Creating graph: {graph_name}...")
                
                # Get folder to check if it has documents
                folder = client.get_folder(folder_name)
                response = folder.list_documents()
                
                if response.returned_count == 0:
                    print(f"  ⚠ Skipping {graph_name} - no documents in folder\n")
                    continue
                
                # Create graph using all documents in the folder
                graph = client.create_graph(
                    name=graph_name,
                    folder_name=folder_name
                )
                
                print(f"  Graph created (processing in background)")
                print(f"  Graph status: {graph.system_metadata.get('status', 'unknown')}")
                print(f"  Documents: {response.returned_count}\n")
                
        except Exception as e:
            print(f"✗ Error with {graph_name}: {e}\n")
    
    print("Graph setup complete!")
    print("\nNote: Graphs are processed asynchronously in the background.")
    print("Use `client.wait_for_graph_completion(graph_name)` to wait for completion.")

if __name__ == "__main__":
    setup_graphs()
