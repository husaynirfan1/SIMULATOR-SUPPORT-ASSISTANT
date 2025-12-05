"""Test the path logic from script.py"""
import os

# Simulate script.py logic
script_dir = "/home/husaynirfan/sse-ai-v2/multi_agent_system/ot_apps"
OUTPUT_BASE_DIR = script_dir

# Simulated output path
safe_name = "John_Doe"
date_str = "20251203_120000"
filename = "OT_Form_12_2025.xlsx"

output_dir = os.path.join(OUTPUT_BASE_DIR, safe_name, date_str)
output_path = os.path.join(output_dir, filename)

print(f"OUTPUT_BASE_DIR: {OUTPUT_BASE_DIR}")
print(f"os.path.dirname(OUTPUT_BASE_DIR): {os.path.dirname(OUTPUT_BASE_DIR)}")
print(f"output_path: {output_path}")

relative_path = os.path.relpath(output_path, os.path.dirname(OUTPUT_BASE_DIR))
print(f"relative_path: {relative_path}")

download_url = f"http://localhost:8082/files/{relative_path.replace(os.sep, '/')}"
print(f"download_url: {download_url}")

print("\n=== Server mount point ===")
print("app.mount('/files/ot_apps', StaticFiles(directory='ot_apps'), name='ot_files')")
print("\nThis means:")
print("  URL: /files/ot_apps/John_Doe/20251203_120000/OT_Form_12_2025.xlsx")
print("  Maps to: ot_apps/John_Doe/20251203_120000/OT_Form_12_2025.xlsx")
print(f"\nGenerated URL: {download_url}")
print(f"Expected URL:  http://localhost:8082/files/ot_apps/{safe_name}/{date_str}/{filename}")
