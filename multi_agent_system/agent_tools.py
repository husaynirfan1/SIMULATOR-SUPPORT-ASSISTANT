"""
Tool definitions for multi-agent system
Converts DR, Inventory, and Mermaid to proper tool calls
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
from agents import DRAgent, InventoryAgent
from mermaid_tool import create_mermaid_response
import pandas as pd
import os

# Initialize agents for tools (will be set by MultiAgentSystem)
_dr_agent: Optional[DRAgent] = None
_inventory_agent: Optional[InventoryAgent] = None


def initialize_tool_agents(dr_agent: DRAgent, inventory_agent: InventoryAgent):
    """Initialize the agent instances for tools"""
    global _dr_agent, _inventory_agent
    _dr_agent = dr_agent
    _inventory_agent = inventory_agent

DR_CSV_PATH = os.path.join(os.path.dirname(__file__), "DR/DR_RECORDS.csv")

def search_dr_in_csv(query: str) -> Dict[str, Any]:
    """
    Helper function to search DR records in CSV using pandas.
    """
    try:
        if not os.path.exists(DR_CSV_PATH):
            return {
                "agent": "DR Agent",
                "error": f"DR records file not found at {DR_CSV_PATH}",
                "results": []
            }

        df = pd.read_csv(DR_CSV_PATH)
        
        # Check if query contains a DR number for exact match
        # Extract numbers from queries like "DR 56", "find 56", "deficiency 56"
        import re
        dr_numbers = re.findall(r'\b\d+\b', query)
        
        # Try exact DeficiencyNumber match first
        if dr_numbers and 'DeficiencyNumber' in df.columns:
            for dr_num in dr_numbers:
                exact_match = df[df['DeficiencyNumber'] == int(dr_num)]
                if not exact_match.empty:
                    # Found exact match, return it
                    results = []
                    for _, row in exact_match.iterrows():
                        results.append({
                            "DeficiencyNumber": row.get('DeficiencyNumber'),
                            "Issue Description": row.get('Issue Description'),
                            "ActionTaken": row.get('ActionTaken'),
                            "System": row.get('System'),
                            "Status": row.get('Status'),
                            "Resource": row.get('Resource')
                        })
                    
                    return {
                        "agent": "DR Agent",
                        "answer": f"Found exact match for DR#{dr_num}.",
                        "results": results
                    }
        
        # Normalize query for keyword search
        query_terms = query.lower().split()
        
        # Columns to search
        search_cols = ['Issue Description', 'ActionTaken', 'DeficiencyNumber', 'System', 'SubSystem', 'Resource']
        
        # Ensure columns exist
        existing_cols = [col for col in search_cols if col in df.columns]
        
        if not existing_cols:
             return {
                "agent": "DR Agent",
                "error": "Searchable columns not found in CSV",
                "results": []
            }

        # ✅ OPTIMIZATION: Use vectorized string operations instead of apply()
        # Combine all searchable columns into one text column
        df['combined_text'] = df[existing_cols].astype(str).agg(' '.join, axis=1).str.lower()
        
        # Calculate relevance score using vectorized operations
        df['relevance'] = 0
        for term in query_terms:
            df['relevance'] += df['combined_text'].str.contains(term, regex=False, na=False).astype(int)
        
        # Filter results with at least one match and limit to top 5 for speed
        results_df = df[df['relevance'] > 0].sort_values(by='relevance', ascending=False).head(5)
        
        # Clean up temporary columns
        df.drop(['combined_text', 'relevance'], axis=1, inplace=True)
        
        if results_df.empty:
             return {
                "agent": "DR Agent",
                "answer": f"No deficiency records found matching '{query}'.",
                "results": []
            }
            
        # Format results
        results = []
        for _, row in results_df.iterrows():
            results.append({
                "DeficiencyNumber": row.get('DeficiencyNumber'),
                "Issue Description": row.get('Issue Description'),
                "ActionTaken": row.get('ActionTaken'),
                "System": row.get('System'),
                "Status": row.get('Status'),
                "Resource": row.get('Resource')
            })
            
        return {
            "agent": "DR Agent",
            "answer": f"Found {len(results)} relevant deficiency records.",
            "results": results
        }

    except Exception as e:
        return {
            "agent": "DR Agent",
            "error": f"Error searching DR records: {str(e)}",
            "results": []
        }

@tool
def search_deficiency_records(query: str) -> Dict[str, Any]:
    """
    Search deficiency records (DRs) and quality issues in the knowledge base.
    
    Use this tool when the user asks about:
    - Known issues, bugs, or problems
    - Deficiency reports (DRs)
    - Quality assurance records
    - Past incidents or failures
    - Corrective actions or resolutions
    
    Args:
        query: The search query about deficiencies or issues
        
    Returns:
        Dict containing deficiency information and sources
    """
    # Prioritize CSV search
    return search_dr_in_csv(query)


@tool
def search_inventory(query: str) -> Dict[str, Any]:
    """
    Search inventory, parts, and component information.
    
    Use this tool when the user asks about:
    - Part numbers, specifications, or availability
    - Component inventory or stock levels
    - Spare parts or replacements
    - Supply chain or procurement information
    - Part compatibility or alternatives
    
    Args:
        query: The search query about inventory or parts
        
    Returns:
        Dict containing inventory information and sources
    """
    if _inventory_agent is None:
        return {
            "agent": "Inventory Agent",
            "answer": "Inventory Agent not initialized",
            "sources": []
        }
    
    return _inventory_agent.query_knowledge(query)


@tool
def create_diagram(query: str, context: str = "") -> Dict[str, Any]:
    """
    Create Mermaid diagrams for visualizing systems, flows, or architectures.
    
    Use this tool when the user explicitly asks to:
    - Create a diagram, flowchart, or visualization
    - Show a process flow or sequence
    - Visualize system architecture
    - Draw relationships or dependencies
    - Generate charts or graphs
    - Illustrate a concept or system
    - Map out a workflow or process
    - Make a visual representation
    
    Keywords that trigger this tool: diagram, flowchart, visualize, draw, chart, graph, 
    illustrate, map, sequence, architecture, flow, visual, mermaid
    
    Args:
        query: Description of what to visualize
        context: Additional context from other agents (optional)
        
    Returns:
        Dict containing Mermaid diagram code
    """
    return create_mermaid_response(query, context)


@tool
def fill_overtime_form(ot_data_json: str) -> Dict[str, Any]:
    """
    Fill overtime form with employee and OT entry data.
    
    This tool creates an Excel overtime form from structured data.
    Use this when users want to create, fill, or generate an overtime form.
    
    Args:
        ot_data_json: JSON string containing employee_info and ot_entries.
                     Format: {
                         "employee_info": {
                             "name": "Full Name",
                             "designation": "Job Title",
                             "department": "Department",
                             "grade": "E4",
                             "month": 11,
                             "year": 2025
                         },
                         "ot_entries": [{
                             "date": "2025-11-06",
                             "start_time": "21:00",
                             "end_time": "09:00",
                             "work_schedule": "Rest Day",  # Must be: Normal, Rest Day, or Public Holiday
                             "reason": "Reason for OT"
                         }]
                     }
    
    Returns:
        Dict with status, download_url, and message
    """
    import json
    import sys
    import os
    
    # Add ot_apps to path
    ot_apps_path = os.path.join(os.path.dirname(__file__), 'ot_apps')
    if ot_apps_path not in sys.path:
        sys.path.insert(0, ot_apps_path)
    
    try:
        from ot_apps.ot_form_models import OTFormRequest
        from ot_apps.script import fill_ot_form
        
        # Parse JSON
        data = json.loads(ot_data_json)
        
        # Validate with Pydantic
        form_request = OTFormRequest(**data)
        
        # Fill form
        result = fill_ot_form(form_request)
        
        if result["status"] == "success":
            return {
                "agent": "OT Form Tool",
                "answer": f"{result['message']}\n\nDownload your form here: {result['download_url']}\n\nEntries filled: {result['entries_count']}",
                "download_url": result["download_url"],
                "file_path": result["file_path"]
            }
        else:
            return {
                "agent": "OT Form Tool",
                "error": result["message"],
                "answer": f"Failed to create form: {result['message']}"
            }
            
    except json.JSONDecodeError as e:
        return {
            "agent": "OT Form Tool",
            "error": f"Invalid JSON format: {str(e)}",
            "answer": "Please provide data in valid JSON format."
        }
    except Exception as e:
        return {
            "agent": "OT Form Tool",
            "error": str(e),
            "answer": f"Error creating overtime form: {str(e)}"
        }


# Export all tools as a list
AVAILABLE_TOOLS = [
    search_deficiency_records,
    search_inventory,
    create_diagram,
    fill_overtime_form
]


# Tool descriptions for LLM to understand when to use each tool
TOOL_DESCRIPTIONS = """
Available Tools:

1. search_deficiency_records(query: str)
   - Use when: User asks about bugs, issues, DRs, problems, failures, incidents
   - Examples: "Are there any known issues with X?", "Check DRs for Y", "What problems have been reported?"
   
2. search_inventory(query: str)
   - Use when: User asks about parts, components, stock, availability, part numbers
   - Examples: "Do we have X in stock?", "What's the part number for Y?", "Find replacement for Z"
   
3. create_diagram(query: str, context: str)
   - Use when: User asks to visualize, create diagrams, show flowcharts, draw architecture
   - Examples: "Create a diagram of X", "Show me the flow of Y", "Visualize the architecture"

4. fill_overtime_form(ot_data_json: str)
   - Use when: User wants to create, fill, or generate an overtime form
   - Examples: "Fill my OT form", "Create overtime form for November", "Generate my overtime sheet"
   - NOTE: This tool requires structured data. Ask user for: name, designation, department, grade, month, year, and OT entries (date, times, schedule type, reason)
"""