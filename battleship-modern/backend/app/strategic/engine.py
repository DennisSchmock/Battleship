"""Strategic SpaceBattleship Game Engine."""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum

from .models import (
    Position, Direction, Ship, GameConfig, GameState,
    Action, FireAction, MoveAction, ScanAction,
    FireResult, MoveResult, ScanResult, TurnResult,
    CellStatus, ActionType
)


class GamePhase(Enum):
    SETUP = "setup"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class PlayerState:
    """Internal state for one player."""
    name: str
    ships: List[Ship] = field(default_factory=list)
    occupied_cells: Set[Position] = field(default_factory=set)

    # What this player knows about the enemy
    known_enemy_cells: Dict[Position, CellStatus] = field(default_factory=dict)
    shots_fired: List[Position] = field(default_factory=list)
    shots_received: List[Position] = field(default_factory=list)

    # Tracking
    enemy_ships_destroyed: List[str] = field(default_factory=list)

    def get_ship_at(self, pos: Position) -> Optional[Ship]:
        """Get ship at a position, if any."""
        for ship in self.ships:
            if pos in ship.positions:
                return ship
        return None

    def all_ships_destroyed(self) -> bool:
        return all(ship.is_destroyed for ship in self.ships)

    def rebuild_occupied_cells(self):
        """Rebuild the occupied cells set from ships."""
        self.occupied_cells = set()
        for ship in self.ships:
            if not ship.is_destroyed:
                for pos in ship.positions:
                    self.occupied_cells.add(pos)


