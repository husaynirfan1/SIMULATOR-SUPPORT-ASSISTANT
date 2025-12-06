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
import signal

# Configuration
PROJECT_ROOT = Path(__file__).parent.absolute()
CONDA_ENV = "sse-ai"
LOG_DIR = PROJECT_ROOT / "logs"

# Service configurations
SERVICES = {
    "morphik": {
        "name": "Morphik Backend",
        "cwd": PROJECT_ROOT / "morphik-core",
        "command": ["bash", "./install_and_start.sh"],
        "log_file": "morphik_backend.log",
        "health_check": "http://localhost:8000/health",
        "startup_delay": 8,
        "use_shell": True,
        "use_conda": False,  # install_and_start.sh handles its own environment
    },
    "auth": {
        "name": "Auth Server",
        "cwd": PROJECT_ROOT / "auth",
        "command": ["uvicorn", "auth_server:app", "--host", "0.0.0.0", "--port", "3221"],
        "log_file": "auth_server.log",
        "health_check": "http://localhost:3221/health",
        "startup_delay": 3,
        "use_shell": True,
        "use_conda": True,
    },
    "multi_agent": {
        "name": "Multi-Agent Server",
        "cwd": PROJECT_ROOT / "multi_agent_system",
        "command": ["python", "server.py"],
        "log_file": "multi_agent_server.log",
        "health_check": "http://localhost:8082/health",
        "startup_delay": 10,
        "use_shell": True,
        "use_conda": True,
    },
    "frontend": {
        "name": "Frontend Server",
        "cwd": PROJECT_ROOT,
        "command": ["python", "-m", "http.server", "3000"],
        "log_file": "frontend_server.log",
        "health_check": "http://localhost:3000",
        "startup_delay": 2,
        "use_shell": True,
        "use_conda": True,
    },
    "morphik_static_ui": {
        "name": "Morphik Static UI",
        "cwd": PROJECT_ROOT / "morphik-static-ui",
        "command": ["python", "-m", "http.server", "8080"],
        "log_file": "morphik_static_ui.log",
        "health_check": "http://localhost:8080",
        "startup_delay": 2,
        "use_shell": True,
        "use_conda": True,
    },
}

