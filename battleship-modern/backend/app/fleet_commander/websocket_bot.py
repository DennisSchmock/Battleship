"""WebSocket Bot Interface for Fleet Commander.

Allows external systems to connect and play as bots via WebSocket.
This enables bots written in any language, LLMs, or external AI systems.

Protocol:
=========

1. Connection
   - Connect to: ws://host:port/fleet-commander/bot/{game_id}/{player_id}
   - Authenticate with: {"type": "auth", "token": "your-token"}

2. Server -> Client Messages:

   game_start:
   {
       "type": "game_start",
       "config": {
           "grid_size": [32, 32, 16],
           "fleet_ships": ["destroyer", "cruiser", ...],
           ...
       }
   }

   place_fleet:
   {
       "type": "place_fleet",
       "zone_x_min": 0,
       "zone_x_max": 7
   }

   get_actions:
   {
       "type": "get_actions",
       "view": {
           "turn": 5,
           "my_ships": [...],  // Each ship has has_acted flag
           "visible_enemy_ships": [...],
           "known_cells": {...},
           "storm": {...},
           ...
       }
   }

   turn_result:
   {
       "type": "turn_result",
       "result": {
           "actions_taken": [...],
           "storm_damage": {...},
           ...
       }
   }

   game_end:
   {
       "type": "game_end",
       "won": true,
       "final_view": {...}
   }

   error:
   {
       "type": "error",
       "message": "Description of error"
   }

3. Client -> Server Messages:

   fleet_placement:
   {
       "type": "fleet_placement",
       "placements": [
           {"ship_type": "destroyer", "position": [5, 10, 3], "direction": "north"},
           ...
       ]
   }

   actions:
   {
       "type": "actions",
       "actions": [
           {"action_type": "move", "ship_id": "ship_1", "path": [[5, 11, 3]]},
           {"action_type": "fire", "ship_id": "ship_2", "target": [15, 10, 5]},
           {"action_type": "ability", "ship_id": "ship_4", "ability": "deploy_mine", "target": [6, 10, 3]},
           ...
       ]
   }

Note: Each ship gets 1 action per turn. Ships that have already acted (has_acted=true) cannot act again until the next turn.
"""
import json
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, asdict

from .bot_interface import FleetBot, GameView, create_game_view
from .models import (
    Position, Direction, ShipType, AbilityType,
    GameConfig, Action, MoveAction, FireAction, ScanAction, AbilityAction, LockOnAction,
    TurnResult
)


def serialize_position(pos: Position) -> List[int]:
    """Convert Position to JSON-serializable list."""
    return [pos.x, pos.y, pos.z]


def deserialize_position(data: List[int]) -> Position:
    """Convert list to Position."""
    return Position(data[0], data[1], data[2])


def serialize_direction(direction: Direction) -> str:
    """Convert Direction to string."""
    return direction.name.lower()


def deserialize_direction(name: str) -> Direction:
    """Convert string to Direction."""
    return Direction[name.upper()]


def serialize_ship_type(ship_type: ShipType) -> str:
    """Convert ShipType to string."""
    return ship_type.value


def deserialize_ship_type(name: str) -> ShipType:
    """Convert string to ShipType."""
    return ShipType(name)


def serialize_ability_type(ability_type: AbilityType) -> str:
    """Convert AbilityType to string."""
    return ability_type.value


def deserialize_ability_type(name: str) -> AbilityType:
    """Convert string to AbilityType."""
    return AbilityType(name)


def serialize_config(config: GameConfig) -> Dict[str, Any]:
    """Serialize GameConfig to JSON-compatible dict."""
    return {
        "grid_size": list(config.grid_size),
        "player1_zone": list(config.player1_zone),
        "player2_zone": list(config.player2_zone),
        "fleet_ships": [s.value for s in config.fleet_config.ships],
        "fog_of_war": config.fog_of_war,
        "memory_decay_turns": config.memory_decay_turns,
        "storm_start_turn": config.storm_start_turn,
        "storm_shrink_interval": config.storm_shrink_interval,
        "storm_damage": config.storm_damage,
        "max_turns": config.max_turns,
    }


