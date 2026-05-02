import json
from pathlib import Path
import websocket


def call_llm(prompt: str) -> str:
    """Stub: connect your provider here and return action_id string."""
    return ""


def fallback(legal_actions):
    if not legal_actions:
        return None
    best = sorted(legal_actions, key=lambda a: (-a.get('heuristic', {}).get('claims_cells', 0), -a.get('heuristic', {}).get('adjacent_enemy_cells', 0), a['id']))[0]
    return best['id']


def main():
    strategy = Path(__file__).with_name('strategy.md').read_text()
    ws = websocket.create_connection('ws://localhost:8000/ws/tile-tactics?player1_type=websocket&player2_type=greedy&seed=42')
    while True:
        msg = json.loads(ws.recv())
        if msg.get('type') == 'choose_action':
            prompt = f"{strategy}\nSTATE:\n{json.dumps(msg['state'])}\nLEGAL:\n{json.dumps(msg['legal_actions'])}"
            action_id = call_llm(prompt).strip()
            legal_ids = {a['id'] for a in msg['legal_actions']}
            if action_id not in legal_ids:
                action_id = fallback(msg['legal_actions'])
            ws.send(json.dumps({'type': 'action', 'action_id': action_id}))
        elif msg.get('type') == 'game_end':
            print(msg)
            break


if __name__ == '__main__':
    main()
