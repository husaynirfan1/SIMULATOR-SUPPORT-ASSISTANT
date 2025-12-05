"""
Interactive Document Upload System for Multi-Agent Knowledge Bases
Upload documents to agent-specific Morphik folders with visual feedback
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from morphik import Morphik

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

# Agent folder configuration
AGENTS = {
    "1": {"name": "Planning Agent", "folder": "planning_kb", "icon": "🎯"},
    "2": {"name": "Interface Specialist", "folder": "interface_kb", "icon": "🖥️"},
    "3": {"name": "Motion Specialist", "folder": "motion_kb", "icon": "⚙️"},
    "4": {"name": "Vibration Specialist", "folder": "vibration_kb", "icon": "📊"},
    "5": {"name": "Visual Specialist", "folder": "visual_kb", "icon": "👁️"},
    "6": {"name": "Computer Specialist", "folder": "computer_kb", "icon": "💻"},
    "7": {"name": "Red Team Agent", "folder": "redteam_kb", "icon": "🔐"},
    "8": {"name": "DR Agent", "folder": "dr_kb", "icon": "📋"},
    "9": {"name": "Inventory Agent", "folder": "inventory_kb", "icon": "📦"},
    "10": {"name": "Synthesizer Agent", "folder": "synthesis_kb", "icon": "🔮"},
}

def animate_progress(message, duration=1.0):
    """Show animated progress bar"""
    bar_length = 40
    for i in range(bar_length + 1):
        percent = (i / bar_length) * 100
        filled = '█' * i
        empty = '░' * (bar_length - i)
        sys.stdout.write(f"\r{Colors.CYAN}{message}: [{filled}{empty}] {percent:.0f}%{Colors.END}")
        sys.stdout.flush()
        time.sleep(duration / bar_length)
    print()  # Newline after completion

def animate_spinner(message, duration=0.5):
    """Show thinking spinner"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(int(duration * 10)):
        for frame in frames:
            sys.stdout.write(f"\r{Colors.CYAN}{frame}{Colors.END} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

def print_banner():
    """Display startup banner"""
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        📚 Agent Knowledge Base - Document Upload             ║
║                                                              ║
║        Upload documents to agent-specific folders            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)