# Tailscale funnel configuration
# Note: Tailscale funnel exposes local services on HTTPS
# We'll expose port 3000 (frontend) directly on HTTPS 443
TAILSCALE_CONFIG = {
    "enabled": True,
    "primary_service": {
        "name": "Frontend UI",
        "local_port": 3000,
        "https_port": 443
    },
    "additional_services": [
        {
            "name": "Auth Server",
            "local_port": 3221,
            "https_port": 3221
        },
        {
            "name": "Multi-Agent WebSocket",
            "local_port": 8082,
            "https_port": 8082
        }
    ]
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

def kill_port_processes(port):
    """Kill any process using the specified port"""
    try:
        # Use lsof to find processes using the port
        result = subprocess.run(
            ["sudo", "lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"  {Colors.YELLOW}⚠ Killing process {pid} on port {port}{Colors.ENDC}")
                    subprocess.run(["sudo", "kill", "-9", pid], check=False)

            # Wait a bit for processes to die
            time.sleep(1)

            # Verify port is free
            verify = subprocess.run(
                ["sudo", "lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True
            )
            if verify.returncode == 0 and verify.stdout.strip():
                print(f"  {Colors.RED}✗ Port {port} still occupied after kill{Colors.ENDC}")
                return False

            return True
        return False
    except Exception as e:
        print(f"  {Colors.YELLOW}⚠ Error checking port {port}: {e}{Colors.ENDC}")
        return False

def reset_tailscale_funnel():
    """Reset Tailscale funnel and verify it's clean"""
    print(f"{Colors.BOLD}Resetting Tailscale Funnel...{Colors.ENDC}\n")

    try:
        # Reset funnel
        print(f"  {Colors.CYAN}Running: sudo tailscale funnel reset{Colors.ENDC}")
        result = subprocess.run(
            ["sudo", "tailscale", "funnel", "reset"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            print(f"  {Colors.GREEN}✓ Tailscale funnel reset successful{Colors.ENDC}")
        else:
            print(f"  {Colors.YELLOW}⚠ Funnel reset returned code {result.returncode}{Colors.ENDC}")

        time.sleep(1)

        # Verify status
        print(f"\n  {Colors.CYAN}Verifying: sudo tailscale funnel status{Colors.ENDC}")
        status_result = subprocess.run(
            ["sudo", "tailscale", "funnel", "status"],
            capture_output=True,
            text=True,
            check=False
        )

        output = status_result.stdout + status_result.stderr

        if "no serve config" in output.lower() or "not running" in output.lower() or not output.strip():
            print(f"  {Colors.GREEN}✓ Confirmed: No serve config (funnel is clean){Colors.ENDC}\n")
            return True
        else:
            print(f"  {Colors.YELLOW}⚠ Funnel status output:{Colors.ENDC}")
            print(f"    {output[:200]}")
            return False

    except Exception as e:
        print(f"  {Colors.RED}✗ Error resetting Tailscale funnel: {e}{Colors.ENDC}\n")
        return False

def cleanup_ports():
    """Clean up all ports used by services"""
    print(f"{Colors.BOLD}Cleaning up ports...{Colors.ENDC}\n")

    # Clean up ports with retries
    ports = [8000, 3221, 8082, 3000, 8080]
    max_retries = 3

    for port in ports:
        freed = False
        for attempt in range(max_retries):
            killed = kill_port_processes(port)
            if killed:
                print(f"  {Colors.GREEN}✓ Port {port} cleaned{Colors.ENDC}")
                freed = True
                break
            elif attempt < max_retries - 1:
                # Port still occupied, retry
                print(f"  {Colors.YELLOW}⚠ Retrying port {port} cleanup (attempt {attempt + 2}/{max_retries}){Colors.ENDC}")
                time.sleep(1)

        if not freed:
            # Check if port is actually free (no processes found)
            check = subprocess.run(
                ["sudo", "lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True
            )
            if check.returncode != 0 or not check.stdout.strip():
                print(f"  {Colors.GREEN}✓ Port {port} is free{Colors.ENDC}")

    print()

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
    use_shell = config.get("use_shell", False)
    use_conda = config.get("use_conda", False)

    # Create service log directory
    service_log_dir = LOG_DIR / service_id
    service_log_dir.mkdir(exist_ok=True)

    # Generate timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = service_log_dir / f"{timestamp}_{log_file}"

    # If using conda, wrap command with conda activation
    if use_conda:
        # Get conda base path
        conda_exe = os.environ.get("CONDA_EXE", "conda")
        conda_base = Path(conda_exe).parent.parent if conda_exe != "conda" else Path.home() / "anaconda3"

        # Build conda activation command
        cmd_str = " ".join(command)
        full_command = f"source {conda_base}/etc/profile.d/conda.sh && conda activate {CONDA_ENV} && cd {cwd} && {cmd_str}"

        print(f"{Colors.BLUE}▶{Colors.ENDC}  Starting {Colors.BOLD}{service_name}{Colors.ENDC}...")
        print(f"   Working dir: {cwd}")
        print(f"   Conda env: {CONDA_ENV}")
        print(f"   Command: {cmd_str}")
        print(f"   Log file: {log_path}")
    else:
        # Replace 'python' in command with actual Python executable
        if command[0] == "python" and not use_shell:
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
        if use_conda:
            log_file_handle.write(f"Conda Environment: {CONDA_ENV}\n")
            log_file_handle.write(f"Command: {full_command}\n")
        else:
            log_file_handle.write(f"Command: {' '.join(command)}\n")
        log_file_handle.write(f"Working Directory: {cwd}\n")
        log_file_handle.write("="*50 + "\n\n")
        log_file_handle.flush()

        # Start process
        if use_conda or use_shell:
            # Use bash to execute with conda activation or shell script
            if use_conda:
                cmd_to_run = full_command
            else:
                cmd_to_run = " ".join(command)

            process = subprocess.Popen(
                ["bash", "-c", cmd_to_run],
                cwd=cwd if not use_conda else None,  # cd is in command for conda
                stdout=log_file_handle,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                bufsize=1,
            )
        else:
            # For non-conda Python commands, use list format
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

def setup_tailscale_funnel():
    """Setup Tailscale funnel to expose services"""
    if not TAILSCALE_CONFIG.get("enabled", False):
        print(f"{Colors.YELLOW}Tailscale funnel disabled in configuration{Colors.ENDC}")
        return None

    print(f"{Colors.BOLD}Setting up Tailscale Funnel...{Colors.ENDC}\n")

    funnel_processes = []

    try:
        # Setup primary service (Frontend on HTTPS 443)
        primary = TAILSCALE_CONFIG["primary_service"]
        print(f"{Colors.BLUE}▶{Colors.ENDC}  Exposing {primary['name']} (localhost:{primary['local_port']}) on HTTPS {primary['https_port']}...")

        # Create log file for primary funnel
        primary_log_path = LOG_DIR / f"tailscale_funnel_{primary['https_port']}.log"
        primary_log = open(primary_log_path, "w", buffering=1)

        # Start funnel for primary service
        primary_process = subprocess.Popen(
            ["sudo", "tailscale", "funnel", f"--bg", f"--https={primary['https_port']}", f"http://localhost:{primary['local_port']}"],
            stdout=primary_log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL
        )

        time.sleep(1)

        if primary_process.poll() is None or primary_process.returncode == 0:
            print(f"  {Colors.GREEN}✓{Colors.ENDC} {primary['name']} funnel started")
            funnel_processes.append({
                "name": primary['name'],
                "process": primary_process if primary_process.poll() is None else None,
                "log_file": primary_log,
                "log_path": primary_log_path,
                "port": primary['https_port']
            })
        else:
            print(f"  {Colors.RED}✗{Colors.ENDC} Failed to start primary funnel")
            primary_log.close()

        # Setup additional services
        for service in TAILSCALE_CONFIG.get("additional_services", []):
            print(f"\n{Colors.BLUE}▶{Colors.ENDC}  Exposing {service['name']} (localhost:{service['local_port']}) on HTTPS {service['https_port']}...")

            svc_log_path = LOG_DIR / f"tailscale_funnel_{service['https_port']}.log"
            svc_log = open(svc_log_path, "w", buffering=1)

            svc_process = subprocess.Popen(
                ["sudo", "tailscale", "funnel", f"--bg", f"--https={service['https_port']}", f"http://localhost:{service['local_port']}"],
                stdout=svc_log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL
            )

            time.sleep(1)

            if svc_process.poll() is None or svc_process.returncode == 0:
                print(f"  {Colors.GREEN}✓{Colors.ENDC} {service['name']} funnel started")
                funnel_processes.append({
                    "name": service['name'],
                    "process": svc_process if svc_process.poll() is None else None,
                    "log_file": svc_log,
                    "log_path": svc_log_path,
                    "port": service['https_port']
                })
            else:
                print(f"  {Colors.YELLOW}⚠{Colors.ENDC} {service['name']} funnel may be running in background")
                svc_log.close()

        if funnel_processes:
            return funnel_processes
        else:
            return None

    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.ENDC} Error: {str(e)}")
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

    # Reset Tailscale funnel first
    reset_tailscale_funnel()

    # Clean up ports before starting
    cleanup_ports()

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

    # Setup Tailscale funnels
    print()
    funnel_processes = setup_tailscale_funnel()

    # Verify funnel status
    if funnel_processes:
        print(f"\n{Colors.BOLD}Verifying Tailscale Funnel status...{Colors.ENDC}\n")
        try:
            status_result = subprocess.run(
                ["sudo", "tailscale", "funnel", "status"],
                capture_output=True,
                text=True,
                check=False
            )
            print(status_result.stdout)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Could not check funnel status: {e}{Colors.ENDC}")

    # Summary
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}")
    print(f"  All services started!")
    print(f"{'='*70}{Colors.ENDC}\n")

    print(f"{Colors.BOLD}Service URLs:{Colors.ENDC}")
    print(f"  • Morphik Backend:     http://localhost:8000")
    print(f"  • Morphik API Docs:    http://localhost:8000/docs")
    print(f"  • Auth Server:         http://localhost:3221")
    print(f"  • Multi-Agent Server:  http://localhost:8082")
    print(f"  • Login Page:          http://localhost:3000/auth/login.html")
    print(f"  • Chatbot UI:          http://localhost:3000/frontend/chatbotui/index.html")
    print(f"  • Morphik Static UI:   http://localhost:8080")

    if funnel_processes:
        print(f"\n{Colors.BOLD}Tailscale Funnel (Public HTTPS Access):{Colors.ENDC}")
        for funnel in funnel_processes:
            print(f"  • {funnel['name']:30} → HTTPS port {funnel['port']}")

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

            # Check if any service has died
            for service_id, service_info in list(running_services.items()):
                process = service_info["process"]
                if process.poll() is not None:
                    print(f"\n{Colors.RED}✗{Colors.ENDC} {service_info['name']} exited with code {process.returncode}")
                    service_info["log_file"].close()
                    del running_services[service_id]

            # Check if any funnel has died
            if funnel_processes:
                for funnel in list(funnel_processes):
                    if funnel["process"] and funnel["process"].poll() is not None:
                        print(f"\n{Colors.RED}✗{Colors.ENDC} Tailscale funnel ({funnel['name']}) exited with code {funnel['process'].returncode}")
                        if funnel["log_file"]:
                            funnel["log_file"].close()
                        funnel_processes.remove(funnel)

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

        # Stop Tailscale funnel processes
        if funnel_processes:
            print(f"\n  Stopping Tailscale funnels...")
            for funnel in funnel_processes:
                print(f"    Stopping {funnel['name']}...")
                if funnel["process"]:
                    try:
                        funnel["process"].terminate()
                        funnel["process"].wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        funnel["process"].kill()
                if funnel["log_file"]:
                    funnel["log_file"].close()

        # Reset Tailscale funnel configuration
        print(f"\n  Resetting Tailscale funnel configuration...")
        try:
            subprocess.run(["sudo", "tailscale", "funnel", "reset"], check=False, capture_output=True)
            print(f"  {Colors.GREEN}✓{Colors.ENDC} Tailscale funnel reset")
        except Exception as e:
            print(f"  {Colors.YELLOW}⚠{Colors.ENDC} Could not reset funnel: {e}")

        print(f"\n{Colors.GREEN}✓ All services stopped{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.ENDC}\n")
        sys.exit(1)
