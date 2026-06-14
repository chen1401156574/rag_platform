import psycopg2
import json

conn = psycopg2.connect('postgresql://postgres:pg123456@localhost:5432/gsk')
cur = conn.cursor()

# 查最新的 trace runs
cur.execute('''
    SELECT trace_id, trace_name, entry_method, status, question, start_time
    FROM t_rag_trace_run
    ORDER BY start_time DESC
    LIMIT 5
''')
runs = cur.fetchall()
print("=== 最近 5 条 trace runs ===")
for r in runs:
    print(f"trace_id={r[0]}, name={r[1]}, entry={r[2]}, status={r[3]}")
    print(f"  question: {r[4]}")
    print(f"  time: {r[5]}")
    print()

# 查最新的 trace nodes (检索节点)
for r in runs:
    trace_id = r[0]
    cur.execute('''
        SELECT node_type, node_name, status, output_json
        FROM t_rag_trace_node
        WHERE trace_id = %s AND node_type = 'VectorRetrieve'
        ORDER BY start_time DESC
        LIMIT 1
    ''', (trace_id,))
    nodes = cur.fetchall()
    for n in nodes:
        print(f"--- VectorRetrieve for trace {trace_id} ---")
        print(f"  status={n[2]}")
        try:
            output = json.loads(n[3]) if n[3] else {}
            refs = output.get('references', [])
            for i, ref in enumerate(refs[:8]):
                content = ref.get('content_with_weight', '')[:200]
                print(f"  chunk[{i}]: {content}...")
        except:
            print(f"  raw output: {n[3][:500] if n[3] else 'none'}")
        print()

cur.close()
conn.close()
