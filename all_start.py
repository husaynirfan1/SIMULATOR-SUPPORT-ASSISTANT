#!/usr/bin/env python3
"""
Unified startup script for SSE-AI-v2 system
Starts Morphik backend, Multi-agent server, and Frontend in parallel
Uses conda environment: sse-ai
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_ROOT = Path(__file__).parent.absolute()
CONDA_ENV = "sse-ai"
LOG_DIR = PROJECT_ROOT / "logs"

# Service configurations
SERVICES = {
    "morphik": {
        "name": "Morphik Backend",
        "cwd": PROJECT_ROOT / "morphik-core",
        "command": ["python", "-m", "uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        "log_file": "morphik_backend.log",
        "health_check": "http://localhost:8000/health",
        "startup_delay": 3,
    },
    "multi_agent": {
        "name": "Multi-Agent Server",
        "cwd": PROJECT_ROOT / "multi_agent_system",
        "command": ["python", "server.py"],
        "log_file": "multi_agent_server.log",
        "health_check": "http://localhost:8082/health",
        "startup_delay": 5,
    },
    
    "frontend": {
        "name": "Frontend Server",
        "cwd": PROJECT_ROOT / "frontend/chatbotui",
        "command": ["python", "-m", "http.server", "3000"],
        "log_file": "frontend_server.log",
        "health_check": "http://localhost:3000",
        "startup_delay": 2,
    },
    "morphik_static_ui": {
        "name": "Morphik Static UI",
        "cwd": PROJECT_ROOT / "morphik-static-ui",
        "command": ["python", "-m", "http.server", "3223"],
        "log_file": "morphik_static_ui.log",
        "health_check": "http://localhost:3223",
        "startup_delay": 2,
    },
    "tailscale_funnel": {
        "name": "Tailscale Funnel (Frontend)",
        "cwd": PROJECT_ROOT / "frontend/chatbotui",
        "command": ["sudo", "tailscale", "funnel", "--bg", "--https=3000", "http://localhost:3000"],
        "log_file": "tailscale_funnel.log",
        "health_check": None,  # No health check for tunnel service
        "startup_delay": 3,
    },
    "tailscale_funnel_ws": {
        "name": "Tailscale Funnel (WebSocket)",
        "cwd": PROJECT_ROOT / "multi_agent_system",
        "command": ["sudo", "tailscale", "funnel", "--bg", "--https=8082", "http://localhost:8082"],
        "log_file": "tailscale_funnel_ws.log",
        "health_check": None,  # No health check for tunnel service
        "startup_delay": 3,
    },
}

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Print startup banner"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print(f"  SSE-AI-v2 System Startup")
    print(f"  Conda Environment: {CONDA_ENV}")
    print(f"  Log Directory: {LOG_DIR}")
    print(f"{'='*70}{Colors.ENDC}\n")

def get_conda_python():
    """Get the Python executable from the conda environment"""

    # Try to find conda
    conda_exe = os.environ.get("CONDA_EXE", "conda")

    try:
        # Get conda environment info
        result = subprocess.run(
            [conda_exe, "env", "list"],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse environment list to find sse-ai
        for line in result.stdout.split('\n'):
            if CONDA_ENV in line and not line.startswith('#'):
                parts = line.split()
                for part in parts:
                    if os.path.isdir(part):
                        env_path = Path(part)
                        python_path = env_path / "bin" / "python"
                        if python_path.exists():
                            return str(python_path)

        print(f"{Colors.YELLOW}⚠️  Could not find conda environment '{CONDA_ENV}'{Colors.ENDC}")
        print(f"{Colors.YELLOW}   Using system Python instead{Colors.ENDC}")
        return sys.executable

    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{Colors.YELLOW}⚠️  Conda not found, using system Python{Colors.ENDC}")
        return sys.executable

def setup_logging():
    """Create log directories"""
    LOG_DIR.mkdir(exist_ok=True)

    # Create service-specific log directories
    for service_id in SERVICES:
        service_log_dir = LOG_DIR / service_id
        service_log_dir.mkdir(exist_ok=True)

    print(f"{Colors.GREEN}✓{Colors.ENDC} Log directories created")

def start_service(service_id, config, python_exe):
    """Start a single service"""
    service_name = config["name"]
    cwd = config["cwd"]
    command = config["command"]
    log_file = config["log_file"]

    # Create service log directory
    service_log_dir = LOG_DIR / service_id
    service_log_dir.mkdir(exist_ok=True)

    # Generate timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = service_log_dir / f"{timestamp}_{log_file}"

    # Replace 'python' in command with actual Python executable
    if command[0] == "python":
        command[0] = python_exe

    print(f"{Colors.BLUE}▶{Colors.ENDC}  Starting {Colors.BOLD}{service_name}{Colors.ENDC}...")
    print(f"   Working dir: {cwd}")
    print(f"   Command: {' '.join(command)}")
    print(f"   Log file: {log_path}")

    try:
        # Check if working directory exists
        if not cwd.exists():
            print(f"{Colors.RED}✗{Colors.ENDC}  Working directory does not exist: {cwd}")
            return None

        # Open log file
        log_file_handle = open(log_path, "w", buffering=1)

        # Write header to log
        log_file_handle.write(f"=== {service_name} Log ===\n")
        log_file_handle.write(f"Started at: {datetime.now().isoformat()}\n")
        log_file_handle.write(f"Command: {' '.join(command)}\n")
        log_file_handle.write(f"Working Directory: {cwd}\n")
        log_file_handle.write("="*50 + "\n\n")
        log_file_handle.flush()

        # Start process
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=log_file_handle,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            bufsize=1,
            universal_newlines=True
        )

        print(f"{Colors.GREEN}✓{Colors.ENDC}  {service_name} started (PID: {process.pid})")

        return {
            "process": process,
            "log_file": log_file_handle,
            "log_path": log_path,
            "name": service_name
        }

    except Exception as e:
        print(f"{Colors.RED}✗{Colors.ENDC}  Failed to start {service_name}: {str(e)}")
        return None


def check_health(url, timeout=2):
    """Check if a service is healthy"""
    try:
        import urllib.request
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except:
        return False


def main():
    """Main startup function"""
    print_header()

    # Setup logging
    setup_logging()

    # Get Python executable from conda environment
    print(f"\n{Colors.BOLD}Resolving Python executable...{Colors.ENDC}")
    python_exe = get_conda_python()
    print(f"{Colors.GREEN}✓{Colors.ENDC} Using Python: {python_exe}\n")

    # Start all services
    print(f"{Colors.BOLD}Starting services...{Colors.ENDC}\n")
    running_services = {}

    for service_id, config in SERVICES.items():
        service_info = start_service(service_id, config, python_exe)

        if service_info:
            running_services[service_id] = service_info

            # Wait for startup delay
            startup_delay = config.get("startup_delay", 2)
            print(f"   Waiting {startup_delay}s for startup...\n")
            time.sleep(startup_delay)
        else:
            print(f"{Colors.RED}✗{Colors.ENDC}  Skipping {config['name']} due to startup failure\n")

    # Health checks
    if running_services:
        print(f"\n{Colors.BOLD}Health checks...{Colors.ENDC}\n")

        for service_id, config in SERVICES.items():
            if service_id in running_services:
                health_url = config.get("health_check")
                if health_url:
                    is_healthy = check_health(health_url)
                    status = f"{Colors.GREEN}✓ HEALTHY{Colors.ENDC}" if is_healthy else f"{Colors.YELLOW}⚠ STARTING{Colors.ENDC}"
                    print(f"  {config['name']:25} {status:20} {health_url}")

    # Summary
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}")
    print(f"  All services started!")
    print(f"{'='*70}{Colors.ENDC}\n")

    print(f"{Colors.BOLD}Service URLs:{Colors.ENDC}")
    print(f"  • Morphik Backend:     http://localhost:8000")
    print(f"  • Morphik API Docs:    http://localhost:8000/docs")
    print(f"  • Multi-Agent Server:  http://localhost:8082")
    print(f"  • Frontend UI:         http://localhost:3000")
    print(f"  • Morphik Static UI:   http://localhost:3223")
    print(f"  • Tailscale Funnel:    Exposing ports 3000 (Frontend) & 8082 (WebSocket) publicly")

    print(f"\n{Colors.BOLD}Logs:{Colors.ENDC}")
    for service_id, service_info in running_services.items():
        print(f"  • {service_info['name']:25} {service_info['log_path']}")

    print(f"\n{Colors.BOLD}To stop all services:{Colors.ENDC}")
    print(f"  Press {Colors.BOLD}Ctrl+C{Colors.ENDC} or run: {Colors.CYAN}python all_stop.py{Colors.ENDC}")

    print(f"\n{Colors.YELLOW}Monitoring services... (Press Ctrl+C to stop all){Colors.ENDC}\n")

    # Monitor services
    try:
        while True:
            time.sleep(5)

            # Check if any process has died
            for service_id, service_info in list(running_services.items()):
                process = service_info["process"]
                if process.poll() is not None:
                    print(f"\n{Colors.RED}✗{Colors.ENDC} {service_info['name']} exited with code {process.returncode}")
                    service_info["log_file"].close()
                    del running_services[service_id]

            if not running_services:
                print(f"\n{Colors.RED}All services have stopped{Colors.ENDC}")
                break

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Shutting down services...{Colors.ENDC}\n")

        # Stop all services
        for service_id, service_info in running_services.items():
            print(f"  Stopping {service_info['name']}...")
            try:
                service_info["process"].terminate()
                service_info["process"].wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"  Force killing {service_info['name']}...")
                service_info["process"].kill()

            service_info["log_file"].close()

        print(f"\n{Colors.GREEN}✓ All services stopped{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.ENDC}\n")
        sys.exit(1)
