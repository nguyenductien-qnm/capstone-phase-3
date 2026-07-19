import requests
import json

try:
    res = requests.get("http://localhost:8089/stats/requests")
    if res.status_code == 200:
        data = res.json()
        print(f"State: {data.get('state')}")
        print(f"Total Users: {data.get('user_count')}")
        print(f"Total RPS: {data.get('total_rps')}")
        print(f"Fail Ratio: {data.get('fail_ratio')}")
        
        print("\nDetailed stats per endpoint:")
        for stat in data.get('stats', []):
            name = stat.get('name')
            method = stat.get('method')
            num_reqs = stat.get('num_requests')
            num_fails = stat.get('num_failures')
            p95 = stat.get('percentile_95')
            if num_reqs > 0:
                print(f"  - {method} {name}: {num_fails}/{num_reqs} fails ({num_fails/num_reqs*100:.2f}%), p95={p95}ms")
    else:
        print(f"Failed to get stats, status code: {res.status_code}")
except Exception as e:
    print(f"Error fetching stats: {e}")
