#!/usr/bin/env python3
"""
Diagnose ALL folders for graph/ingestion issues
"""

import requests
import json
import sys

def diagnose_folder(folder_name, base_url="http://localhost:8000"):
    """Diagnose a single folder"""

    print("\n" + "=" * 70)
    print(f"📁 FOLDER: {folder_name}")
    print("=" * 70)

    try:
        # Get folder details with documents
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
            print(f"❌ Error: API returned {response.status_code}")
            return None

        data = response.json()

        if not data.get("folders"):
            print(f"❌ Folder '{folder_name}' not found!")
            return None

        folder_info = data["folders"][0]
        doc_info = folder_info.get("document_info", {})
        docs = doc_info.get("documents", [])
        total_count = doc_info.get("document_count", len(docs))

        # Analyze documents
        docs_with_chunks = 0
        docs_without_chunks = 0
        total_chunks = 0
        failed_docs = []
        processing_docs = []
        completed_no_chunks = []

        for doc in docs:
            status = doc.get("system_metadata", {}).get("status", "unknown")
            chunk_ids = doc.get("chunk_ids", [])
            num_chunks = len(chunk_ids) if chunk_ids else 0

            if num_chunks > 0:
                docs_with_chunks += 1
                total_chunks += num_chunks
            else:
                docs_without_chunks += 1
                if status == "failed":
                    failed_docs.append(doc)
                elif status == "processing":
                    processing_docs.append(doc)
                elif status == "completed":
                    completed_no_chunks.append(doc)

        # Print summary
        print(f"Total documents: {total_count}")
        print(f"✅ With chunks: {docs_with_chunks} ({total_chunks} total chunks)")
        print(f"❌ Without chunks: {docs_without_chunks}")

        if failed_docs:
            print(f"   ⚠️  Failed: {len(failed_docs)}")
        if processing_docs:
            print(f"   ⏳ Processing: {len(processing_docs)}")
        if completed_no_chunks:
            print(f"   ⚠️  Completed but no chunks: {len(completed_no_chunks)}")

        # Check graph
        graph_response = requests.get(f"{base_url}/graph", timeout=10)
        if graph_response.status_code == 200:
            graphs = graph_response.json()
            folder_graphs = [g for g in graphs if
                           folder_name in g.get("name", "").lower() or
                           g.get("folder_name") == folder_name]

            if folder_graphs:
                for graph in folder_graphs:
                    entities = len(graph.get('entities', []))
                    relationships = len(graph.get('relationships', []))
                    status = graph.get('system_metadata', {}).get('status', 'unknown')

                    print(f"\n📊 Graph: {graph.get('name')}")
                    print(f"   Status: {status}")
                    print(f"   Entities: {entities}")
                    print(f"   Relationships: {relationships}")

                    if entities == 0 or entities < docs_with_chunks * 2:
                        print(f"   ⚠️  Graph needs rebuild!")
            else:
                print(f"\n📊 No graph found - needs creation!")

        return {
            "folder_name": folder_name,
            "total_docs": total_count,
            "docs_with_chunks": docs_with_chunks,
            "docs_without_chunks": docs_without_chunks,
            "total_chunks": total_chunks,
            "failed": len(failed_docs),
            "processing": len(processing_docs),
            "needs_attention": docs_without_chunks > 0 or total_chunks < 10,
            "graph_exists": len(folder_graphs) > 0 if graph_response.status_code == 200 else False
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Diagnose all folders"""

    print("=" * 70)
    print("MULTI-FOLDER DIAGNOSIS")
    print("=" * 70)

    base_url = "http://localhost:8000"

    # Check if backend is running
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
            print(f"⚠️  Could not list folders, using defaults...")
            folder_names = [
                "visual_kb",
                "interface_specialist",
                "motion_specialist",
                "vibration_specialist",
                "computer_specialist"
            ]
    except Exception as e:
        print(f"⚠️  Error listing folders: {e}")
        folder_names = [
            "visual_kb",
            "interface_specialist",
            "motion_specialist",
            "vibration_specialist",
            "computer_specialist"
        ]

    # Diagnose each folder
    results = []
    for folder_name in folder_names:
        result = diagnose_folder(folder_name, base_url)
        if result:
            results.append(result)

    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    total_folders = len(results)
    folders_with_issues = sum(1 for r in results if r["needs_attention"])
    total_docs = sum(r["total_docs"] for r in results)
    total_chunks = sum(r["total_chunks"] for r in results)
    folders_need_graph = sum(1 for r in results if not r["graph_exists"])

    print(f"\nFolders analyzed: {total_folders}")
    print(f"Total documents: {total_docs}")
    print(f"Total chunks: {total_chunks}")
    print(f"\n⚠️  Folders needing attention: {folders_with_issues}")
    print(f"📊 Folders needing graph: {folders_need_graph}")

    # Show problematic folders
    if folders_with_issues > 0:
        print(f"\n🔧 Folders with issues:")
        for r in results:
            if r["needs_attention"]:
                issues = []
                if r["failed"] > 0:
                    issues.append(f"{r['failed']} failed")
                if r["processing"] > 0:
                    issues.append(f"{r['processing']} processing")
                if r["docs_without_chunks"] > 0:
                    issues.append(f"{r['docs_without_chunks']} no chunks")

                print(f"   • {r['folder_name']}: {', '.join(issues)}")

    # Show folders needing graphs
    if folders_need_graph > 0:
        print(f"\n📊 Folders needing graph creation:")
        for r in results:
            if not r["graph_exists"] and r["docs_with_chunks"] > 0:
                print(f"   • {r['folder_name']} ({r['docs_with_chunks']} docs, {r['total_chunks']} chunks)")

    print("\n" + "=" * 70)
    print("\n💡 Next steps:")
    print("   1. Run: python rebuild_all_graphs.py")
    print("   2. For failed docs, check: morphik-core/logs/worker.log")
    print("   3. Re-upload failed documents after fixing issues")
    print()


if __name__ == "__main__":
    main()
