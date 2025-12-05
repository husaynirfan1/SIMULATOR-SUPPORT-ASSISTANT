import time
import sys
import threading
import itertools
import argparse
from morphik import Morphik

# --- CONFIGURATION ---
# Replace with your actual URI (local or cloud)
MORPHIK_URI = "http://localhost:8000" 
# MORPHIK_URI = "https://api.morphik.ai" # Example for cloud

class AsciiLoader:
    """
    A simple ASCII loader animation running in a separate thread.
    """
    def __init__(self, desc="Loading..."):
        self.desc = desc
        self.done = False
        self.thread = threading.Thread(target=self._animate, daemon=True)

    def start(self):
        self.done = False
        self.thread.start()

    def stop(self):
        self.done = True
        self.thread.join()
        sys.stdout.write(f"\r{self.desc} Done!          \n")
        sys.stdout.flush()

    def _animate(self):
        for c in itertools.cycle(['|', '/', '-', '\\']):
            if self.done:
                break
            sys.stdout.write(f"\r{self.desc} {c}")
            sys.stdout.flush()
            time.sleep(0.1)

class MorphikTester:
    def __init__(self, uri):
        # Initialize the Morphik client [cite: 107]
        self.client = Morphik(uri=uri)
        print(f"⚡ Connected to Morphik at {uri}")

    def test_ingest(self, text_content, filename):
        """
        Tests text ingestion[cite: 64, 106].
        """
        loader = AsciiLoader(f"Ingesting '{filename}'")
        loader.start()
        
        try:
            # Ingest text document
            doc = self.client.ingest_text(text_content, filename)
            loader.stop()
            print(f"✅ Ingestion started. Doc ID: {doc.id}")
            return doc.id
        except Exception as e:
            loader.stop()
            print(f"❌ Ingestion failed: {e}")
            sys.exit(1)

    def wait_for_processing(self, doc_id):
        """
        Polls get_document_status until the document is active[cite: 13, 105].
        """
        loader = AsciiLoader(f"Waiting for processing (Doc: {doc_id})")
        loader.start()

        while True:
            try:
                # Check status 
                status_response = self.client.get_document_status(doc_id)
                # Assuming 'active' or 'ready' indicates success based on metadata examples [cite: 16]
                if status_response.status == "active": 
                    break
                elif status_response.status == "failed":
                    loader.stop()
                    print(f"❌ Document processing failed.")
                    sys.exit(1)
                
                time.sleep(1)
            except Exception as e:
                loader.stop()
                print(f"❌ Error polling status: {e}")
                sys.exit(1)
        
        loader.stop()
        print("✅ Document is ready for retrieval.")

    def test_retrieval(self, query_text):
        """
        Tests retrieving chunks[cite: 82, 107].
        """
        loader = AsciiLoader(f"Retrieving chunks for: '{query_text}'")
        loader.start()

        try:
            # Retrieve relevant chunks
            chunks = self.client.retrieve_chunks(query=query_text)
            loader.stop()
            
            print(f"✅ Retrieved {len(chunks)} chunks.")
            for i, chunk in enumerate(chunks[:2]): # Show first 2
                print(f"   [{i+1}] {chunk.content[:50]}...")
            return chunks
        except Exception as e:
            loader.stop()
            print(f"❌ Retrieval failed: {e}")

    def test_query(self, question):
        """
        Tests the generation/chat query.
        """
        loader = AsciiLoader(f"Asking LLM: '{question}'")
        loader.start()

        try:
            # Generate completion using relevant chunks as context
            response = self.client.query(query=question)
            loader.stop()
            
            print(f"✅ Answer: {response.content}")
        except Exception as e:
            loader.stop()
            print(f"❌ Query failed: {e}")

    def cleanup(self, doc_id):
        """
        Tests document deletion[cite: 6, 104].
        """
        loader = AsciiLoader(f"Deleting Document {doc_id}")
        loader.start()
        try:
            self.client.delete_document(doc_id)
            loader.stop()
            print("✅ Cleanup successful.")
        except Exception as e:
            loader.stop()
            print(f"❌ Cleanup failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Morphik SDK ASCII Test Script")
    parser.add_argument("--mode", choices=["all", "ingest", "retrieve", "query", "cleanup"], default="all", help="Test mode")
    parser.add_argument("--doc_id", type=str, help="Document ID (required for retrieve/query/cleanup in individual mode)")
    args = parser.parse_args()

    tester = MorphikTester(MORPHIK_URI)

    # Sample Data
    SAMPLE_TEXT = "Morphik is a powerful RAG framework that simplifies document ingestion and retrieval."
    SAMPLE_FILENAME = "test_morphik_intro.txt"
    SAMPLE_QUERY = "What is Morphik?"

    # --- EXECUTION FLOW ---

    doc_id = args.doc_id

    # 1. INGESTION
    if args.mode in ["all", "ingest"]:
        doc_id = tester.test_ingest(SAMPLE_TEXT, SAMPLE_FILENAME)
        tester.wait_for_processing(doc_id)
        if args.mode == "ingest":
            print(f"ℹ️  Save this ID for other tests: {doc_id}")

    # 2. RETRIEVAL (Requires Doc ID)
    if args.mode in ["all", "retrieve"]:
        if not doc_id:
            print("❌ Error: --doc_id required for retrieval test.")
            sys.exit(1)
        tester.test_retrieval(SAMPLE_QUERY)

    # 3. QUERY / GENERATION (Requires Doc ID context effectively)
    if args.mode in ["all", "query"]:
        if not doc_id:
            print("❌ Error: --doc_id required for query test.")
            sys.exit(1)
        tester.test_query(SAMPLE_QUERY)

    # 4. CLEANUP
    if args.mode in ["all", "cleanup"]:
        if not doc_id:
            print("❌ Error: --doc_id required for cleanup.")
            sys.exit(1)
        tester.cleanup(doc_id)

if __name__ == "__main__":
    main()