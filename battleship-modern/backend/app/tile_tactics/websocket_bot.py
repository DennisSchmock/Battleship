from dataclasses import asdict

def serialize_legal_actions(legal_actions):
    return [{"id": a.id, "label": a.label, "heuristic": a.heuristic} for a in legal_actions]

def serialize_state(state):
    data = asdict(state)
    data["scores"] = {str(k): v for k, v in data["scores"].items()}
    data["remaining_pieces"] = {str(k): v for k, v in data["remaining_pieces"].items()}
    return data