def print_menu():
    """Display agent selection menu"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'═' * 60}{Colors.END}")
    print(f"{Colors.BOLD}  Select Agent Knowledge Base:{Colors.END}")
    print(f"{Colors.BLUE}{'═' * 60}{Colors.END}\n")
    
    # Print in two columns
    agents_list = list(AGENTS.items())
    mid = (len(agents_list) + 1) // 2
    
    for i in range(mid):
        left_id, left_agent = agents_list[i]
        line = f"  {Colors.YELLOW}{left_id}.{Colors.END} {left_agent['icon']}  {left_agent['name']:<25}"
        
        if i + mid < len(agents_list):
            right_id, right_agent = agents_list[i + mid]
            line += f"  {Colors.YELLOW}{right_id}.{Colors.END} {right_agent['icon']}  {right_agent['name']}"
        
        print(line)
    
    print(f"\n  {Colors.YELLOW}A.{Colors.END} 📁  Upload to ALL agents")
    print(f"  {Colors.YELLOW}L.{Colors.END} 📊  List documents in folder")
    print(f"  {Colors.YELLOW}Q.{Colors.END} 🚪  Quit\n")
    print(f"{Colors.BLUE}{'═' * 60}{Colors.END}")

def show_upload_options():
    """Display upload method options"""
    print(f"\n{Colors.BOLD}Upload Method:{Colors.END}")
    print(f"  {Colors.CYAN}1.{Colors.END} 📄 Upload text content")
    print(f"  {Colors.CYAN}2.{Colors.END} 📁 Upload file")
    print(f"  {Colors.CYAN}3.{Colors.END} ⬅️  Back to agent selection")

def upload_text(client, folder_name, agent_name):
    """Upload text content to agent folder"""
    print(f"\n{Colors.BOLD}Enter your document content:{Colors.END}")
    print(f"{Colors.DIM}(Enter 'END' on a new line when finished){Colors.END}\n")
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠ Cancelled{Colors.END}")
            return
    
    content = "\n".join(lines)
    
    if not content.strip():
        print(f"{Colors.RED}✗ No content provided{Colors.END}")
        return
    
    # Get metadata
    title = input(f"\n{Colors.BOLD}Document title:{Colors.END} ").strip() or "Untitled Document"
    
    try:
        animate_spinner(f"Uploading to {agent_name}", 1.0)
        
        # Get folder and use folder.ingest_text()
        folder = client.get_folder(folder_name)
        doc = folder.ingest_text(
            text=content,
            metadata={"title": title, "source": "manual_upload"}
        )
        
        animate_progress("Processing document", 1.5)
        print(f"{Colors.GREEN}✓ Successfully uploaded '{title}' to {agent_name}!{Colors.END}")
        print(f"{Colors.DIM}Document ID: {doc.external_id}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}✗ Upload failed: {e}{Colors.END}")

def upload_file(client, folder_name, agent_name):
    """Upload file to agent folder"""
    file_path = input(f"\n{Colors.BOLD}Enter file path:{Colors.END} ").strip()
    
    if not file_path:
        print(f"{Colors.RED}✗ No file path provided{Colors.END}")
        return
    
    path = Path(file_path)
    if not path.exists():
        print(f"{Colors.RED}✗ File not found: {file_path}{Colors.END}")
        return
    
    if not path.is_file():
        print(f"{Colors.RED}✗ Path is not a file: {file_path}{Colors.END}")
        return
    
    try:
        animate_spinner(f"Reading {path.name}", 0.5)
        
        # Get folder and use folder.ingest_file() with file and metadata only
        folder = client.get_folder(folder_name)
        doc = folder.ingest_file(
            file=str(path),
            metadata={"source": "file_upload"}
        )
        
        animate_progress(f"Uploading {path.name}", 2.0)
        print(f"{Colors.GREEN}✓ Successfully uploaded '{path.name}' to {agent_name}!{Colors.END}")
        print(f"{Colors.DIM}Document ID: {doc.external_id}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}✗ Upload failed: {e}{Colors.END}")

def list_documents(client, folder_name, agent_name):
    """List all documents in agent folder"""
    try:
        animate_spinner(f"Fetching documents from {agent_name}", 0.5)
        
        # Get folder and use folder.list_documents()
        folder = client.get_folder(folder_name)
        response = folder.list_documents()  # Returns ListDocsResponse
        
        # Access documents from response
        docs = response.documents
        
        if not docs:
            print(f"\n{Colors.YELLOW}📭 No documents in {agent_name} folder{Colors.END}")
            return
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}📚 Documents in {agent_name}:{Colors.END}")
        print(f"{Colors.DIM}{'─' * 60}{Colors.END}")
        
        for i, doc in enumerate(docs, 1):
            # Document object from SDK
            title = getattr(doc, 'filename', 'Untitled')
            doc_id = getattr(doc, 'external_id', 'N/A')
            size = getattr(doc, 'size', 0)
            
            print(f"{Colors.CYAN}{i}.{Colors.END} {title}")
            print(f"   {Colors.DIM}ID: {str(doc_id)[:8]}... | Size: {size} bytes{Colors.END}")
        
        print(f"{Colors.DIM}{'─' * 60}{Colors.END}")
        print(f"{Colors.BOLD}Total: {response.returned_count} document(s){Colors.END}\n")
        
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to list documents: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

def handle_agent_upload(client, agent_id):
    """Handle upload for specific agent"""
    agent = AGENTS[agent_id]
    
    while True:
        print(f"\n{Colors.BOLD}{agent['icon']}  {agent['name']}{Colors.END}")
        show_upload_options()
        
        choice = input(f"\n{Colors.BOLD}Select option:{Colors.END} ").strip()
        
        if choice == "1":
            upload_text(client, agent['folder'], agent['name'])
        elif choice == "2":
            upload_file(client, agent['folder'], agent['name'])
        elif choice == "3":
            break
        else:
            print(f"{Colors.RED}✗ Invalid option{Colors.END}")

def upload_to_all(client):
    """Upload same content to all agents"""
    print(f"\n{Colors.YELLOW}⚠️  This will upload to ALL agent knowledge bases{Colors.END}")
    confirm = input(f"Continue? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print(f"{Colors.DIM}Cancelled{Colors.END}")
        return
    
    choice = input(f"\n{Colors.BOLD}Upload (1) Text or (2) File?{Colors.END} ").strip()
    
    if choice == "1":
        # Get content once
        print(f"\n{Colors.BOLD}Enter your document content:{Colors.END}")
        print(f"{Colors.DIM}(Enter 'END' on a new line when finished){Colors.END}\n")
        
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}⚠ Cancelled{Colors.END}")
                return
        
        content = "\n".join(lines)
        title = input(f"\n{Colors.BOLD}Document title:{Colors.END} ").strip() or "Shared Document"
        
        # Upload to all
        print(f"\n{Colors.CYAN}Uploading to all agents...{Colors.END}")
        success_count = 0
        
        for agent_id, agent in AGENTS.items():
            try:
                sys.stdout.write(f"\r{Colors.CYAN}⚙{Colors.END}  {agent['name']:<30}")
                sys.stdout.flush()
                
                folder = client.get_folder(agent['folder'])
                folder.ingest_text(
                    text=content,
                    metadata={"title": title, "source": "bulk_upload"}
                )
                
                success_count += 1
                time.sleep(0.2)
                
            except Exception as e:
                print(f"\n{Colors.RED}✗ Failed for {agent['name']}: {e}{Colors.END}")
        
        print(f"\n{Colors.GREEN}✓ Uploaded to {success_count}/{len(AGENTS)} agents!{Colors.END}")
        
    elif choice == "2":
        file_path = input(f"\n{Colors.BOLD}Enter file path:{Colors.END} ").strip()
        path = Path(file_path)
        
        if not path.exists() or not path.is_file():
            print(f"{Colors.RED}✗ Invalid file{Colors.END}")
            return
        
        print(f"\n{Colors.CYAN}Uploading {path.name} to all agents...{Colors.END}")
        success_count = 0
        
        for agent_id, agent in AGENTS.items():
            try:
                sys.stdout.write(f"\r{Colors.CYAN}⚙{Colors.END}  {agent['name']:<30}")
                sys.stdout.flush()
                
                folder = client.get_folder(agent['folder'])
                folder.ingest_file(
                    file=str(path),
                    metadata={"source": "bulk_upload"}
                )
                
                success_count += 1
                time.sleep(0.2)
                
            except Exception as e:
                print(f"\n{Colors.RED}✗ Failed for {agent['name']}: {e}{Colors.END}")
        
        print(f"\n{Colors.GREEN}✓ Uploaded to {success_count}/{len(AGENTS)} agents!{Colors.END}")

def main():
    """Main interactive loop"""
    print_banner()
    
    # Initialize Morphik
    print(f"{Colors.DIM}Initializing connection to Morphik...{Colors.END}")
    animate_spinner("Connecting", 0.5)
    
    try:
        client = Morphik(timeout=10000, is_local=True)
        print(f"{Colors.GREEN}✓ Connected to Morphik!{Colors.END}\n")
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to connect: {e}{Colors.END}")
        return
    
    while True:
        try:
            print_menu()
            choice = input(f"{Colors.BOLD}Enter choice:{Colors.END} ").strip().upper()
            
            if choice == 'Q':
                print(f"\n{Colors.CYAN}👋 Goodbye!{Colors.END}\n")
                break
            
            elif choice == 'A':
                upload_to_all(client)
            
            elif choice == 'L':
                # List documents menu
                print_menu()
                agent_id = input(f"\n{Colors.BOLD}Select agent (1-10):{Colors.END} ").strip()
                if agent_id in AGENTS:
                    agent = AGENTS[agent_id]
                    list_documents(client, agent['folder'], agent['name'])
                else:
                    print(f"{Colors.RED}✗ Invalid agent{Colors.END}")
            
            elif choice in AGENTS:
                handle_agent_upload(client, choice)
            
            else:
                print(f"{Colors.RED}✗ Invalid choice{Colors.END}")
        
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⚠ Interrupted{Colors.END}")
            break
        except Exception as e:
            print(f"\n{Colors.RED}✗ Error: {e}{Colors.END}")

if __name__ == "__main__":
    main()
