#!/usr/bin/env python3
"""
Diagnose why graph creation shows "Retrieved 0 chunks"
"""

import requests
import json

def diagnose():
    print("=" * 70)
    print("GRAPH ISSUE DIAGNOSIS")
    print("=" * 70)

    # Check visual_specialist folder via API
    folder_name = "visual_kb"
    base_url = "http://localhost:8000"

    print(f"\n📁 Checking folder: {folder_name}\n")

    try:
        # Get folder details with documents
        response = requests.post(
            f"{base_url}/folders/details",
            json={
                "identifiers": [folder_name],
                "include_documents": True,
                "include_document_count": True,
                "document_limit": 50
            },
            timeout=10
        )

        if response.status_code != 200:
            print(f"❌ Error: API returned {response.status_code}")
            print(f"   Response: {response.text}")
            return

        data = response.json()

        if not data.get("folders"):
            print(f"❌ Folder '{folder_name}' not found!")
            return

        folder_info = data["folders"][0]
        doc_info = folder_info.get("document_info", {})
        docs = doc_info.get("documents", [])
        total_count = doc_info.get("document_count", len(docs))

        print(f"Total documents in folder: {total_count}")
        print(f"Retrieved: {len(docs)}\n")

        # Analyze each document
        docs_with_chunks = 0
        docs_without_chunks = 0
        total_chunks = 0
        problematic_docs = []

        for idx, doc in enumerate(docs, 1):
            status = doc.get("system_metadata", {}).get("status", "unknown")
            chunk_ids = doc.get("chunk_ids", [])
            num_chunks = len(chunk_ids) if chunk_ids else 0

            if num_chunks > 0:
                docs_with_chunks += 1
                total_chunks += num_chunks
                symbol = "✅"
            else:
                docs_without_chunks += 1
                symbol = "❌"
                problematic_docs.append(doc)

            print(f"{symbol} {idx}. {doc.get('filename', 'Unknown')}")
            print(f"     Status: {status}")
            print(f"     External ID: {doc.get('external_id', 'N/A')}")
            print(f"     Chunks: {num_chunks}")

            # If no chunks but status is completed, this is a problem
            if num_chunks == 0 and status == "completed":
                print(f"     ⚠️  WARNING: Document marked 'completed' but has NO chunks!")
                print(f"     This will cause graph creation to find 0 chunks!")
            elif num_chunks == 0 and status == "processing":
                print(f"     ℹ️  Still processing - wait for completion")

            print()

        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Documents WITH chunks: {docs_with_chunks}")
        print(f"Documents WITHOUT chunks: {docs_without_chunks}")
        print(f"Total chunks across all docs: {total_chunks}")

        if docs_without_chunks > 0:
            print(f"\n⚠️  ISSUE FOUND:")
            print(f"   {docs_without_chunks} documents have NO chunks!")
            print(f"   This is why graph creation shows 'Retrieved 0 chunks'")
            print(f"\n💡 POSSIBLE CAUSES:")
            print(f"   1. Documents still processing (status != 'completed')")
            print(f"   2. Ingestion failed silently")
            print(f"   3. chunk_ids not saved to database after ingestion")
            print(f"\n🔧 SOLUTIONS:")
            print(f"   1. Wait for documents to finish processing")
            print(f"   2. Re-ingest failed documents")
            print(f"   3. Check worker logs: morphik-core/logs/worker.log")

            # Show problematic documents
            print(f"\n📋 Documents without chunks:")
            for doc in problematic_docs[:5]:
                print(f"   - {doc.get('filename')} (status: {doc.get('system_metadata', {}).get('status')})")
        else:
            print(f"\n✅ All documents have chunks!")
            print(f"   Graph creation should work properly.")

        print("\n" + "=" * 70)

        # Check if graphs exist
        print("\n📊 Checking existing graphs...\n")

        try:
            graph_response = requests.get(f"{base_url}/graph", timeout=10)
            if graph_response.status_code == 200:
                graphs = graph_response.json()

                # Filter for visual_specialist graphs
                visual_graphs = [g for g in graphs if folder_name in g.get("name", "").lower() or
                                g.get("folder_name") == folder_name]

                if visual_graphs:
                    for graph in visual_graphs:
                        print(f"Graph: {graph.get('name')}")
                        print(f"  Status: {graph.get('system_metadata', {}).get('status')}")
                        print(f"  Entities: {len(graph.get('entities', []))}")
                        print(f"  Relationships: {len(graph.get('relationships', []))}")

                        if len(graph.get('entities', [])) == 0:
                            print(f"  ❌ EMPTY GRAPH - needs rebuild!")
                        else:
                            print(f"  ✅ Graph has content")
                        print()
                else:
                    print(f"No graphs found for {folder_name}")
                    print(f"Create one with: python -c \"from morphik import Morphik; Morphik(is_local=True).create_graph('{folder_name}_graph', folder_name='{folder_name}')\"")
            else:
                print(f"Could not fetch graphs: {graph_response.status_code}")
        except Exception as e:
            print(f"Error fetching graphs: {e}")

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Morphik backend at {base_url}")
        print(f"   Make sure Morphik is running: python all_start.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
