"""
Setup script to create Morphik folders for each agent
Run this once to initialize the knowledge base structure
"""

import os
from morphik import Morphik
from dotenv import load_dotenv

load_dotenv()


def setup_folders():
    """Create Morphik folders for each specialist agent"""
    
    # Initialize Morphik client
    client = Morphik(timeout=10000, is_local=True)
    
    # Define all agent folders
    folders = [
        {"name": "planning_kb", "description": "Planning and orchestration knowledge"},
        {"name": "interface_kb", "description": "User interface and HMI knowledge"},
        {"name": "motion_kb", "description": "Motion systems and actuator knowledge"},
        {"name": "vibration_kb", "description": "Vibration analysis knowledge"},
        {"name": "visual_kb", "description": "Visual systems and graphics knowledge"},
        {"name": "computer_kb", "description": "Computing hardware and software knowledge"},
        {"name": "redteam_kb", "description": "Security and vulnerability knowledge"},
        {"name": "dr_kb", "description": "Deficiency and issue tracking knowledge"},
        {"name": "inventory_kb", "description": "Parts and inventory management knowledge"},
        {"name": "mermaid_kb", "description": "Mermaid diagram examples and visualization knowledge"},
        {"name": "synthesis_kb", "description": "Synthesis and integration knowledge"}
    ]
    
    print("Creating Morphik folders for multi-agent system...")
    
    for folder_info in folders:
        try:
            # Create folder
            # Using create_folder directly on client as per user pattern
            folder = client.create_folder(
                name=folder_info["name"],
                description=folder_info["description"]
            )
            print(f"✓ Created folder: {folder_info['name']}")
        except Exception as e:
            # Folder might already exist
            print(f"⚠ Folder {folder_info['name']}: {str(e)}")
    
    print("\n✓ Folder setup complete!")
    print("\nNext steps:")
    print("1. Add documents to each folder using the add_documents.py script")
    print("2. Run main.py to test the multi-agent system")


if __name__ == "__main__":
    setup_folders()
