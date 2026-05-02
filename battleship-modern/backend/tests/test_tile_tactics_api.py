from fastapi.testclient import TestClient
from app.main import app


def test_quick_game_endpoint():
    c = TestClient(app)
    r = c.post('/api/tile-tactics/quick-game', json={'player1_type': 'greedy', 'player2_type': 'blocking', 'seed': 42})
    assert r.status_code == 200
    data = r.json()
    assert 'winner' in data and 'replay_id' in data
