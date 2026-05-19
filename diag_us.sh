#!/usr/bin/env bash
curl -s "http://127.0.0.1:8000/api/reports/us/latest" | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(f'report_date: {r[\"report_date\"]}')
print(f'generated_at: {r[\"generated_at\"]}')
print(f'sectors: {len(r[\"sectors\"])}  movers: {len(r[\"movers\"])}  indices: {len(r[\"indices\"])}')
print('indices:')
for i in r['indices']:
    print(f'  {i[\"name\"]:10s} date={i.get(\"date\")}  close={i[\"close\"]}  pct={i.get(\"change_pct\"):.2f}%')
print('latest 5 mover names:')
for m in r['movers'][:5]:
    print(f'  {m[\"name\"]} ({m[\"symbol\"]}) {m[\"move_type\"]}  {m[\"change_pct\"]:.2f}%')
"

echo
echo "--- us history ---"
curl -s "http://127.0.0.1:8000/api/reports/us?limit=10" | python3 -c "
import json, sys
for x in json.load(sys.stdin):
    print(f'  {x[\"report_date\"]}  {x[\"status\"]}')
"
