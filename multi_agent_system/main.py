"""
Interactive Multi-Agent System Demo with Visual Flow
Shows agent thinking, routing, and responses with ASCII animations
Updates: Aligned with graph.py tool calling and state structure
"""

import os
import sys
import time
from dotenv import load_dotenv
from graph import MultiAgentSystem

load_dotenv()

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    DIM = '\033[2m'
    MAGENTA = '\033[35m'

def print_banner():
    """Display startup banner"""
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🤖 Multi-Agent System - LangGraph + Morphik          ║
║                                                              ║
║  Planning → Specialists → Tools? → RedTeam? → Synthesis     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)

def animate_thinking(message, duration=0.5):
    """Show thinking animation"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    steps = int(duration * 10)
    for _ in range(steps):
        for frame in frames:
            sys.stdout.write(f"\r{Colors.CYAN}{frame}{Colors.END} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(message) + 10) + "\r")
    sys.stdout.flush()

def print_section(title, color=Colors.BLUE):
    """Print section header"""
    print(f"\n{color}{'─' * 80}{Colors.END}")
    print(f"{color}{Colors.BOLD}{title}{Colors.END}")
    print(f"{color}{'─' * 80}{Colors.END}")

def get_agent_icon(name):
    """Get icon for agent or tool"""
    icons = {
        "Planning Agent": "🎯",
        "Computer Specialist": "💻",
        "Interface Specialist": "🖥️",
        "Motion Specialist": "⚙️",
        "Vibration Specialist": "📊",
        "Visual Specialist": "👁️",
        "Red Team Agent": "🔐",
        "DR Agent": "📋",
        "Inventory Agent": "📦",
        "Mermaid Tool": "📐",
        "Synthesizer Agent": "🔮",
        # Lowercase mappings
        "computer": "💻",
        "interface": "🖥️",
        "motion": "⚙️",
        "vibration": "📊",
        "visual": "👁️",
        "redteam": "🔐",
        "search_deficiency_records": "📋",
        "search_inventory": "📦",
        "create_diagram": "📐"
    }
    return icons.get(name, "🤖")

def show_flow_arrow(text=""):
    """Show flow arrow"""
    print(f"\n{Colors.CYAN}{'─' * 35}▶{Colors.END} {text}")

def interactive_mode():
    """Run interactive query mode with visual flow"""
    morphik_uri = os.getenv("MORPHIK_URI", "http://localhost:8000")
    from dotenv import load_dotenv
    load_dotenv()

    print_banner()
    print(f"{Colors.DIM}Initializing agents and tools...{Colors.END}")
    
    try:
        
        system = MultiAgentSystem(morphik_uri, openrouter_api_key=os.getenv("OPENROUTER_API_KEY"))
        print(f"{Colors.GREEN}✓ System ready!{Colors.END}\n")
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to initialize: {e}{Colors.END}")
        return
    
    print(f"{Colors.DIM}Type your query below, or 'exit' to quit.{Colors.END}\n")
    
    while True:
        try:
            # Get user input
            query = input(f"{Colors.BOLD}{Colors.BLUE}🔍 Query:{Colors.END} ").strip()
            
            if query.lower() in ['exit', 'quit', 'q']:
                print(f"\n{Colors.CYAN}👋 Goodbye!{Colors.END}\n")
                break
            
            if not query:
                continue
            
            print() 
            
            # 1. VISUALIZE PROCESSING
            # Since graph.py runs entirely in one invoke call, we animate "Working" 
            # then display the trace of what happened.
            print_section("🚀 WORKFLOW EXECUTION", Colors.MAGENTA)
            animate_thinking("Planning and Consulting Specialists...", 1.5)
            animate_thinking("Checking for Tool Requirements...", 1.0)
            
            # 2. EXECUTE QUERY
            start_time = time.time()
            result = system.query(query)
            duration = time.time() - start_time
            
            # 3. DISPLAY TRACE
            
            # --- Planning Phase ---
            show_flow_arrow("Planning Complete")
            print(f"  {Colors.GREEN}✓{Colors.END} Routing Decision:")
            if result['agents_consulted']:
                for agent in result['agents_consulted']:
                    if agent != "redteam": # Handle redteam separately
                        print(f"    • {get_agent_icon(agent)} {agent.title()} Specialist")
            else:
                print(f"    • {Colors.DIM}No specific specialists required{Colors.END}")

            # --- Specialist Responses ---
            if result['agent_responses']:
                print_section("💬 SPECIALIST INSIGHTS", Colors.BLUE)
                for response in result['agent_responses']:
                    # Skip redteam here, show later
                    if response['agent'] == 'redteam':
                        continue
                        
                    agent_name = response['agent']
                    preview = response['answer'][:150].replace('\n', ' ') + "..."
                    print(f"  {get_agent_icon(agent_name)} {Colors.BOLD}{agent_name.title()}{Colors.END}")
                    print(f"     {Colors.DIM}{preview}{Colors.END}\n")

            # --- Tool Execution Phase ---
            # Derived from graph.py's execute_tools_node
            tools_used = result.get('tools_used', [])
            if tools_used:
                show_flow_arrow("Executing Tools")
                print_section("🛠️ TOOL OUTPUTS", Colors.YELLOW)
                
                # Check tool responses
                tool_responses = result.get('tool_responses', [])
                
                # Map generic tool names if needed
                tool_map = {
                    "search_deficiency_records": "DR Agent (Tool)",
                    "search_inventory": "Inventory Agent (Tool)",
                    "create_diagram": "Mermaid Tool"
                }

                # We iterate through the tools_used list (names of tools)
                # Note: In graph.py, the tool response object isn't strictly named by the tool, 
                # but usually strings. We'll display whatever is in tool_responses.
                for i, resp in enumerate(tool_responses):
                    # Try to match response to tool name if possible, otherwise generic
                    tool_name = "Tool Execution" 
                    if i < len(tools_used):
                        tool_name = tool_map.get(tools_used[i], tools_used[i])
                    
                    print(f"  {get_agent_icon(tools_used[i] if i < len(tools_used) else '')} {Colors.BOLD}{tool_name}{Colors.END}")
                    print(f"     {Colors.DIM}{str(resp)[:200]}...{Colors.END}\n")
            else:
                print(f"\n  {Colors.DIM}No external tools (DR, Inventory, Diagrams) were required.{Colors.END}")

            # --- Red Team Phase ---
            if result.get('redteam_reviewed'):
                show_flow_arrow("Security Review")
                print(f"\n  {Colors.RED}🔐 RED TEAM ACTIVATED{Colors.END}")
                # Find the redteam response
                rt_response = next((r for r in result['agent_responses'] if r['agent'] == 'redteam'), None)
                if rt_response:
                    print(f"     {Colors.RED}{rt_response['answer'][:200]}...{Colors.END}")

            # --- Synthesis Phase ---
            show_flow_arrow("Final Synthesis")
            print_section("✨ SYNTHESIZED RESPONSE", Colors.GREEN)
            print(f"\n{result['final_answer']}\n")
            
            # --- Metadata Footer ---
            print(f"{Colors.DIM}──────────────────────────────────────────────────────────────{Colors.END}")
            print(f"{Colors.DIM}Time: {duration:.2f}s | Specialists: {len(result['agents_consulted'])} | Tools: {len(tools_used)}{Colors.END}")
            if result.get('redteam_reviewed'):
                print(f"{Colors.YELLOW}Security Audit Logged{Colors.END}")
            print()
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⚠ Interrupted{Colors.END}")
            break
        except Exception as e:
            print(f"\n{Colors.RED}✗ Error: {e}{Colors.END}\n")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    interactive_mode()