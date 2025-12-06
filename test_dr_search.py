#!/usr/bin/env python3
"""Test DR search functionality"""

import sys
sys.path.insert(0, '/home/husaynirfan/sse-ai-v2')

from multi_agent_system.agent_tools import search_dr_in_csv

# Test search for PFD
print("Testing DR search for 'PFD'...")
print("="*60)

result = search_dr_in_csv("PFD")

print(f"\nResults count: {len(result.get('results', []))}")
print(f"\nAnswer:\n{result.get('answer', 'No answer')}")

if result.get('results'):
    print(f"\n\nFirst 3 DR records:")
    for i, dr in enumerate(result['results'][:3], 1):
        print(f"\n{i}. DR-{dr.get('DeficiencyNumber')}: {dr.get('Issue Description', '')[:100]}")
