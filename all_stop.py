#!/usr/bin/env python3
"""
Stop all SSE-AI-v2 services
"""

import subprocess
import sys
import signal
import time

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def find_processes():
    """Find all related processes"""
    processes_to_kill = []

    # Search patterns for each service
    patterns = [
        ("Morphik Backend", "uvicorn core.main:app"),
        ("Multi-Agent Server", "python server.py"),
        ("Frontend Server", "python -m http.server 3000"),
    ]

    try:
        # Get all processes
        ps_output = subprocess.check_output(["ps", "aux"], text=True)

        for name, pattern in patterns:
            for line in ps_output.split('\n'):
                if pattern in line and "grep" not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        processes_to_kill.append((name, pid))

    except subprocess.CalledProcessError:
        pass

    return processes_to_kill


def kill_process(name, pid):
    """Kill a process by PID"""
    try:
        print(f"  Stopping {name} (PID: {pid})...")
        subprocess.run(["kill", "-TERM", pid], check=True)
        time.sleep(1)

        # Check if still running
        try:
            subprocess.run(["kill", "-0", pid], check=True, stderr=subprocess.DEVNULL)
            # Still running, force kill
            print(f"  Force killing {name} (PID: {pid})...")
            subprocess.run(["kill", "-KILL", pid], check=True)
        except subprocess.CalledProcessError:
            # Process is dead
            pass

        print(f"{Colors.GREEN}✓{Colors.ENDC} Stopped {name}")
        return True

    except subprocess.CalledProcessError:
        print(f"{Colors.YELLOW}⚠{Colors.ENDC} Process {name} (PID: {pid}) not found")
        return False


def main():
    """Main function"""
    print(f"\n{Colors.BOLD}Stopping SSE-AI-v2 services...{Colors.ENDC}\n")

    processes = find_processes()

    if not processes:
        print(f"{Colors.YELLOW}No running services found{Colors.ENDC}\n")
        return

    print(f"Found {len(processes)} running service(s)\n")

    for name, pid in processes:
        kill_process(name, pid)

    print(f"\n{Colors.GREEN}✓ All services stopped{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted{Colors.ENDC}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {str(e)}{Colors.ENDC}\n")
        sys.exit(1)