def serialize_action(action: Action) -> Dict[str, Any]:
    """Serialize an Action to JSON-compatible dict."""
    if isinstance(action, MoveAction):
        return {
            "action_type": "move",
            "ship_id": action.ship_id,
            "path": [serialize_position(p) for p in action.path]
        }
    elif isinstance(action, FireAction):
        result = {
            "action_type": "fire",
            "ship_id": action.ship_id,
            "target": serialize_position(action.target)
        }
        if action.ability:
            result["ability"] = serialize_ability_type(action.ability)
        return result
    elif isinstance(action, ScanAction):
        result = {
            "action_type": "scan",
            "ship_id": action.ship_id,
            "center": serialize_position(action.center)
        }
        if action.ability:
            result["ability"] = serialize_ability_type(action.ability)
        return result
    elif isinstance(action, AbilityAction):
        result = {
            "action_type": "ability",
            "ship_id": action.ship_id,
            "ability": serialize_ability_type(action.ability)
        }
        if action.target:
            result["target"] = serialize_position(action.target)
        if action.target_ship_id:
            result["target_ship_id"] = action.target_ship_id
        return result
    elif isinstance(action, LockOnAction):
        return {
            "action_type": "lock_on",
            "ship_id": action.ship_id,
            "target": serialize_position(action.target)
        }
    else:
        raise ValueError(f"Unknown action type: {type(action)}")


def deserialize_action(data: Dict[str, Any]) -> Action:
    """Deserialize JSON dict to Action."""
    action_type = data["action_type"]
    ship_id = data["ship_id"]

    if action_type == "move":
        path = [deserialize_position(p) for p in data["path"]]
        return MoveAction(ship_id=ship_id, path=path)

    elif action_type == "fire":
        target = deserialize_position(data["target"])
        ability = deserialize_ability_type(data["ability"]) if "ability" in data else None
        return FireAction(ship_id=ship_id, target=target, ability=ability)

    elif action_type == "scan":
        center = deserialize_position(data["center"])
        ability = deserialize_ability_type(data["ability"]) if "ability" in data else None
        return ScanAction(ship_id=ship_id, center=center, ability=ability)

    elif action_type == "ability":
        ability = deserialize_ability_type(data["ability"])
        target = deserialize_position(data["target"]) if "target" in data else None
        target_ship_id = data.get("target_ship_id")
        return AbilityAction(ship_id=ship_id, ability=ability, target=target, target_ship_id=target_ship_id)

    elif action_type == "lock_on":
        target = deserialize_position(data["target"])
        return LockOnAction(ship_id=ship_id, target=target)

    else:
        raise ValueError(f"Unknown action type: {action_type}")


