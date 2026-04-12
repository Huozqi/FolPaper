import sys
import os
import urllib.request
import urllib.parse
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pubmed_service import PubMedService

query = '("AI"[Title/Abstract] OR "artificial intelligence"[Title/Abstract] OR "deep learning"[Title/Abstract] OR "machine learning"[Title/Abstract] OR "reinforcement learning"[Title/Abstract] AND "molecular optim*"[Title/Abstract] OR "lead optimization"[Title/Abstract] OR "de novo"[Title/Abstract] OR "property predict*"[Title/Abstract] OR "ADMET"[Title/Abstract] OR "toxicity prediction"[Title/Abstract] OR "QSPR"[Title/Abstract] OR "QSAR"[Title/Abstract]) AND (2026/03/07:2026/04/07[dpdat])'

service = PubMedService()
encoded_query = urllib.parse.quote(query)
search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmode=json&retmax=100&sort=pub+date"

print(f"Direct request to: {search_url}")
try:
    req = urllib.request.Request(search_url)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
