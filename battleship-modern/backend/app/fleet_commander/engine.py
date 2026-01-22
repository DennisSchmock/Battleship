"""Fleet Commander Game Engine.

Handles all game logic including ship movement, combat, abilities,
fog of war, and the storm mechanic.
"""
import random
from typing import List, Dict, Set, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, field

from .models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    Ship, ShipConfig, SHIP_CONFIGS, ActiveAbility,
    Drone, Mine, Sensor, Decoy, Storm,
    GameConfig, FleetConfig, PlayerState, KnownCell,
    Action, MoveAction, FireAction, ScanAction, AbilityAction, LockOnAction,
    ActionResult, TurnResult
)


class GamePhase(Enum):
    """Current phase of the game."""
    SETUP = "setup"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class FleetCommanderGame:
    """Main game engine for Fleet Commander."""

    config: GameConfig
    phase: GamePhase = GamePhase.SETUP
    turn: int = 0
    current_player_idx: int = 0

    players: List[PlayerState] = field(default_factory=list)
    storm: Optional[Storm] = None
    winner: Optional[int] = None

    # All entities indexed by position for collision detection
    _occupied_cells: Dict[Position, str] = field(default_factory=dict)  # pos -> entity_id
    _ship_id_counter: int = 0
    _entity_id_counter: int = 0

    def __post_init__(self):
        """Initialize the game."""
        # Create players
        self.players = [
            PlayerState(player_id=0, name="Player 1"),
            PlayerState(player_id=1, name="Player 2")
        ]

        # Initialize storm (starts inactive)
        x, y, z = self.config.grid_size
        self.storm = Storm(
            current_bounds=(Position(0, 0, 0), Position(x - 1, y - 1, z - 1)),
            final_bounds=(Position(x // 4, y // 4, z // 4),
                         Position(3 * x // 4, 3 * y // 4, 3 * z // 4)),
            shrink_rate=self.config.storm_shrink_rate,
            shrink_interval=self.config.storm_shrink_interval,
            damage_per_turn=self.config.storm_damage,
            turns_until_shrink=self.config.storm_start_turn
        )

    def _next_ship_id(self) -> str:
        self._ship_id_counter += 1
        return f"ship_{self._ship_id_counter}"

    def _next_entity_id(self, prefix: str) -> str:
        self._entity_id_counter += 1
        return f"{prefix}_{self._entity_id_counter}"

    # =========================================================================
    # SETUP
    # =========================================================================

    def setup_fleet(self, player_id: int, placements: List[Tuple[ShipType, Position, Direction]]) -> bool:
        """
        Place a player's fleet.

        Args:
            player_id: Which player (0 or 1)
            placements: List of (ship_type, start_position, direction)

        Returns:
            True if placement successful
        """
        player = self.players[player_id]
        zone_min, zone_max = (
            self.config.player1_zone if player_id == 0 else self.config.player2_zone
        )

        for ship_type, start_pos, direction in placements:
            ship_config = SHIP_CONFIGS[ship_type]

            # Calculate all positions for this ship
            positions = [start_pos]
            current = start_pos
            for _ in range(ship_config.size - 1):
                current = current.move(direction)
                positions.append(current)

            # Validate positions
            for pos in positions:
                # Check in zone
                if not (zone_min <= pos.x <= zone_max):
                    return False
                # Check in grid
                if not self._is_valid_position(pos):
                    return False
                # Check not occupied
                if pos in self._occupied_cells:
                    return False

            # Create ship
            ship = Ship(
                id=self._next_ship_id(),
                config=ship_config,
                owner=player_id,
                positions=positions,
                hp=ship_config.max_hp
            )

            # Register positions
            for pos in positions:
                self._occupied_cells[pos] = ship.id
                player.visited_cells.add(pos)

            player.ships.append(ship)

        return True

    def auto_place_fleet(self, player_id: int) -> bool:
        """Automatically place a player's fleet randomly."""
        player = self.players[player_id]
        zone_min, zone_max = (
            self.config.player1_zone if player_id == 0 else self.config.player2_zone
        )
        y_max, z_max = self.config.grid_size[1], self.config.grid_size[2]

        for ship_type in self.config.fleet_config.ships:
            ship_config = SHIP_CONFIGS[ship_type]
            placed = False

            for _ in range(1000):  # Max attempts
                # Random start position in zone
                start = Position(
                    random.randint(zone_min, zone_max),
                    random.randint(0, y_max - 1),
                    random.randint(0, z_max - 1)
                )
                direction = random.choice(list(Direction))

                # Calculate positions
                positions = [start]
                current = start
                valid = True

                for _ in range(ship_config.size - 1):
                    current = current.move(direction)
                    if not self._is_valid_position(current):
                        valid = False
                        break
                    if not (zone_min <= current.x <= zone_max):
                        valid = False
                        break
                    if current in self._occupied_cells:
                        valid = False
                        break
                    positions.append(current)

                if not valid or start in self._occupied_cells:
                    continue

                # Create ship
                ship = Ship(
                    id=self._next_ship_id(),
                    config=ship_config,
                    owner=player_id,
                    positions=positions,
                    hp=ship_config.max_hp
                )

                for pos in positions:
                    self._occupied_cells[pos] = ship.id
                    player.visited_cells.add(pos)

                player.ships.append(ship)
                placed = True
                break

            if not placed:
                return False

        return True

    def start_game(self):
        """Start the game after setup."""
        self.phase = GamePhase.PLAYING
        self.turn = 1
        self.current_player_idx = 0

        # Reset all ships for first turn
        for player in self.players:
            player.action_points = self.config.action_points_per_turn
            for ship in player.ships:
                ship.reset_turn()

    # =========================================================================
    # GAME STATE
    # =========================================================================

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current_player_idx]

    @property
    def opponent(self) -> PlayerState:
        return self.players[1 - self.current_player_idx]

    def _is_valid_position(self, pos: Position) -> bool:
        """Check if position is within grid."""
        x, y, z = self.config.grid_size
        return 0 <= pos.x < x and 0 <= pos.y < y and 0 <= pos.z < z

    def _get_ship_by_id(self, ship_id: str) -> Optional[Ship]:
        """Find a ship by ID."""
        for player in self.players:
            for ship in player.ships:
                if ship.id == ship_id:
                    return ship
        return None

    def _get_entity_at(self, pos: Position) -> Optional[str]:
        """Get entity ID at position."""
        return self._occupied_cells.get(pos)

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def execute_turn(self, actions: List[Action]) -> TurnResult:
        """Execute a player's turn."""
        player = self.current_player
        result = TurnResult(player_id=player.player_id, turn=self.turn)

        for action in actions:
            # Find the ship
            ship = self._get_ship_by_id(action.ship_id)
            if not ship or ship.is_destroyed or ship.owner != player.player_id:
                result.actions_taken.append(ActionResult(
                    success=False,
                    action=action,
                    message="Invalid ship"
                ))
                continue

            # Check action points
            if player.action_points < ship.config.action_cost:
                result.actions_taken.append(ActionResult(
                    success=False,
                    action=action,
                    message="Not enough action points"
                ))
                continue

            # Execute action
            if isinstance(action, MoveAction):
                action_result = self._execute_move(ship, action, player)
            elif isinstance(action, FireAction):
                action_result = self._execute_fire(ship, action, player)
            elif isinstance(action, ScanAction):
                action_result = self._execute_scan(ship, action, player)
            elif isinstance(action, AbilityAction):
                action_result = self._execute_ability(ship, action, player)
            elif isinstance(action, LockOnAction):
                action_result = self._execute_lock_on(ship, action, player)
            else:
                action_result = ActionResult(
                    success=False,
                    action=action,
                    message="Unknown action type"
                )

            if action_result.success:
                player.action_points -= ship.config.action_cost

            result.actions_taken.append(action_result)

        # End turn processing
        self._end_turn(result)

        return result

    def _execute_move(self, ship: Ship, action: MoveAction, player: PlayerState) -> ActionResult:
        """Execute a move action."""
        if ship.has_moved_this_turn and any(
            ab.config.blocks_movement for ab in ship.abilities.values()
            if not ab.can_use  # Used this turn
        ):
            return ActionResult(False, action, "Ship used blocking ability")

        path = action.path
        if not path:
            return ActionResult(False, action, "Empty path")

        # Validate path length
        if len(path) > ship.movement_remaining:
            return ActionResult(False, action, "Path too long for remaining movement")

        # Validate each step
        current_positions = set(ship.positions)
        for i, target in enumerate(path):
            # Must be adjacent to current position
            if i == 0:
                if not any(target.distance_to(p) == 1 for p in ship.positions):
                    return ActionResult(False, action, "First step not adjacent")
            else:
                if path[i].distance_to(path[i-1]) != 1:
                    return ActionResult(False, action, "Path not continuous")

            # Must be valid position
            if not self._is_valid_position(target):
                return ActionResult(False, action, "Path goes outside grid")

            # Must not collide with other ships (except self)
            entity = self._get_entity_at(target)
            if entity and entity != ship.id:
                return ActionResult(False, action, f"Collision at {target.to_tuple()}")

        # Execute move - shift all positions
        # For simplicity, move the "head" of the ship along path
        # and the rest follows
        final_target = path[-1]

        # Calculate direction of movement
        head = ship.positions[0]
        direction = None
        for d in Direction:
            if head.move(d).distance_to(final_target) < head.distance_to(final_target):
                direction = d
                break

        if direction is None:
            # Find direction from path
            dx = final_target.x - head.x
            dy = final_target.y - head.y
            dz = final_target.z - head.z

            if abs(dx) >= abs(dy) and abs(dx) >= abs(dz):
                direction = Direction.EAST if dx > 0 else Direction.WEST
            elif abs(dy) >= abs(dz):
                direction = Direction.SOUTH if dy > 0 else Direction.NORTH
            else:
                direction = Direction.UP if dz > 0 else Direction.DOWN

        # Move ship
        old_positions = ship.positions.copy()

        # Remove from occupied
        for pos in old_positions:
            if self._occupied_cells.get(pos) == ship.id:
                del self._occupied_cells[pos]

        # Calculate new positions (shift in direction)
        move_vector = Position(*direction.value)
        steps = len(path)
        new_positions = [Position(p.x + move_vector.x * steps,
                                  p.y + move_vector.y * steps,
                                  p.z + move_vector.z * steps)
                        for p in ship.positions]

        ship.positions = new_positions
        ship.movement_remaining -= len(path)
        ship.has_moved_this_turn = True

        # Update occupied cells
        for pos in new_positions:
            self._occupied_cells[pos] = ship.id
            player.visited_cells.add(pos)

        # Check for mines
        triggered = []
        for pos in new_positions:
            for other_player in self.players:
                if other_player.player_id == player.player_id:
                    continue
                for mine in other_player.mines:
                    if mine.position == pos and not mine.triggered:
                        mine.triggered = True
                        ship.take_damage(mine.damage)
                        triggered.append(mine.id)

        return ActionResult(
            success=True,
            action=action,
            triggered_mines=triggered
        )

    def _execute_fire(self, ship: Ship, action: FireAction, player: PlayerState) -> ActionResult:
        """Execute a fire action."""
        ability_type = action.ability
        if ability_type not in ship.abilities:
            return ActionResult(False, action, "Ship doesn't have this ability")

        ability = ship.abilities[ability_type]
        if not ability.can_use:
            return ActionResult(False, action, f"Ability on cooldown ({ability.cooldown_remaining})")

        # Check range
        if not ship.center.in_range(action.target, ability.config.range):
            return ActionResult(False, action, "Target out of range")

        # Check blocking
        if ability.config.blocks_movement and ship.has_moved_this_turn:
            return ActionResult(False, action, "Can't use after moving")

        # Execute based on ability type
        ability.use()

        ships_hit = []
        ships_destroyed = []
        damage_dealt = 0

        if ability_type == AbilityType.FIRE:
            # Single target
            hit_result = self._deal_damage_at(action.target, ability.config.damage, player)
            if hit_result:
                ships_hit.append(hit_result[0])
                damage_dealt = hit_result[1]
                if hit_result[2]:
                    ships_destroyed.append(hit_result[0])

        elif ability_type == AbilityType.BURST_FIRE:
            # Multiple shots at same target
            for _ in range(3):
                hit_result = self._deal_damage_at(action.target, ability.config.damage, player)
                if hit_result:
                    if hit_result[0] not in ships_hit:
                        ships_hit.append(hit_result[0])
                    damage_dealt += hit_result[1]
                    if hit_result[2] and hit_result[0] not in ships_destroyed:
                        ships_destroyed.append(hit_result[0])

        elif ability_type == AbilityType.AREA_BOMBARDMENT:
            # Hit 3x3x3 area
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    for dz in range(-1, 2):
                        target = Position(
                            action.target.x + dx,
                            action.target.y + dy,
                            action.target.z + dz
                        )
                        if self._is_valid_position(target):
                            hit_result = self._deal_damage_at(target, ability.config.damage, player)
                            if hit_result:
                                if hit_result[0] not in ships_hit:
                                    ships_hit.append(hit_result[0])
                                damage_dealt += hit_result[1]
                                if hit_result[2] and hit_result[0] not in ships_destroyed:
                                    ships_destroyed.append(hit_result[0])

        elif ability_type == AbilityType.PRECISION_STRIKE:
            # Check lock
            if ability.locked_target != action.target:
                return ActionResult(False, action, "Must lock on target first")
            hit_result = self._deal_damage_at(action.target, ability.config.damage, player)
            if hit_result:
                ships_hit.append(hit_result[0])
                damage_dealt = hit_result[1]
                if hit_result[2]:
                    ships_destroyed.append(hit_result[0])
            ability.locked_target = None

        elif ability_type == AbilityType.PIERCING_SHOT:
            # Calculate direction and hit multiple cells
            dx = action.target.x - ship.center.x
            dy = action.target.y - ship.center.y
            dz = action.target.z - ship.center.z

            # Normalize to get direction
            max_comp = max(abs(dx), abs(dy), abs(dz), 1)
            dx, dy, dz = dx // max_comp, dy // max_comp, dz // max_comp

            current = action.target
            for _ in range(3):  # Pierce through 3 cells
                if self._is_valid_position(current):
                    hit_result = self._deal_damage_at(current, ability.config.damage, player)
                    if hit_result:
                        if hit_result[0] not in ships_hit:
                            ships_hit.append(hit_result[0])
                        damage_dealt += hit_result[1]
                        if hit_result[2] and hit_result[0] not in ships_destroyed:
                            ships_destroyed.append(hit_result[0])
                current = Position(current.x + dx, current.y + dy, current.z + dz)

        # Update fog of war - mark target as known
        player.known_cells[action.target] = KnownCell(
            status=CellStatus.HIT if ships_hit else CellStatus.EMPTY,
            turn_observed=self.turn
        )

        return ActionResult(
            success=True,
            action=action,
            damage_dealt=damage_dealt,
            ships_hit=ships_hit,
            ships_destroyed=ships_destroyed
        )

    def _deal_damage_at(self, pos: Position, damage: int, attacker: PlayerState) -> Optional[Tuple[str, int, bool]]:
        """Deal damage at position. Returns (ship_id, damage_dealt, destroyed) or None."""
        entity_id = self._get_entity_at(pos)
        if not entity_id:
            return None

        ship = self._get_ship_by_id(entity_id)
        if not ship or ship.owner == attacker.player_id:
            return None

        actual_damage = ship.take_damage(damage)

        if ship.is_destroyed:
            # Remove from occupied cells
            for p in ship.positions:
                if self._occupied_cells.get(p) == ship.id:
                    del self._occupied_cells[p]

        return (ship.id, actual_damage, ship.is_destroyed)

    def _execute_scan(self, ship: Ship, action: ScanAction, player: PlayerState) -> ActionResult:
        """Execute a scan action."""
        ability_type = action.ability
        if ability_type not in ship.abilities:
            return ActionResult(False, action, "Ship doesn't have this ability")

        ability = ship.abilities[ability_type]
        if not ability.can_use:
            return ActionResult(False, action, f"Ability on cooldown")

        # Check range
        if not ship.center.in_range(action.center, ability.config.range):
            return ActionResult(False, action, "Scan center out of range")

        ability.use()

        # Reveal cells in area
        radius = ability.config.area_size
        revealed = {}
        is_anti_stealth = ability_type == AbilityType.ANTI_STEALTH_SCAN

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    pos = Position(
                        action.center.x + dx,
                        action.center.y + dy,
                        action.center.z + dz
                    )
                    if not self._is_valid_position(pos):
                        continue

                    # Check what's there
                    entity_id = self._get_entity_at(pos)
                    status = CellStatus.EMPTY

                    if entity_id:
                        target_ship = self._get_ship_by_id(entity_id)
                        if target_ship and target_ship.owner != player.player_id:
                            # Check stealth
                            if target_ship.config.stealth > 0 and not is_anti_stealth:
                                if random.random() < target_ship.config.stealth:
                                    status = CellStatus.EMPTY  # Stealth success
                                else:
                                    status = CellStatus.SHIP
                            else:
                                status = CellStatus.SHIP

                    # Check for mines (only your own)
                    for mine in player.mines:
                        if mine.position == pos:
                            status = CellStatus.MINE

                    # Check for enemy decoys
                    for other in self.players:
                        if other.player_id == player.player_id:
                            continue
                        for decoy in other.decoys:
                            if decoy.position == pos:
                                status = CellStatus.SHIP  # Looks like a ship

                    # Check if in storm
                    if self.storm and self.storm.is_in_storm(pos):
                        # Can still see but mark as storm
                        pass  # Keep status but note it's in storm

                    revealed[pos] = status
                    player.known_cells[pos] = KnownCell(
                        status=status,
                        turn_observed=self.turn
                    )

        return ActionResult(
            success=True,
            action=action,
            cells_revealed=revealed
        )

    def _execute_ability(self, ship: Ship, action: AbilityAction, player: PlayerState) -> ActionResult:
        """Execute a special ability."""
        ability_type = action.ability
        if ability_type not in ship.abilities:
            return ActionResult(False, action, "Ship doesn't have this ability")

        ability = ship.abilities[ability_type]
        if not ability.can_use:
            return ActionResult(False, action, "Ability on cooldown")

        if ability_type == AbilityType.REPAIR:
            # Find target ship
            target_ship = self._get_ship_by_id(action.target_ship_id) if action.target_ship_id else None
            if not target_ship or target_ship.owner != player.player_id:
                return ActionResult(False, action, "Invalid repair target")
            if not ship.center.in_range(target_ship.center, ability.config.range):
                return ActionResult(False, action, "Target out of range")

            # Heal
            heal_amount = min(1, target_ship.config.max_hp - target_ship.hp)
            target_ship.hp += heal_amount
            ability.use()

            return ActionResult(success=True, action=action, damage_dealt=-heal_amount)

        elif ability_type == AbilityType.JAM:
            # Jamming is passive - just mark that we used it
            ability.use()
            # In a real implementation, this would affect enemy scans
            return ActionResult(success=True, action=action)

        elif ability_type == AbilityType.DEPLOY_DECOY:
            if not action.target or not self._is_valid_position(action.target):
                return ActionResult(False, action, "Invalid decoy position")
            if not ship.center.in_range(action.target, ability.config.range):
                return ActionResult(False, action, "Position out of range")

            decoy = Decoy(
                id=self._next_entity_id("decoy"),
                owner=player.player_id,
                position=action.target
            )
            player.decoys.append(decoy)
            ability.use()

            return ActionResult(success=True, action=action)

        elif ability_type == AbilityType.DEPLOY_MINE:
            if not action.target or not self._is_valid_position(action.target):
                return ActionResult(False, action, "Invalid mine position")
            if not ship.center.in_range(action.target, ability.config.range):
                return ActionResult(False, action, "Position out of range")
            if self._get_entity_at(action.target):
                return ActionResult(False, action, "Position occupied")

            mine = Mine(
                id=self._next_entity_id("mine"),
                owner=player.player_id,
                position=action.target,
                damage=ability.config.damage
            )
            player.mines.append(mine)
            ability.use()

            return ActionResult(success=True, action=action)

        elif ability_type == AbilityType.DEPLOY_SENSOR:
            if not action.target or not self._is_valid_position(action.target):
                return ActionResult(False, action, "Invalid sensor position")
            if not ship.center.in_range(action.target, ability.config.range):
                return ActionResult(False, action, "Position out of range")

            sensor = Sensor(
                id=self._next_entity_id("sensor"),
                owner=player.player_id,
                position=action.target
            )
            player.sensors.append(sensor)
            ability.use()

            return ActionResult(success=True, action=action)

        elif ability_type == AbilityType.LAUNCH_DRONE:
            drone = Drone(
                id=self._next_entity_id("drone"),
                owner=player.player_id,
                position=ship.center
            )
            player.drones.append(drone)
            ability.use()

            return ActionResult(success=True, action=action)

        return ActionResult(False, action, "Unknown ability")

    def _execute_lock_on(self, ship: Ship, action: LockOnAction, player: PlayerState) -> ActionResult:
        """Lock on to a target for precision strike."""
        if AbilityType.PRECISION_STRIKE not in ship.abilities:
            return ActionResult(False, action, "Ship can't lock on")

        ability = ship.abilities[AbilityType.PRECISION_STRIKE]
        if not ship.center.in_range(action.target, ability.config.range):
            return ActionResult(False, action, "Target out of range")

        ability.locked_target = action.target

        return ActionResult(success=True, action=action)

    # =========================================================================
    # TURN MANAGEMENT
    # =========================================================================

    def _end_turn(self, result: TurnResult):
        """Process end of turn."""
        # Apply storm damage
        if self.storm and self.turn >= self.config.storm_start_turn:
            for player in self.players:
                for ship in player.ships:
                    if ship.is_destroyed:
                        continue
                    for pos in ship.positions:
                        if self.storm.is_in_storm(pos):
                            damage = ship.take_damage(self.storm.damage_per_turn)
                            if damage > 0:
                                result.storm_damage_taken[ship.id] = damage
                            break  # Only damage once per ship

            # Tick storm
            if self.storm.tick():
                result.storm_shrunk = True

        # Decay old fog of war info
        current_player = self.current_player
        if self.config.fog_of_war and self.config.memory_decay_turns > 0:
            expired = []
            for pos, cell in current_player.known_cells.items():
                if self.turn - cell.turn_observed > self.config.memory_decay_turns:
                    if pos not in current_player.visited_cells:
                        expired.append(pos)
            for pos in expired:
                del current_player.known_cells[pos]

        # Remove expired decoys
        for player in self.players:
            player.decoys = [d for d in player.decoys if d.turns_remaining > 0]
            for decoy in player.decoys:
                decoy.turns_remaining -= 1

        # Remove triggered mines
        for player in self.players:
            player.mines = [m for m in player.mines if not m.triggered]

        # Check victory conditions
        self._check_victory()

        # Switch player
        self.current_player_idx = 1 - self.current_player_idx
        if self.current_player_idx == 0:
            self.turn += 1

        # Reset for next player's turn
        next_player = self.current_player
        next_player.action_points = self.config.action_points_per_turn
        for ship in next_player.ships:
            if not ship.is_destroyed:
                ship.reset_turn()

    def _check_victory(self):
        """Check if someone has won."""
        p1_alive = self.players[0].combat_ships_alive
        p2_alive = self.players[1].combat_ships_alive

        if p1_alive == 0 and p2_alive == 0:
            # Draw - whoever has more total HP wins
            p1_hp = sum(s.hp for s in self.players[0].ships if not s.is_destroyed)
            p2_hp = sum(s.hp for s in self.players[1].ships if not s.is_destroyed)
            self.winner = 0 if p1_hp >= p2_hp else 1
            self.phase = GamePhase.FINISHED
        elif p1_alive == 0:
            self.winner = 1
            self.phase = GamePhase.FINISHED
        elif p2_alive == 0:
            self.winner = 0
            self.phase = GamePhase.FINISHED
        elif self.turn >= self.config.max_turns:
            # Time limit - most ships wins
            self.winner = 0 if p1_alive >= p2_alive else 1
            self.phase = GamePhase.FINISHED

    # =========================================================================
    # GAME STATE FOR BOTS
    # =========================================================================

    def get_visible_state(self, player_id: int) -> dict:
        """Get the game state visible to a specific player."""
        player = self.players[player_id]
        opponent = self.players[1 - player_id]

        # Own ships (full info)
        own_ships = [ship.to_dict() for ship in player.ships]

        # Enemy ships (only if in known cells with SHIP status)
        visible_enemy_ships = []
        for ship in opponent.ships:
            if ship.is_destroyed:
                continue
            visible = False
            for pos in ship.positions:
                cell = player.known_cells.get(pos)
                if cell and cell.status == CellStatus.SHIP:
                    visible = True
                    break
            if visible:
                visible_enemy_ships.append({
                    "id": ship.id,
                    "positions": [p.to_tuple() for p in ship.positions],
                    # Don't reveal full info
                })

        # Storm bounds
        storm_info = None
        if self.storm:
            min_b, max_b = self.storm.current_bounds
            storm_info = {
                "min": min_b.to_tuple(),
                "max": max_b.to_tuple(),
                "turns_until_shrink": self.storm.turns_until_shrink,
                "damage": self.storm.damage_per_turn
            }

        return {
            "turn": self.turn,
            "phase": self.phase.value,
            "my_player_id": player_id,
            "action_points": player.action_points,
            "my_ships": own_ships,
            "visible_enemy_ships": visible_enemy_ships,
            "known_cells": {
                str(p.to_tuple()): {"status": c.status.value, "turn": c.turn_observed}
                for p, c in player.known_cells.items()
            },
            "my_mines": [{"id": m.id, "pos": m.position.to_tuple()} for m in player.mines],
            "my_sensors": [{"id": s.id, "pos": s.position.to_tuple()} for s in player.sensors],
            "my_decoys": [{"id": d.id, "pos": d.position.to_tuple()} for d in player.decoys],
            "my_drones": [{"id": d.id, "pos": d.position.to_tuple(), "hp": d.hp} for d in player.drones],
            "storm": storm_info,
            "grid_size": self.config.grid_size,
        }