class WebSocketBotAdapter(FleetBot):
    """
    Adapter that wraps WebSocket communication to implement FleetBot interface.

    This allows an external system connected via WebSocket to act as a bot.
    """

    def __init__(self, websocket, name: str = "WebSocketBot"):
        self.websocket = websocket
        self._name = name
        self._config: Optional[GameConfig] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._timeout = 30.0  # 30 second timeout for responses

    def get_name(self) -> str:
        return self._name

    async def _send(self, message: Dict[str, Any]) -> None:
        """Send a message to the WebSocket client."""
        await self.websocket.send_text(json.dumps(message))

    async def _receive(self, expected_type: str) -> Dict[str, Any]:
        """Receive and validate a message from the WebSocket client."""
        try:
            response = await asyncio.wait_for(
                self._response_queue.get(),
                timeout=self._timeout
            )
            if response.get("type") != expected_type:
                raise ValueError(f"Expected {expected_type}, got {response.get('type')}")
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"WebSocket bot timed out waiting for {expected_type}")

    async def handle_message(self, message: str) -> None:
        """Handle incoming message from WebSocket."""
        data = json.loads(message)
        await self._response_queue.put(data)

    async def on_game_start_async(self, config: GameConfig) -> None:
        """Async version of on_game_start."""
        self._config = config
        await self._send({
            "type": "game_start",
            "config": serialize_config(config)
        })

    def on_game_start(self, config: GameConfig) -> None:
        """Sync wrapper - should not be called directly for WebSocket bots."""
        self._config = config

    async def place_fleet_async(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                                ) -> List[Tuple[ShipType, Position, Direction]]:
        """Async version of place_fleet."""
        await self._send({
            "type": "place_fleet",
            "zone_x_min": zone_x_min,
            "zone_x_max": zone_x_max
        })

        response = await self._receive("fleet_placement")
        placements = []
        for p in response["placements"]:
            ship_type = deserialize_ship_type(p["ship_type"])
            position = deserialize_position(p["position"])
            direction = deserialize_direction(p["direction"])
            placements.append((ship_type, position, direction))

        return placements

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        """Sync wrapper - returns empty, actual placement done via async."""
        # This is a fallback - shouldn't be called for WebSocket bots
        from .bot_interface import random_fleet_placement
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    async def get_actions_async(self, view: GameView) -> List[Action]:
        """Async version of get_actions."""
        # Convert view to JSON-serializable dict
        view_dict = {
            "turn": view.turn,
            "my_player_id": view.my_player_id,
            "grid_size": list(view.grid_size),
            "my_ships": [
                {
                    "id": s.id,
                    "positions": [serialize_position(p) for p in s.positions],
                    "ship_type": s.ship_type.value if s.ship_type else None,
                    "hp": s.hp,
                    "max_hp": s.max_hp,
                    "speed": s.speed,
                    "movement_remaining": s.movement_remaining,
                    "has_acted": s.has_acted,
                    "can_act": s.can_act(),
                    "can_fire": s.can_fire(),
                    "can_scan": s.can_scan(),
                    "can_move": s.can_move(),
                    "fire_range": s.get_fire_range(),
                    "scan_range": s.get_scan_range(),
                    "abilities": {
                        k.value: {
                            "can_use": v.can_use,
                            "cooldown": v.cooldown_remaining,
                            "range": v.range,
                            "damage": v.damage,
                            "area_size": v.area_size,
                        }
                        for k, v in (s.ability_info or {}).items()
                    }
                }
                for s in view.my_ships
            ],
            "visible_enemy_ships": [
                {
                    "id": s.id,
                    "positions": [serialize_position(p) for p in s.positions]
                }
                for s in view.visible_enemy_ships
            ],
            "known_cells": {
                f"{p.x},{p.y},{p.z}": status.value
                for p, status in view.known_cells.items()
            },
            "my_mines": [[m[0], serialize_position(m[1])] for m in view.my_mines],
            "my_sensors": [[s[0], serialize_position(s[1])] for s in view.my_sensors],
            "my_decoys": [[d[0], serialize_position(d[1])] for d in view.my_decoys],
            "my_drones": [[d[0], serialize_position(d[1]), d[2]] for d in view.my_drones],
            "storm": {
                "min": serialize_position(view.storm_min) if view.storm_min else None,
                "max": serialize_position(view.storm_max) if view.storm_max else None,
                "turns_until_shrink": view.storm_turns_until_shrink,
                "damage": view.storm_damage
            } if view.storm_min else None
        }

        await self._send({
            "type": "get_actions",
            "view": view_dict
        })

        response = await self._receive("actions")
        actions = [deserialize_action(a) for a in response["actions"]]
        return actions

    def get_actions(self, view: GameView) -> List[Action]:
        """Sync wrapper - returns empty, actual actions done via async."""
        # This is a fallback - shouldn't be called for WebSocket bots
        return []

    async def on_turn_result_async(self, result: TurnResult) -> None:
        """Async version of on_turn_result."""
        result_dict = {
            "turn": result.turn,
            "player_id": result.player_id,
            "actions_taken": [
                {
                    "success": ar.success,
                    "message": ar.message,
                    "action": serialize_action(ar.action) if ar.action else None,
                    "damage_dealt": ar.damage_dealt,
                    "ships_hit": ar.ships_hit,
                    "ships_destroyed": ar.ships_destroyed,
                }
                for ar in result.actions_taken
            ],
            "storm_damage": result.storm_damage_taken,
            "storm_shrunk": result.storm_shrunk,
        }

        await self._send({
            "type": "turn_result",
            "result": result_dict
        })

    def on_turn_result(self, result: TurnResult) -> None:
        """Sync wrapper."""
        pass

    async def on_game_end_async(self, won: bool, view: GameView) -> None:
        """Async version of on_game_end."""
        await self._send({
            "type": "game_end",
            "won": won
        })

    def on_game_end(self, won: bool, view: GameView) -> None:
        """Sync wrapper."""
        pass


# ============================================================================
# Example WebSocket endpoint (for FastAPI)
# ============================================================================

"""
Example FastAPI WebSocket endpoint:

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/fleet-commander/bot/{game_id}")
async def websocket_bot_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()

    # Create adapter
    bot = WebSocketBotAdapter(websocket, name="ExternalBot")

    # Register bot with game manager
    game = get_game(game_id)
    player_id = game.register_bot(bot)

    try:
        # Main message loop
        while True:
            message = await websocket.receive_text()
            await bot.handle_message(message)
    except WebSocketDisconnect:
        game.handle_bot_disconnect(player_id)
"""