@dataclass
class StrategicGame:
    """The main game engine for Strategic SpaceBattleship."""
    config: GameConfig = field(default_factory=GameConfig)
    player1: PlayerState = field(default_factory=lambda: PlayerState(name="Player 1"))
    player2: PlayerState = field(default_factory=lambda: PlayerState(name="Player 2"))
    current_player_idx: int = 0
    turn: int = 0
    phase: GamePhase = GamePhase.SETUP
    winner: Optional[str] = None

    # Event log for replay
    events: List[dict] = field(default_factory=list)

    @property
    def current_player(self) -> PlayerState:
        return self.player1 if self.current_player_idx == 0 else self.player2

    @property
    def opponent(self) -> PlayerState:
        return self.player2 if self.current_player_idx == 0 else self.player1

    def is_valid_position(self, pos: Position) -> bool:
        """Check if position is within the grid."""
        x_max, y_max, z_max = self.config.grid_size
        return (0 <= pos.x < x_max and
                0 <= pos.y < y_max and
                0 <= pos.z < z_max)

    def setup_player_ships(self, player: PlayerState, placements: Optional[List[Tuple[str, Position, Direction]]] = None):
        """
        Place ships for a player.
        If placements is None, place randomly.
        placements: [(ship_id, start_position, direction), ...]
        """
        player.ships = []
        player.occupied_cells = set()

        for idx, (ship_name, ship_size) in enumerate(self.config.ships):
            ship_id = f"{ship_name.lower()}_{idx}"
            ship = Ship(id=ship_id, name=ship_name, size=ship_size)

            if placements:
                # Use provided placement
                _, start_pos, direction = placements[idx]
                positions = self._get_ship_positions(start_pos, direction, ship_size)
                if not self._can_place_ship(player, positions):
                    raise ValueError(f"Invalid placement for {ship_name}")
                ship.positions = positions
            else:
                # Random placement
                ship.positions = self._random_place_ship(player, ship_size)

            player.ships.append(ship)
            for pos in ship.positions:
                player.occupied_cells.add(pos)

    def _get_ship_positions(self, start: Position, direction: Direction, size: int) -> List[Position]:
        """Get all positions a ship would occupy."""
        positions = [start]
        current = start
        for _ in range(size - 1):
            current = current.move(direction)
            positions.append(current)
        return positions

    def _can_place_ship(self, player: PlayerState, positions: List[Position]) -> bool:
        """Check if ship can be placed at these positions."""
        for pos in positions:
            if not self.is_valid_position(pos):
                return False
            if pos in player.occupied_cells:
                return False
        return True

    def _random_place_ship(self, player: PlayerState, size: int) -> List[Position]:
        """Randomly place a ship of given size."""
        directions = list(Direction)
        x_max, y_max, z_max = self.config.grid_size

        for _ in range(1000):
            start = Position(
                random.randint(0, x_max - 1),
                random.randint(0, y_max - 1),
                random.randint(0, z_max - 1)
            )
            direction = random.choice(directions)
            positions = self._get_ship_positions(start, direction, size)

            if self._can_place_ship(player, positions):
                return positions

        raise RuntimeError(f"Could not place ship of size {size}")

    def start_game(self):
        """Start the game after setup."""
        if not self.player1.ships or not self.player2.ships:
            raise RuntimeError("Both players must have ships placed")
        self.phase = GamePhase.PLAYING
        self.turn = 1

    def get_game_state(self, for_player: PlayerState) -> GameState:
        """Get the game state from a player's perspective."""
        return GameState(
            turn=self.turn,
            grid_size=self.config.grid_size,
            my_ships=[Ship(
                id=s.id,
                name=s.name,
                size=s.size,
                positions=list(s.positions),
                hits=set(s.hits),
                move_cooldown=s.move_cooldown
            ) for s in for_player.ships],
            known_cells=dict(for_player.known_enemy_cells),
            my_shots=list(for_player.shots_fired),
            enemy_shots_on_me=list(for_player.shots_received),
            actions_remaining=self.config.actions_per_turn,
            enemy_ships_destroyed=list(for_player.enemy_ships_destroyed)
        )

    def execute_turn(self, actions: List[Action]) -> TurnResult:
        """Execute a player's turn actions."""
        if self.phase != GamePhase.PLAYING:
            raise RuntimeError(f"Cannot execute turn in phase: {self.phase}")

        if len(actions) > self.config.actions_per_turn:
            actions = actions[:self.config.actions_per_turn]

        result = TurnResult()
        player = self.current_player
        enemy = self.opponent

        for action in actions:
            if isinstance(action, FireAction):
                fire_result = self._execute_fire(player, enemy, action)
                result.fire_results.append(fire_result)

            elif isinstance(action, MoveAction):
                move_result = self._execute_move(player, action)
                result.move_results.append(move_result)

            elif isinstance(action, ScanAction):
                scan_result = self._execute_scan(player, enemy, action)
                result.scan_results.append(scan_result)

        # Log event
        self.events.append({
            "turn": self.turn,
            "player": player.name,
            "actions": [a.to_dict() if hasattr(a, 'to_dict') else str(a) for a in actions],
            "results": {
                "fires": [{"target": r.target.to_tuple(), "hit": r.hit, "destroyed": r.destroyed_ship}
                         for r in result.fire_results],
                "moves": [{"ship": r.ship_id, "success": r.success} for r in result.move_results],
                "scans": [{"center": r.center.to_tuple(), "cells_revealed": len(r.revealed)}
                         for r in result.scan_results]
            }
        })

        # Check for winner
        if enemy.all_ships_destroyed():
            self.phase = GamePhase.FINISHED
            self.winner = player.name

        return result

    def _execute_fire(self, player: PlayerState, enemy: PlayerState, action: FireAction) -> FireResult:
        """Execute a fire action."""
        target = action.target

        if not self.is_valid_position(target):
            return FireResult(target=target, hit=False)

        player.shots_fired.append(target)
        enemy.shots_received.append(target)

        # Check for hit
        ship = enemy.get_ship_at(target)
        if ship and target not in ship.hits:
            ship.hits.add(target)

            if self.config.fog_of_war:
                # In fog of war, you only know you hit if you destroyed the ship
                if ship.is_destroyed:
                    # Reveal all ship positions
                    for pos in ship.positions:
                        player.known_enemy_cells[pos] = CellStatus.DESTROYED
                    player.enemy_ships_destroyed.append(ship.name)
                    return FireResult(target=target, hit=True, destroyed_ship=ship.name)
                else:
                    # You don't know you hit!
                    return FireResult(target=target, hit=True)  # Internal hit, but player doesn't know
            else:
                # No fog of war
                player.known_enemy_cells[target] = CellStatus.HIT
                if ship.is_destroyed:
                    for pos in ship.positions:
                        player.known_enemy_cells[pos] = CellStatus.DESTROYED
                    player.enemy_ships_destroyed.append(ship.name)
                    return FireResult(target=target, hit=True, destroyed_ship=ship.name)
                return FireResult(target=target, hit=True)

        # Miss
        if not self.config.fog_of_war:
            player.known_enemy_cells[target] = CellStatus.MISS
        return FireResult(target=target, hit=False)

    def _execute_move(self, player: PlayerState, action: MoveAction) -> MoveResult:
        """Execute a move action."""
        ship = next((s for s in player.ships if s.id == action.ship_id), None)

        if not ship:
            return MoveResult(ship_id=action.ship_id, success=False, reason="Ship not found")

        if not ship.can_move:
            return MoveResult(ship_id=action.ship_id, success=False,
                            reason=f"Ship on cooldown ({ship.move_cooldown} turns)")

        if ship.is_destroyed:
            return MoveResult(ship_id=action.ship_id, success=False, reason="Ship is destroyed")

        # Calculate new positions
        new_positions = [pos.move(action.direction) for pos in ship.positions]

        # Validate new positions
        for pos in new_positions:
            if not self.is_valid_position(pos):
                return MoveResult(ship_id=action.ship_id, success=False, reason="Move out of bounds")
            # Check collision with own ships (excluding this ship)
            for other_ship in player.ships:
                if other_ship.id != ship.id and not other_ship.is_destroyed:
                    if pos in other_ship.positions:
                        return MoveResult(ship_id=action.ship_id, success=False,
                                        reason="Collision with own ship")

        # Execute move
        old_positions = ship.positions
        ship.positions = new_positions
        ship.move_cooldown = self.config.move_cooldown

        # Update hits to new positions (hits follow the ship)
        new_hits = set()
        for i, old_pos in enumerate(old_positions):
            if old_pos in ship.hits:
                new_hits.add(new_positions[i])
        ship.hits = new_hits

        # Rebuild occupied cells
        player.rebuild_occupied_cells()

        return MoveResult(ship_id=action.ship_id, success=True, new_positions=new_positions)

    def _execute_scan(self, player: PlayerState, enemy: PlayerState, action: ScanAction) -> ScanResult:
        """Execute a scan action."""
        center = action.center
        radius = self.config.scan_radius
        revealed = {}

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    pos = Position(center.x + dx, center.y + dy, center.z + dz)
                    if not self.is_valid_position(pos):
                        continue

                    # Check what's at this position
                    ship = enemy.get_ship_at(pos)
                    if ship and not ship.is_destroyed:
                        if pos in ship.hits:
                            status = CellStatus.HIT
                        else:
                            status = CellStatus.HIT  # We found a ship!
                        player.known_enemy_cells[pos] = status
                    else:
                        status = CellStatus.EMPTY
                        player.known_enemy_cells[pos] = status

                    revealed[pos] = status

        return ScanResult(center=center, revealed=revealed)

    def end_turn(self):
        """End the current player's turn."""
        # Decrease cooldowns for current player's ships
        for ship in self.current_player.ships:
            if ship.move_cooldown > 0:
                ship.move_cooldown -= 1

        # Switch players
        self.current_player_idx = 1 - self.current_player_idx

        # Increment turn counter when back to player 1
        if self.current_player_idx == 0:
            self.turn += 1

    def get_replay(self) -> dict:
        """Get full game replay data."""
        return {
            "config": {
                "grid_size": self.config.grid_size,
                "actions_per_turn": self.config.actions_per_turn,
            },
            "player1": self.player1.name,
            "player2": self.player2.name,
            "winner": self.winner,
            "total_turns": self.turn,
            "events": self.events
        }
