#!/usr/bin/env bash
for m in jp kr; do
  echo "=== $m ==="
  curl -s "http://127.0.0.1:8000/api/reports/$m/latest" | python3 -c "
import json, sys
r = json.load(sys.stdin)
print('sectors:')
for s in r['sectors'][:5]:
    print(f'  {s[\"name\"]}  | {s[\"note\"][:60]}')
print('movers:')
for x in r['movers'][:5]:
    print(f'  {x[\"name\"]} ({x[\"symbol\"]})')
"
  echo
done
