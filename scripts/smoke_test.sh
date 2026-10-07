#!/usr/bin/env bash
set -euo pipefail

resp=$(curl -s -F "file=@tests/data/sample.kml" http://localhost:8000/api/files/)
fid=$(echo "$resp" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
status=$(echo "$resp" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
feat=$(echo "$resp" | python3 -c "import sys, json; print(json.load(sys.stdin)['feature_count'])")
test "$status" = "COMPLETED"
test "$feat" = "3"
curl -sf "http://localhost:8000/api/files/$fid/measurements/" | python3 -c "
import sys, json
data = json.load(sys.stdin)
poly = next(x for x in data['results'] if x['geometry_type'] == 'Polygon')
assert poly['area_sq_m'] > 0, f'Polygon area should be positive: {poly}'
"