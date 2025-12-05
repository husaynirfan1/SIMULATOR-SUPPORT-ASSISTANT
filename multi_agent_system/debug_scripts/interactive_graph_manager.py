#!/usr/bin/env python3
"""
Interactive Graph Manager - Diagnose and rebuild graphs one by one
"""

import requests
import sys
from morphik import AsyncMorphik
import time
import asyncio
import itertools
import threading

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class Spinner:
    """ASCII spinner for loading animations"""
    def __init__(self, message="Processing"):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.message = message
        self.running = False
        self.thread = None

    def spin(self):
        while self.running:
            sys.stdout.write(f'\r{self.message} {next(self.spinner)}')
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
        sys.stdout.flush()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()


class InteractiveGraphManager:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.client = None
        self.folders = []

    def check_connection(self):
        """Check if Morphik backend is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✓ Connected to Morphik backend{Colors.ENDC}")
                return True
        except requests.exceptions.ConnectionError:
            print(f"{Colors.RED}✗ Cannot connect to Morphik at {self.base_url}{Colors.ENDC}")
            print(f"{Colors.YELLOW}  Start it with: python all_start.py{Colors.ENDC}")
            return False

    async def initialize_client(self):
        """Initialize AsyncMorphik client"""
        try:
            self.client = AsyncMorphik()
            await self.client.__aenter__()
            print(f"{Colors.GREEN}✓ Morphik client initialized{Colors.ENDC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}✗ Failed to initialize client: {e}{Colors.ENDC}")
            return False

    def load_folders(self):
        """Load all available folders"""
        try:
            response = requests.get(f"{self.base_url}/folders", timeout=10)
            if response.status_code == 200:
                all_folders = response.json()
                self.folders = [f.get("name") for f in all_folders if f.get("name")]
                print(f"{Colors.GREEN}✓ Found {len(self.folders)} folders{Colors.ENDC}")
                return True
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Error loading folders: {e}{Colors.ENDC}")
            print(f"{Colors.YELLOW}  Using default folder list{Colors.ENDC}")
            self.folders = [
                "visual_kb",
                "interface_specialist",
                "motion_specialist",
                "vibration_specialist",
                "computer_specialist"
            ]
            return True

    async def diagnose_folder(self, folder_name):
        """Diagnose a single folder"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}📁 DIAGNOSING: {folder_name}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")

        try:
            response = requests.post(
                f"{self.base_url}/folders/details",
                json={
                    "identifiers": [folder_name],
                    "include_documents": True,
                    "include_document_count": True,
                    "document_limit": 100
                },
                timeout=10
            )

            if response.status_code != 200:
                print(f"{Colors.RED}✗ Error accessing folder{Colors.ENDC}")
                return None

            data = response.json()
            if not data.get("folders"):
                print(f"{Colors.RED}✗ Folder not found{Colors.ENDC}")
                return None

            docs = data["folders"][0]["document_info"]["documents"]

            # Analyze documents
            successful_docs = [
                d for d in docs
                if d.get("system_metadata", {}).get("status") == "completed"
                and len(d.get("chunk_ids", [])) > 0
            ]
            failed_docs = [d for d in docs if d.get("system_metadata", {}).get("status") == "failed"]
            processing_docs = [d for d in docs if d.get("system_metadata", {}).get("status") == "processing"]

            total_chunks = sum(len(d.get("chunk_ids", [])) for d in successful_docs)

            # Display stats
            print(f"📊 Document Statistics:")
            print(f"   Total documents: {len(docs)}")
            print(f"   {Colors.GREEN}✓ Successful: {len(successful_docs)}{Colors.ENDC} ({total_chunks} chunks)")

            if failed_docs:
                print(f"   {Colors.RED}✗ Failed: {len(failed_docs)}{Colors.ENDC}")
                for doc in failed_docs[:3]:
                    print(f"      - {doc.get('filename')}")
                if len(failed_docs) > 3:
                    print(f"      ... and {len(failed_docs)-3} more")

            if processing_docs:
                print(f"   {Colors.YELLOW}⏳ Processing: {len(processing_docs)}{Colors.ENDC}")

            # Check graph
            graph_name = f"{folder_name}_graph"
            graph_info = None

            try:
                graph = await self.client.get_graph(graph_name)
                entities = len(graph.entities)
                relationships = len(graph.relationships)
                status = graph.system_metadata.get('status', 'unknown')

                # Track which documents are already in the graph
                existing_doc_ids = set(graph.system_metadata.get('document_ids', []))
                docs_in_graph = len(existing_doc_ids)

                print(f"\n📊 Graph: {graph_name}")
                print(f"   Status: {status}")
                print(f"   Entities: {entities}")
                print(f"   Relationships: {relationships}")
                print(f"   Documents in graph: {docs_in_graph}")

                if entities < len(successful_docs) * 2 and status == "completed":
                    print(f"   {Colors.YELLOW}⚠ Graph seems small - may need rebuild{Colors.ENDC}")

                graph_info = {
                    "exists": True,
                    "entities": entities,
                    "relationships": relationships,
                    "status": status,
                    "docs_in_graph": docs_in_graph,
                    "existing_doc_ids": existing_doc_ids
                }
            except Exception:
                print(f"\n📊 No graph found")
                graph_info = {"exists": False, "docs_in_graph": 0, "existing_doc_ids": set()}

            return {
                "folder_name": folder_name,
                "total_docs": len(docs),
                "successful_docs": len(successful_docs),
                "successful_doc_ids": [d["external_id"] for d in successful_docs],
                "failed_docs": len(failed_docs),
                "processing_docs": len(processing_docs),
                "total_chunks": total_chunks,
                "graph": graph_info
            }

        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()
            return None

    async def rebuild_folder_graph(self, folder_info):
        """Rebuild graph for a folder"""
        folder_name = folder_info["folder_name"]
        graph_name = f"{folder_name}_graph"

        print(f"\n{Colors.BOLD}{Colors.GREEN}🔨 REBUILDING GRAPH: {graph_name}{Colors.ENDC}\n")

        if folder_info["successful_docs"] == 0:
            print(f"{Colors.YELLOW}⚠ No documents to process - skipping{Colors.ENDC}")
            return False

        try:
            graph_exists = folder_info["graph"]["exists"]
            doc_ids = folder_info["successful_doc_ids"]
            existing_doc_ids = folder_info["graph"].get("existing_doc_ids", set())

            # Track which docs are new vs already processed
            new_doc_ids = [doc_id for doc_id in doc_ids if doc_id not in existing_doc_ids]
            already_processed = [doc_id for doc_id in doc_ids if doc_id in existing_doc_ids]

            if already_processed:
                print(f"📋 Already in graph: {len(already_processed)} documents")
            if new_doc_ids:
                print(f"📋 New documents to add: {len(new_doc_ids)}")
                # Debug: Show first few doc IDs to check format
                print(f"📋 Sample new doc IDs: {new_doc_ids[:3]}")

            spinner = Spinner(f"🔨 {'Updating' if graph_exists else 'Creating'} graph")
            spinner.start()

            if graph_exists:
                # Check if we should add all docs or just new ones
                # If no new docs, skip update
                if len(new_doc_ids) == 0:
                    spinner.stop()
                    print(f"{Colors.YELLOW}⚠ No new documents to add - graph already up to date{Colors.ENDC}")
                    return True

                # Only add new documents, in batches if needed
                BATCH_SIZE = 50  # Morphik batch limit

                if len(new_doc_ids) > BATCH_SIZE:
                    print(f"⚠️  Large batch ({len(new_doc_ids)} docs), processing in batches of {BATCH_SIZE}...")

                    for i in range(0, len(new_doc_ids), BATCH_SIZE):
                        batch = new_doc_ids[i:i + BATCH_SIZE]
                        batch_num = (i // BATCH_SIZE) + 1
                        total_batches = (len(new_doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

                        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} docs)...")

                        graph = await self.client.update_graph(
                            name=graph_name,
                            additional_documents=batch
                        )
                else:
                    try:
                        graph = await self.client.update_graph(
                            name=graph_name,
                            additional_documents=new_doc_ids  # Use only NEW documents
                        )
                    except Exception as e:
                        spinner.stop()
                        print(f"\n{Colors.RED}✗ Failed to update graph{Colors.ENDC}")
                        print(f"   Graph: {graph_name}")
                        print(f"   Documents to add: {len(new_doc_ids)}")
                        print(f"   Document IDs: {new_doc_ids}")
                        print(f"   Error: {e}")

                        # Check if it's an httpx error with response body
                        if hasattr(e, 'response') and hasattr(e.response, 'text'):
                            print(f"   Response body: {e.response.text}")
                        raise
                action = "updated"
            else:
                graph = await self.client.create_graph(
                    name=graph_name,
                    folder_name=folder_name
                )
                action = "created"

            spinner.stop()

            status = graph.system_metadata.get('status', 'unknown')
            print(f"{Colors.GREEN}✓ Graph {action}!{Colors.ENDC}")
            print(f"  Status: {status}")
            print(f"  Initial entities: {len(graph.entities)}")

            if status == "processing":
                print(f"\n{Colors.YELLOW}⏳ Graph is building in background...{Colors.ENDC}")
                monitor = input(f"\nMonitor progress? (y/n): ").lower().strip()

                if monitor == 'y':
                    await self.monitor_graph(graph_name)

            return True

        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()
            return False

    async def monitor_graph(self, graph_name, max_wait=600):
        """Monitor graph building progress"""
        print(f"\n{Colors.CYAN}Monitoring {graph_name}...{Colors.ENDC}")
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                graph = await self.client.get_graph(graph_name)
                status = graph.system_metadata.get('status', 'unknown')
                entities = len(graph.entities)
                relationships = len(graph.relationships)

                elapsed = int(time.time() - start_time)
                print(f"  [{elapsed}s] Status: {status:12} | Entities: {entities:4} | Relationships: {relationships:4}", end='\r')

                if status == "completed":
                    print(f"\n\n{Colors.GREEN}✓ Graph completed!{Colors.ENDC}")
                    print(f"  Final: {entities} entities, {relationships} relationships")
                    break
                elif status == "failed":
                    print(f"\n\n{Colors.RED}✗ Graph failed!{Colors.ENDC}")
                    break

                await asyncio.sleep(5)
            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Monitoring stopped (graph continues in background){Colors.ENDC}")
                break
            except Exception as e:
                print(f"\n{Colors.RED}Error: {e}{Colors.ENDC}")
                break

    def show_menu(self):
        """Show main menu"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}INTERACTIVE GRAPH MANAGER{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}\n")

        print("1. Diagnose all folders")
        print("2. Diagnose single folder")
        print("3. Rebuild all graphs")
        print("4. Rebuild single graph")
        print("5. List all folders")
        print("6. Monitor a graph")
        print("0. Exit")

        return input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}").strip()

    async def diagnose_all(self):
        """Diagnose all folders"""
        print(f"\n{Colors.BOLD}Diagnosing all folders...{Colors.ENDC}\n")

        results = []
        for folder in self.folders:
            result = await self.diagnose_folder(folder)
            if result:
                results.append(result)
            await asyncio.sleep(1)

        # Summary
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}SUMMARY{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")

        for r in results:
            status_symbol = f"{Colors.GREEN}✓{Colors.ENDC}" if r["graph"]["exists"] else f"{Colors.YELLOW}⚠{Colors.ENDC}"
            docs_in_graph = r["graph"].get("docs_in_graph", 0)
            graph_status = f"Yes ({docs_in_graph} docs)" if r["graph"]["exists"] else "No"
            print(f"{status_symbol} {r['folder_name']:30} | Docs: {r['successful_docs']:3} | Chunks: {r['total_chunks']:4} | Graph: {graph_status}")

    async def rebuild_all(self):
        """Rebuild all graphs"""
        print(f"\n{Colors.BOLD}Rebuilding all graphs...{Colors.ENDC}\n")

        confirm = input(f"{Colors.YELLOW}This will rebuild ALL graphs. Continue? (y/n): {Colors.ENDC}").lower().strip()
        if confirm != 'y':
            print("Cancelled")
            return

        results = []
        for folder in self.folders:
            folder_info = await self.diagnose_folder(folder)
            if folder_info and folder_info["successful_docs"] > 0:
                success = await self.rebuild_folder_graph(folder_info)
                results.append((folder, success))
                await asyncio.sleep(2)

        print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
        for folder, success in results:
            symbol = f"{Colors.GREEN}✓{Colors.ENDC}" if success else f"{Colors.RED}✗{Colors.ENDC}"
            print(f"  {symbol} {folder}")

    async def run(self):
        """Main run loop"""
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}INTERACTIVE GRAPH MANAGER{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

        # Initialize
        if not self.check_connection():
            return
        if not await self.initialize_client():
            return
        if not self.load_folders():
            return

        try:
            # Main loop
            while True:
                choice = self.show_menu()

                if choice == '0':
                    print(f"\n{Colors.GREEN}Goodbye!{Colors.ENDC}\n")
                    break

                elif choice == '1':
                    await self.diagnose_all()

                elif choice == '2':
                    print(f"\n{Colors.BOLD}Available folders:{Colors.ENDC}")
                    for i, folder in enumerate(self.folders, 1):
                        print(f"  {i}. {folder}")
                    folder_idx = input(f"\nSelect folder number: ").strip()
                    try:
                        idx = int(folder_idx) - 1
                        if 0 <= idx < len(self.folders):
                            await self.diagnose_folder(self.folders[idx])
                        else:
                            print(f"{Colors.RED}Invalid selection{Colors.ENDC}")
                    except ValueError:
                        print(f"{Colors.RED}Invalid input{Colors.ENDC}")

                elif choice == '3':
                    await self.rebuild_all()

                elif choice == '4':
                    print(f"\n{Colors.BOLD}Available folders:{Colors.ENDC}")
                    for i, folder in enumerate(self.folders, 1):
                        print(f"  {i}. {folder}")
                    folder_idx = input(f"\nSelect folder number: ").strip()
                    try:
                        idx = int(folder_idx) - 1
                        if 0 <= idx < len(self.folders):
                            folder_info = await self.diagnose_folder(self.folders[idx])
                            if folder_info:
                                confirm = input(f"\n{Colors.YELLOW}Rebuild this graph? (y/n): {Colors.ENDC}").lower().strip()
                                if confirm == 'y':
                                    await self.rebuild_folder_graph(folder_info)
                        else:
                            print(f"{Colors.RED}Invalid selection{Colors.ENDC}")
                    except ValueError:
                        print(f"{Colors.RED}Invalid input{Colors.ENDC}")

                elif choice == '5':
                    print(f"\n{Colors.BOLD}Available folders:{Colors.ENDC}")
                    for i, folder in enumerate(self.folders, 1):
                        print(f"  {i}. {folder}")

                elif choice == '6':
                    print(f"\n{Colors.BOLD}Available folders:{Colors.ENDC}")
                    for i, folder in enumerate(self.folders, 1):
                        print(f"  {i}. {folder}")
                    folder_idx = input(f"\nSelect folder number: ").strip()
                    try:
                        idx = int(folder_idx) - 1
                        if 0 <= idx < len(self.folders):
                            graph_name = f"{self.folders[idx]}_graph"
                            await self.monitor_graph(graph_name)
                        else:
                            print(f"{Colors.RED}Invalid selection{Colors.ENDC}")
                    except ValueError:
                        print(f"{Colors.RED}Invalid input{Colors.ENDC}")

                else:
                    print(f"{Colors.RED}Invalid option{Colors.ENDC}")

                input(f"\n{Colors.BOLD}Press Enter to continue...{Colors.ENDC}")

        finally:
            # Clean up AsyncMorphik client
            if self.client:
                await self.client.__aexit__(None, None, None)


if __name__ == "__main__":
    manager = InteractiveGraphManager()
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.ENDC}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
