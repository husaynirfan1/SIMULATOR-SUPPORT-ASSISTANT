from morphik import Morphik

# Initialize with Morphik URI
client = Morphik(
)

text_doc = client.ingest_file(
    file="/home/husaynirfan/Downloads/NOTESPWN/PersonalNotesPWN-1.txt",
    metadata={"demo_variant": "standard"},
    use_colpali=False
)

# Wait for processing
client.wait_for_document_completion(text_doc.external_id, timeout_seconds=120)

QUESTION = "What are the key takeaways from the uploaded document?"

# Query with text chunks
text_response = client.query(
    query=QUESTION,
    use_colpali=False,
    k=4,
    filters={"demo_variant": "standard"}
)

print(f"Text answer: {text_response.completion}")