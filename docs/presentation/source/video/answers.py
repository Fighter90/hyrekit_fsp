"""Верные ответы последней попытки теста в SQLite стенда: python3 answers.py <db>."""

import json, sqlite3, sys
from app.assessment import engine
db = sqlite3.connect(sys.argv[1])
plan = json.loads(db.execute('select plan from assessment_attempts order by created_at desc limit 1').fetchone()[0])
out = []
for d in plan:
    p = engine.PlannedItem(**{k: d[k] for k in ('id', 'family', 'topic', 'level', 'seed')})
    it = engine.materialize(p)
    out.append({'id': p.id, 'kind': it.kind, 'stem': it.stem[:60], 'answer': it.answer})
print(json.dumps(out, ensure_ascii=False))
