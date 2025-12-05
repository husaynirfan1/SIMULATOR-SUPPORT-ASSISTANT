#!/usr/bin/env python3
"""
Rebuild/update knowledge graph to include all successfully ingested documents
"""

from morphik import Morphik
import time

def rebuild_graph(folder_name="visual_kb", graph_name="visual_kb_graph"):
    """
    Update existing graph or create new one with all successfully ingested documents

    Args:
        folder_name: Name of the folder to create graph from
        graph_name: Name of the graph to update/create
    """

    print("=" * 70)
    print(f"REBUILDING GRAPH: {graph_name}")
    print("=" * 70)

    client = Morphik(is_local=True, timeout=30000)

    # Check if graph exists
    graph_exists = False
    try:
        existing_graph = client.get_graph(graph_name)
        graph_exists = True
        print(f"\n✅ Found existing graph: {graph_name}")
        print(f"   Current entities: {len(existing_graph.entities)}")
        print(f"   Current relationships: {len(existing_graph.relationships)}")
    except Exception as e:
        print(f"\n⚠️  No existing graph found: {e}")
        print(f"   Will create new graph instead")

    # Get all documents in folder to see what we're working with
    print(f"\n📁 Checking documents in folder: {folder_name}")
    try:
        folder = client.get_folder(folder_name)

        # This will show us document status via the API
        import requests
        response = requests.post(
            "http://localhost:8000/folders/details",
            json={
                "identifiers": [folder_name],
                "include_documents": True,
                "include_document_count": True,
                "document_limit": 100
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            docs = data["folders"][0]["document_info"]["documents"]

            successful_docs = [d for d in docs if d.get("system_metadata", {}).get("status") == "completed" and len(d.get("chunk_ids", [])) > 0]
            failed_docs = [d for d in docs if d.get("system_metadata", {}).get("status") == "failed"]

            print(f"   Total documents: {len(docs)}")
            print(f"   ✅ Successful: {len(successful_docs)}")
            print(f"   ❌ Failed: {len(failed_docs)}")

            total_chunks = sum(len(d.get("chunk_ids", [])) for d in successful_docs)
            print(f"   📊 Total chunks: {total_chunks}")

            if len(successful_docs) == 0:
                print(f"\n❌ ERROR: No successfully ingested documents found!")
                print(f"   Cannot create/update graph with 0 documents.")
                return

            if len(failed_docs) > 0:
                print(f"\n⚠️  WARNING: {len(failed_docs)} documents failed ingestion:")
                for doc in failed_docs[:5]:
                    print(f"      - {doc.get('filename')}")
                print(f"   These will NOT be included in the graph.")
                print(f"   Check worker logs for details: morphik-core/logs/worker.log")
    except Exception as e:
        print(f"⚠️  Could not check document status: {e}")
        print(f"   Proceeding anyway...")

    # Update or create graph
    print(f"\n🔨 {'Updating' if graph_exists else 'Creating'} graph...")

    try:
        if graph_exists:
            # Update existing graph with ALL documents from folder
            # This will re-process everything and rebuild entities/relationships
            print(f"   Using update_graph() to rebuild from scratch...")

            # Get all successful document IDs
            successful_doc_ids = [d["external_id"] for d in successful_docs]

            print(f"   Processing {len(successful_doc_ids)} documents...")

            # Update graph with all documents
            # This will extract entities from ALL documents, not just new ones
            # Batch if needed to avoid 400 errors
            BATCH_SIZE = 50

            if len(successful_doc_ids) > BATCH_SIZE:
                print(f"   ⚠️  Large batch ({len(successful_doc_ids)} docs), processing in batches of {BATCH_SIZE}...")

                for i in range(0, len(successful_doc_ids), BATCH_SIZE):
                    batch = successful_doc_ids[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    total_batches = (len(successful_doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

                    print(f"      Batch {batch_num}/{total_batches} ({len(batch)} docs)...")

                    updated_graph = client.update_graph(
                        name=graph_name,
                        additional_documents=batch
                    )
            else:
                updated_graph = client.update_graph(
                    name=graph_name,
                    additional_documents=successful_doc_ids  # Re-process all documents
                )

            print(f"\n✅ Graph updated successfully!")

        else:
            # Create new graph
            print(f"   Using create_graph() for first-time creation...")
            updated_graph = client.create_graph(
                name=graph_name,
                folder_name=folder_name
            )

            print(f"\n✅ Graph created successfully!")

        # Show initial status
        status = updated_graph.system_metadata.get('status', 'unknown')
        print(f"   Status: {status}")
        print(f"   Entities: {len(updated_graph.entities)}")
        print(f"   Relationships: {len(updated_graph.relationships)}")

        if status == "processing":
            print(f"\n⏳ Graph is being built in background...")
            print(f"   This may take a few minutes depending on document size.")
            print(f"   Monitoring progress...\n")

            # Monitor progress
            for i in range(60):  # Wait up to 10 minutes
                time.sleep(10)

                current_graph = client.get_graph(graph_name)
                current_status = current_graph.system_metadata.get('status')
                entities = len(current_graph.entities)
                relationships = len(current_graph.relationships)

                print(f"   [{i*10}s] Status: {current_status:12} | Entities: {entities:4} | Relationships: {relationships:4}")

                if current_status == "completed":
                    print(f"\n🎉 Graph building complete!")
                    print(f"\n📊 Final Statistics:")
                    print(f"   Entities: {entities}")
                    print(f"   Relationships: {relationships}")
                    print(f"\n✅ Graph '{graph_name}' is ready to use!")

                    # Show sample entities
                    if entities > 0:
                        print(f"\n📋 Sample entities:")
                        for entity in list(current_graph.entities)[:10]:
                            print(f"   - {entity.label} ({entity.type})")

                    break
                elif current_status == "failed":
                    print(f"\n❌ Graph building FAILED!")
                    print(f"   Check morphik logs: morphik-core/logs/morphik.log")
                    break
            else:
                print(f"\n⏰ Still processing after 10 minutes...")
                print(f"   Graph will continue building in background.")
                print(f"   Check status with: client.get_graph('{graph_name}')")

        elif status == "completed":
            print(f"\n✅ Graph is ready immediately!")

            # Show sample entities
            entities = len(updated_graph.entities)
            if entities > 0:
                print(f"\n📋 Sample entities:")
                for entity in list(updated_graph.entities)[:10]:
                    print(f"   - {entity.label} ({entity.type})")

    except Exception as e:
        print(f"\n❌ ERROR during graph {'update' if graph_exists else 'creation'}: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)

    # Usage instructions
    print(f"\n💡 To use the graph in queries:")
    print(f"""
from morphik import Morphik

client = Morphik(is_local=True)
folder = client.get_folder("{folder_name}")

response = folder.query(
    query="Your question here",
    k=10,
    graph_name="{graph_name}",
    hop_depth=2
)

print(response.completion)
""")

if __name__ == "__main__":
    # You can customize these
    FOLDER_NAME = "visual_kb"
    GRAPH_NAME = "visual_kb_graph"

    rebuild_graph(FOLDER_NAME, GRAPH_NAME)
