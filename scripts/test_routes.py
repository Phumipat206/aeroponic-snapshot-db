#!/usr/bin/env python3
"""Test all routes and report errors."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import app

app.config['TESTING'] = True

routes = ['/', '/upload', '/query', '/daily', '/categories', '/generate-video',
          '/videos', '/stats', '/online', '/security', '/about', '/api/upload/test',
          '/login']

results = []
with app.test_client() as client:
    # Login
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
    print(f"Login: {resp.status_code}")
    
    for r in routes:
        try:
            resp = client.get(r, follow_redirects=True)
            if resp.status_code >= 400:
                body = resp.data.decode('utf-8', errors='replace')
                # Find error type
                import re
                err_match = re.search(r'(NameError|TypeError|ImportError|AttributeError|KeyError|ValueError|FileNotFoundError|jinja2\.\w+Error)[^\n<]*', body)
                err = err_match.group(0) if err_match else body[:150]
                results.append(f"FAIL  {r} → {resp.status_code}: {err}")
            else:
                results.append(f"OK    {r} → {resp.status_code}")
        except Exception as e:
            results.append(f"CRASH {r} → {e}")

print("\n=== ROUTE TEST RESULTS ===")
for r in results:
    print(r)

fails = [r for r in results if not r.startswith("OK")]
print(f"\nTotal: {len(results)}, OK: {len(results)-len(fails)}, Failed: {len(fails)}")
