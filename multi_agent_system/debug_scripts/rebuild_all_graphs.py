#!/usr/bin/env python3
"""
Rebuild/update graphs for ALL folders
"""

from morphik import AsyncMorphik
import requests
import time
import sys
import asyncio
import itertools
import threading

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


async def rebuild_folder_graph(client, folder_name, base_url="http://localhost:8000"):
    """Rebuild graph for a single folder"""

    graph_name = f"{folder_name}_graph"

    print("\n" + "=" * 70)
    print(f"📁 FOLDER: {folder_name}")
    print(f"📊 GRAPH: {graph_name}")
    print("=" * 70)

    # Get folder info
    try:
        response = requests.post(
            f"{base_url}/folders/details",
            json={
                "identifiers": [folder_name],
                "include_documents": True,
                "include_document_count": True,
                "document_limit": 100
            },
            timeout=10
        )

        if response.status_code != 200:
            print(f"❌ Error: Cannot access folder")
            return False

        data = response.json()
        if not data.get("folders"):
            print(f"❌ Folder not found!")
            return False

        docs = data["folders"][0]["document_info"]["documents"]

        # Filter successful documents
        successful_docs = [
            d for d in docs
            if d.get("system_metadata", {}).get("status") == "completed"
            and len(d.get("chunk_ids", [])) > 0
        ]

        if len(successful_docs) == 0:
            print(f"⚠️  No successfully ingested documents - skipping!")
            return False

        total_chunks = sum(len(d.get("chunk_ids", [])) for d in successful_docs)

        print(f"\n✅ Documents with chunks: {len(successful_docs)}")
        print(f"📊 Total chunks: {total_chunks}")

    except Exception as e:
        print(f"❌ Error checking folder: {e}")
        return False

    # Check if graph exists and track which docs are already processed
    graph_exists = False
    existing_doc_ids = set()
    try:
        existing_graph = await client.get_graph(graph_name)
        graph_exists = True

        # Extract document IDs that are already in the graph
        existing_doc_ids = set(existing_graph.system_metadata.get('document_ids', []))

        print(f"\n📊 Existing graph found:")
        print(f"   Entities: {len(existing_graph.entities)}")
        print(f"   Relationships: {len(existing_graph.relationships)}")
        print(f"   Documents already processed: {len(existing_doc_ids)}")
    except Exception:
        print(f"\n📊 No existing graph - will create new one")

    # Get all successful document IDs
    successful_doc_ids = [d["external_id"] for d in successful_docs]

    # Track which docs are new vs already processed
    new_doc_ids = [doc_id for doc_id in successful_doc_ids if doc_id not in existing_doc_ids]
    already_processed = [doc_id for doc_id in successful_doc_ids if doc_id in existing_doc_ids]

    if already_processed:
        print(f"\n📋 Already in graph: {len(already_processed)} documents")
    if new_doc_ids:
        print(f"📋 New documents to add: {len(new_doc_ids)}")

    # Update or create graph
    try:
        spinner = Spinner(f"🔨 {'Updating' if graph_exists else 'Creating'} graph")
        spinner.start()

        if graph_exists:
            updated_graph = await client.update_graph(
                name=graph_name,
                additional_documents=successful_doc_ids
            )
            action = "updated"
        else:
            updated_graph = await client.create_graph(
                name=graph_name,
                folder_name=folder_name
            )
            action = "created"

        spinner.stop()

        status = updated_graph.system_metadata.get('status', 'unknown')
        print(f"✅ Graph {action}!")
        print(f"   Status: {status}")
        print(f"   Initial entities: {len(updated_graph.entities)}")

        if status == "processing":
            print(f"\n⏳ Building graph in background...")
            print(f"   (This folder will continue processing)")
            return True
        elif status == "completed":
            print(f"✅ Graph ready immediately!")
            return True
        else:
            return True

    except Exception as e:
        print(f"\n❌ Error during graph {action if graph_exists else 'creation'}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def monitor_all_graphs(client, folder_names, max_wait_seconds=600):
    """Monitor all graphs until completion"""

    print("\n" + "=" * 70)
    print("MONITORING ALL GRAPHS")
    print("=" * 70)

    graph_names = [f"{fn}_graph" for fn in folder_names]
    start_time = time.time()
    check_interval = 15  # seconds

    completed = set()
    failed = set()

    while time.time() - start_time < max_wait_seconds:
        all_done = True

        print(f"\n⏱  [{int(time.time() - start_time)}s] Checking status...")

        for graph_name in graph_names:
            if graph_name in completed or graph_name in failed:
                continue

            try:
                graph = await client.get_graph(graph_name)
                status = graph.system_metadata.get('status', 'unknown')
                entities = len(graph.entities)
                relationships = len(graph.relationships)

                if status == "completed":
                    completed.add(graph_name)
                    print(f"   ✅ {graph_name:30} - DONE ({entities} entities, {relationships} rels)")
                elif status == "failed":
                    failed.add(graph_name)
                    print(f"   ❌ {graph_name:30} - FAILED")
                elif status == "processing":
                    all_done = False
                    print(f"   ⏳ {graph_name:30} - Processing ({entities} entities so far)")
                else:
                    print(f"   ⚠️  {graph_name:30} - Status: {status}")
            except Exception as e:
                # Graph might not exist yet
                print(f"   ⚠️  {graph_name:30} - Not found")
                all_done = False

        if all_done:
            print(f"\n🎉 All graphs completed!")
            break

        await asyncio.sleep(check_interval)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(f"\n✅ Completed: {len(completed)}")
    for name in sorted(completed):
        try:
            graph = await client.get_graph(name)
            print(f"   • {name}: {len(graph.entities)} entities, {len(graph.relationships)} relationships")
        except:
            pass

    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for name in sorted(failed):
            print(f"   • {name}")

    still_processing = set(graph_names) - completed - failed
    if still_processing:
        print(f"\n⏳ Still processing: {len(still_processing)}")
        for name in sorted(still_processing):
            print(f"   • {name}")


async def main():
    """Rebuild graphs for all folders"""

    print("=" * 70)
    print("REBUILD ALL GRAPHS")
    print("=" * 70)

    base_url = "http://localhost:8000"

    # Check backend
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Morphik backend not healthy!")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Morphik at {base_url}")
        print(f"   Start it with: python all_start.py")
        sys.exit(1)

    # Get all folders
    try:
        folders_response = requests.get(f"{base_url}/folders", timeout=10)
        if folders_response.status_code == 200:
            all_folders = folders_response.json()
            folder_names = [f.get("name") for f in all_folders if f.get("name")]
            print(f"\n✅ Found {len(folder_names)} folders\n")
        else:
            print(f"⚠️  Using default folder list...")
            folder_names = [
                "visual_kb",
                "interface_specialist",
                "motion_specialist",
                "vibration_specialist",
                "computer_specialist"
            ]
    except Exception as e:
        print(f"⚠️  Error: {e}")
        folder_names = [
            "visual_kb",
            "interface_specialist",
            "motion_specialist",
            "vibration_specialist",
            "computer_specialist"
        ]

    # Initialize AsyncMorphik client
    async with AsyncMorphik() as client:
        # Rebuild each folder's graph
        print("\n🔨 Starting graph rebuild for all folders...\n")

        successful_rebuilds = []
        skipped = []

        for folder_name in folder_names:
            success = await rebuild_folder_graph(client, folder_name, base_url)
            if success:
                successful_rebuilds.append(folder_name)
            else:
                skipped.append(folder_name)
            await asyncio.sleep(2)  # Brief pause between folders

        # Summary
        print("\n" + "=" * 70)
        print("REBUILD SUMMARY")
        print("=" * 70)

        print(f"\n✅ Graphs triggered: {len(successful_rebuilds)}")
        for fn in successful_rebuilds:
            print(f"   • {fn}")

        if skipped:
            print(f"\n⚠️  Skipped: {len(skipped)}")
            for fn in skipped:
                print(f"   • {fn}")

        # Monitor progress
        if successful_rebuilds:
            print(f"\n⏳ All graphs are now building in background...")
            print(f"   Monitoring progress (this may take 5-15 minutes)...\n")

            await monitor_all_graphs(client, successful_rebuilds, max_wait_seconds=900)  # 15 min max

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
