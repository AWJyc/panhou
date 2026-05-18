#!/usr/bin/env bash
for m in cn_a jp kr; do
  echo "=== $m ==="
  curl -s "http://127.0.0.1:8000/api/reports/$m/latest" | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(f'  report_date: {r[\"report_date\"]}  status: {r[\"status\"]}')
print(f'  indices count: {len(r[\"indices\"])}')
for i in r['indices']:
    print(f'    {i[\"name\"]:14s}  date={i.get(\"date\")}  close={i.get(\"close\")}  pct={i.get(\"change_pct\")}')
print()
"
done
echo "--- 历史日期 (最近 10) ---"
for m in cn_a jp kr us; do
  echo "$m:"
  curl -s "http://127.0.0.1:8000/api/reports/$m?limit=10" | python3 -c "
import json, sys
r = json.load(sys.stdin)
for x in r:
    print(f'    {x[\"report_date\"]}  {x[\"status\"]}')
"
done
