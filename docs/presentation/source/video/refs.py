"""Эталонные решения задач открытого раунда Arena для варианта участника: python3 refs.py <round_id> <profile_id>."""

import json, sys
from app.arena import problems
round_id, profile_id = sys.argv[1], sys.argv[2]
out = {c: problems.variant(c, problems.variant_seed(round_id, profile_id, c)).problem.reference(problems.variant(c, problems.variant_seed(round_id, profile_id, c)).params) for c in problems.OPEN_ROUND_PROBLEMS}
print(json.dumps(out))
