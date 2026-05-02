import json, uuid
from datetime import datetime, timezone
from pathlib import Path


class TileReplayStorage:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, payload: dict):
        replay_id = payload.get("replay_id") or str(uuid.uuid4())
        payload["replay_id"] = replay_id
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        p = self.directory / f"{replay_id}.json"
        p.write_text(json.dumps(payload, indent=2))
        return replay_id

    def list_replays(self):
        out = []
        for f in sorted(self.directory.glob("*.json")):
            data = json.loads(f.read_text())
            out.append({"replay_id": data.get("replay_id"), "created_at": data.get("created_at"), "winner": data.get("winner")})
        return out

    def load(self, replay_id: str):
        p = self.directory / f"{replay_id}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text())
