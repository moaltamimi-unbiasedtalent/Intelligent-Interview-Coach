"""Return bounded facts from this campaign's disposable database only."""
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not root.name.startswith('ask4mo_story_connected_') or not root.is_dir():
    raise SystemExit('disposable campaign directory required')
a, b, expected_session = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
owner_id = json.loads((root / "accounts.json").read_text())["owner"]["id"]
with sqlite3.connect(f'file:{root / "journey.db"}?mode=ro', uri=True) as db:
    rows = db.execute('SELECT id, user_id FROM candidate_stories ORDER BY id').fetchall()
    uses = db.execute('SELECT user_id, story_id, session_id FROM story_uses ORDER BY story_id').fetchall()
    sessions = db.execute('SELECT session_id, user_id, state_payload FROM interview_sessions').fetchall()
    grants = db.execute('SELECT resource_id, permission, status FROM share_grants').fetchall()
    config = json.loads(sessions[0][2]).get('config', {}) if len(sessions) == 1 else {}
    background = config.get('candidate_background', '')
    other_config = {k: v for k, v in config.items() if k != 'candidate_background'}
    print(json.dumps({'a_row': any(x[0] == a for x in rows), 'b_row': any(x[0] == b for x in rows),
        'one_session': len(sessions) == 1, 'expected_owner_session': len(sessions) == 1 and sessions[0][0] == expected_session and sessions[0][1] == owner_id,
        'other_config_digest': hashlib.sha256(json.dumps(other_config, sort_keys=True).encode()).hexdigest(), 'a_use': sum(x[1] == a for x in uses), 'b_use': sum(x[1] == b for x in uses),
        'same_session': len(sessions) == 1 and all(x[2] == sessions[0][0] and x[0] == sessions[0][1] for x in uses),
        'a_context': f'[[STORY {a} BEGIN]]' in background, 'a_marker': 'SYNTH_SELECTED_CEDAR' in background,
        'b_context': f'[[STORY {b} BEGIN]]' in background and 'SYNTH_UNSELECTED_MAPLE' in background,
        'a_grant': [x[1:] for x in grants if str(x[0]) == str(a)]}))
