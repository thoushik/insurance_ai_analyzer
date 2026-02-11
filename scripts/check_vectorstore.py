"""Simple check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vectorstore import get_vector_store

vs = get_vector_store()
print(f"Total chunks: {vs.collection.count()}")

results = vs.search("underwriting insurance premium", n_results=3)
print(f"\nSearch 'underwriting': {len(results)} results")
for r in results:
    print(f"\nDistance: {r.get('distance', 'N/A')}")
    print(f"Source: {r.get('metadata', {}).get('source', 'Unknown')}")
    text = r.get('text', '')[:200]
    print(f"Text: {text}")
