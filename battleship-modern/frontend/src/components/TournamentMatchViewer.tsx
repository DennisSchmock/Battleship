import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Stars } from '@react-three/drei';
import * as THREE from 'three';
import './TournamentMatchViewer.css';

// ============================================================================
// TYPES
// ============================================================================

interface Position {
  x: number;
  y: number;
  z: number;
}

interface ShipData {
  id: string;
  type: string;
  positions: Position[];
  hp: number;
  max_hp: number;
  is_destroyed: boolean;
}

interface StormData {
  min: Position;
  max: Position;
  turns_until_shrink: number;
  damage: number;
}

interface FireResult {
  ship_id: string;
  target: Position;
  hit: boolean;
  damage: number;
  destroyed_ship?: string;
}

interface TurnData {
  turn: number;
  player: number;
  player_name: string;
  fire_results: FireResult[];
  move_results: unknown[];
  scan_results: unknown[];
  ability_results: unknown[];
  ships_destroyed: string[];
  storm_damage_dealt: Record<string, number>;
}

interface GameState {
  turn: number;
  phase: string;
  player1_ships: ShipData[];
  player2_ships: ShipData[];
  storm: StormData;
  current_player: number;
  winner?: number;
}

interface ReplayEvent {
  turn: number;
  player_id: number;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

interface ReplayData {
  replay_id: string;
  created_at: string;
  config: {
    grid_size: [number, number, number];
    fleet: string[];
  };
  player1_name: string;
  player2_name: string;
  winner: number | null;
  total_turns: number;
  initial_ships_p1: ShipData[];
  initial_ships_p2: ShipData[];
  events: ReplayEvent[];
}

// Ship colors
const SHIP_COLORS: Record<string, string> = {
  scout: '#00ffaa',
  destroyer: '#4488ff',
  cruiser: '#8844ff',
  support: '#44ff88',
  carrier: '#ffaa00',
  artillery: '#ff4444',
  minelayer: '#888888',
};

const SHIP_EMISSIVE: Record<string, string> = {
  scout: '#00aa66',
  destroyer: '#2244aa',
  cruiser: '#4422aa',
  support: '#22aa44',
  carrier: '#aa6600',
  artillery: '#aa2222',
  minelayer: '#444444',
};

// ============================================================================
// 3D COMPONENTS
// ============================================================================

function AnimatedShip({
  ship,
  playerColor,
  offset,
}: {
  ship: ShipData;
  playerColor: string;
  offset: [number, number, number];
}) {
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const phaseOffset = useRef(Math.random() * Math.PI * 2);

  const shipColor = SHIP_COLORS[ship.type] || playerColor;
  const emissive = SHIP_EMISSIVE[ship.type] || '#222222';
  const healthRatio = ship.hp / ship.max_hp;

  useFrame((state) => {
    if (groupRef.current && !ship.is_destroyed) {
      const bob = Math.sin(state.clock.elapsedTime * 1.5 + phaseOffset.current) * 0.1;
      groupRef.current.position.y = bob;

      if (healthRatio < 0.5) {
        groupRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 2) * 0.05 * (1 - healthRatio);
      }
    }
  });

  if (ship.is_destroyed) {
    return (
      <group>
        {ship.positions.map((pos, i) => (
          <mesh
            key={i}
            position={[
              pos.x + offset[0],
              pos.z + offset[2] + Math.sin(i) * 0.2,
              pos.y + offset[1]
            ]}
            rotation={[Math.random(), Math.random(), Math.random()]}
          >
            <boxGeometry args={[0.3, 0.3, 0.3]} />
            <meshStandardMaterial
              color="#333333"
              transparent
              opacity={0.4}
              metalness={0.8}
              roughness={0.2}
            />
          </mesh>
        ))}
      </group>
    );
  }

  return (
    <group
      ref={groupRef}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      {ship.positions.map((pos, i) => (
        <group key={i}>
          <mesh
            position={[
              pos.x + offset[0],
              pos.z + offset[2],
              pos.y + offset[1]
            ]}
          >
            <boxGeometry args={[0.85, 0.4, 0.85]} />
            <meshStandardMaterial
              color={shipColor}
              metalness={0.7}
              roughness={0.3}
              emissive={emissive}
              emissiveIntensity={hovered ? 0.4 : 0.2}
            />
          </mesh>

          {/* Health indicator */}
          <mesh
            position={[
              pos.x + offset[0],
              pos.z + offset[2] + 0.6,
              pos.y + offset[1]
            ]}
            scale={[healthRatio * 0.8, 0.1, 0.1]}
          >
            <boxGeometry />
            <meshBasicMaterial
              color={healthRatio > 0.5 ? '#00ff00' : healthRatio > 0.25 ? '#ffaa00' : '#ff0000'}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function GridFloor({
  gridSize,
  offset,
}: {
  gridSize: [number, number, number];
  offset: [number, number, number];
}) {
  return (
    <group position={[0, offset[2] - 0.5, 0]}>
      <gridHelper
        args={[Math.max(gridSize[0], gridSize[1]), Math.max(gridSize[0], gridSize[1]), '#1a3a5c', '#0a1a2c']}
        rotation={[0, 0, 0]}
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <planeGeometry args={[gridSize[0], gridSize[1]]} />
        <meshStandardMaterial
          color="#050a15"
          transparent
          opacity={0.9}
        />
      </mesh>
    </group>
  );
}

function StormBoundary({
  storm,
  gridSize: _gridSize,
  offset,
}: {
  storm: StormData;
  gridSize: [number, number, number];
  offset: [number, number, number];
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      const material = meshRef.current.material as THREE.MeshStandardMaterial;
      material.opacity = 0.15 + Math.sin(state.clock.elapsedTime * 2) * 0.05;
    }
  });

  const stormWidth = storm.max.x - storm.min.x;
  const stormDepth = storm.max.y - storm.min.y;
  const stormHeight = storm.max.z - storm.min.z;

  const centerX = (storm.min.x + storm.max.x) / 2 + offset[0];
  const centerY = (storm.min.y + storm.max.y) / 2 + offset[1];
  const centerZ = (storm.min.z + storm.max.z) / 2 + offset[2];

  return (
    <mesh
      ref={meshRef}
      position={[centerX, centerZ, centerY]}
    >
      <boxGeometry args={[stormWidth, stormHeight, stormDepth]} />
      <meshStandardMaterial
        color="#ff4400"
        transparent
        opacity={0.15}
        side={THREE.BackSide}
        wireframe={false}
      />
    </mesh>
  );
}

function LaserProjectile({
  start,
  target,
  hit,
  onComplete,
}: {
  start: [number, number, number];
  target: [number, number, number];
  hit: boolean;
  onComplete: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const progress = useRef(0);

  useFrame((_, delta) => {
    progress.current += delta * 3;

    if (progress.current >= 1) {
      onComplete();
      return;
    }

    if (meshRef.current) {
      meshRef.current.position.set(
        start[0] + (target[0] - start[0]) * progress.current,
        start[1] + (target[1] - start[1]) * progress.current,
        start[2] + (target[2] - start[2]) * progress.current
      );
    }
  });

  return (
    <group>
      <mesh ref={meshRef} position={start}>
        <sphereGeometry args={[0.15, 8, 8]} />
        <meshBasicMaterial color={hit ? '#ff0000' : '#ffaa00'} />
      </mesh>
      <pointLight
        position={[
          start[0] + (target[0] - start[0]) * progress.current,
          start[1] + (target[1] - start[1]) * progress.current,
          start[2] + (target[2] - start[2]) * progress.current,
        ]}
        color={hit ? '#ff0000' : '#ffaa00'}
        intensity={2}
        distance={5}
      />
    </group>
  );
}

function BattleScene({
  gameState,
  currentTurn,
  gridSize,
  player1Name,
  player2Name,
}: {
  gameState: GameState;
  currentTurn: TurnData | null;
  gridSize: [number, number, number];
  player1Name: string;
  player2Name: string;
}) {
  const [projectiles, setProjectiles] = useState<Array<{
    id: number;
    start: [number, number, number];
    target: [number, number, number];
    hit: boolean;
  }>>([]);

  const projectileId = useRef(0);

  const offset: [number, number, number] = useMemo(() => [
    -gridSize[0] / 2 + 0.5,
    -gridSize[1] / 2 + 0.5,
    -gridSize[2] / 2 + 0.5,
  ], [gridSize]);

  // Process turn events
  useEffect(() => {
    if (!currentTurn) return;

    currentTurn.fire_results.forEach((fire, i) => {
      setTimeout(() => {
        const isPlayer1 = currentTurn.player === 0;
        const ships = isPlayer1 ? gameState.player1_ships : gameState.player2_ships;
        const firingShip = ships.find(s => s.id === fire.ship_id);

        let startPos: [number, number, number];
        if (firingShip && firingShip.positions.length > 0) {
          const shipCenter = firingShip.positions[Math.floor(firingShip.positions.length / 2)];
          startPos = [
            shipCenter.x + offset[0],
            shipCenter.z + offset[2],
            shipCenter.y + offset[1],
          ];
        } else {
          startPos = isPlayer1
            ? [-gridSize[0] / 2 - 3, gridSize[2] / 2, 0]
            : [gridSize[0] / 2 + 3, gridSize[2] / 2, 0];
        }

        setProjectiles(prev => [...prev, {
          id: projectileId.current++,
          start: startPos,
          target: [
            fire.target.x + offset[0],
            fire.target.z + offset[2],
            fire.target.y + offset[1],
          ],
          hit: fire.hit,
        }]);
      }, i * 150);
    });
  }, [currentTurn, gridSize, offset, gameState]);

  const removeProjectile = (id: number) => {
    setProjectiles(prev => prev.filter(p => p.id !== id));
  };

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[20, 30, 20]} intensity={1.2} color="#ffffff" />
      <pointLight position={[-20, -10, -20]} intensity={0.4} color="#4488ff" />
      <pointLight position={[20, -10, -20]} intensity={0.4} color="#ff4488" />

      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={0.5} />

      <GridFloor gridSize={gridSize} offset={offset} />

      {gameState.storm && (
        <StormBoundary storm={gameState.storm} gridSize={gridSize} offset={offset} />
      )}

      {gameState.player1_ships.map(ship => (
        <AnimatedShip key={ship.id} ship={ship} playerColor="#4488ff" offset={offset} />
      ))}

      {gameState.player2_ships.map(ship => (
        <AnimatedShip key={ship.id} ship={ship} playerColor="#ff4488" offset={offset} />
      ))}

      {projectiles.map(p => (
        <LaserProjectile
          key={p.id}
          start={p.start}
          target={p.target}
          hit={p.hit}
          onComplete={() => removeProjectile(p.id)}
        />
      ))}

      <Text
        position={[-gridSize[0] / 2 - 3, gridSize[2] / 2 + 2, 0]}
        fontSize={0.6}
        color="#4488ff"
        anchorX="center"
        outlineWidth={0.05}
        outlineColor="#000000"
      >
        {player1Name}
      </Text>
      <Text
        position={[gridSize[0] / 2 + 3, gridSize[2] / 2 + 2, 0]}
        fontSize={0.6}
        color="#ff4488"
        anchorX="center"
        outlineWidth={0.05}
        outlineColor="#000000"
      >
        {player2Name}
      </Text>

      <Text
        position={[0, gridSize[2] / 2 + 3, 0]}
        fontSize={0.5}
        color="#ffffff"
        anchorX="center"
      >
        Turn {gameState.turn}
      </Text>

      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={10}
        maxDistance={80}
        target={[0, 0, 0]}
      />
    </>
  );
}

// ============================================================================
// REPLAY PLAYER LOGIC
// ============================================================================

function useReplayPlayer(replay: ReplayData | null) {
  const [currentTurnIndex, setCurrentTurnIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [currentTurn, setCurrentTurn] = useState<TurnData | null>(null);
  const playbackRef = useRef<number | null>(null);

  // Get all turn events
  const turnEvents = useMemo(() => {
    if (!replay) return [];
    return replay.events.filter(e => e.event_type === 'turn_result');
  }, [replay]);

  // Initialize game state from replay
  useEffect(() => {
    if (!replay) return;

    setGameState({
      turn: 0,
      phase: 'playing',
      player1_ships: replay.initial_ships_p1,
      player2_ships: replay.initial_ships_p2,
      storm: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: replay.config.grid_size[0], y: replay.config.grid_size[1], z: replay.config.grid_size[2] },
        turns_until_shrink: 10,
        damage: 1,
      },
      current_player: 0,
    });
    setCurrentTurnIndex(0);
    setCurrentTurn(null);
  }, [replay]);

  // Apply turn result to update game state
  const applyTurnResult = useCallback((event: ReplayEvent) => {
    const data = event.data as {
      game_state?: {
        player1_ships: ShipData[];
        player2_ships: ShipData[];
        storm?: StormData;
        turn: number;
        winner?: number;
      };
      actions_taken?: Array<{
        action: { type: string; ship_id: string; target?: Position };
        success: boolean;
        damage_dealt: number;
        ships_hit: string[];
        ships_destroyed: string[];
      }>;
    };

    if (data.game_state) {
      setGameState(prev => ({
        ...prev!,
        turn: data.game_state!.turn,
        player1_ships: data.game_state!.player1_ships,
        player2_ships: data.game_state!.player2_ships,
        storm: data.game_state!.storm || prev!.storm,
        winner: data.game_state!.winner,
        current_player: event.player_id,
        phase: data.game_state!.winner !== undefined ? 'finished' : 'playing',
      }));
    }

    // Build turn data for animations
    const fireResults: FireResult[] = [];
    if (data.actions_taken) {
      for (const action of data.actions_taken) {
        if (action.action.type === 'fire' && action.action.target) {
          fireResults.push({
            ship_id: action.action.ship_id,
            target: action.action.target,
            hit: action.ships_hit.length > 0,
            damage: action.damage_dealt,
            destroyed_ship: action.ships_destroyed[0],
          });
        }
      }
    }

    setCurrentTurn({
      turn: event.turn,
      player: event.player_id,
      player_name: event.player_id === 0 ? replay?.player1_name || 'P1' : replay?.player2_name || 'P2',
      fire_results: fireResults,
      move_results: [],
      scan_results: [],
      ability_results: [],
      ships_destroyed: [],
      storm_damage_dealt: {},
    });
  }, [replay]);

  // Playback loop
  useEffect(() => {
    if (!isPlaying || !turnEvents.length) {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
        playbackRef.current = null;
      }
      return;
    }

    playbackRef.current = window.setInterval(() => {
      setCurrentTurnIndex(prev => {
        if (prev >= turnEvents.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        const nextIndex = prev + 1;
        applyTurnResult(turnEvents[nextIndex]);
        return nextIndex;
      });
    }, 1000 / playbackSpeed);

    return () => {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
      }
    };
  }, [isPlaying, turnEvents, playbackSpeed, applyTurnResult]);

  // Seek to specific turn
  const seekToTurn = useCallback((turnIndex: number) => {
    if (!replay || turnIndex < 0 || turnIndex >= turnEvents.length) return;

    // Reset to initial state
    let state: GameState = {
      turn: 0,
      phase: 'playing',
      player1_ships: replay.initial_ships_p1,
      player2_ships: replay.initial_ships_p2,
      storm: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: replay.config.grid_size[0], y: replay.config.grid_size[1], z: replay.config.grid_size[2] },
        turns_until_shrink: 10,
        damage: 1,
      },
      current_player: 0,
    };

    // Apply all events up to the target turn
    for (let i = 0; i <= turnIndex; i++) {
      const event = turnEvents[i];
      const data = event.data as {
        game_state?: {
          player1_ships: ShipData[];
          player2_ships: ShipData[];
          storm?: StormData;
          turn: number;
          winner?: number;
        };
      };

      if (data.game_state) {
        state = {
          ...state,
          turn: data.game_state.turn,
          player1_ships: data.game_state.player1_ships,
          player2_ships: data.game_state.player2_ships,
          storm: data.game_state.storm || state.storm,
          winner: data.game_state.winner,
          current_player: event.player_id,
          phase: data.game_state.winner !== undefined ? 'finished' : 'playing',
        };
      }
    }

    setGameState(state);
    setCurrentTurnIndex(turnIndex);
    applyTurnResult(turnEvents[turnIndex]);
  }, [replay, turnEvents, applyTurnResult]);

  return {
    gameState,
    currentTurn,
    currentTurnIndex,
    totalTurns: turnEvents.length,
    isPlaying,
    playbackSpeed,
    setIsPlaying,
    setPlaybackSpeed,
    seekToTurn,
  };
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const API_BASE = 'http://localhost:8000';

interface TournamentMatchViewerProps {
  mode: 'live' | 'replay';
  tournamentId?: string;  // Required for live mode
  replayId?: string;      // Required for replay mode
  player1Name: string;
  player2Name: string;
  onClose: () => void;
}

export function TournamentMatchViewer({
  mode,
  tournamentId,
  replayId,
  player1Name,
  player2Name,
  onClose,
}: TournamentMatchViewerProps) {
  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [liveGameState, setLiveGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gridSize, setGridSize] = useState<[number, number, number]>([12, 12, 6]);
  const [matchEnded, setMatchEnded] = useState(false);
  const pollRef = useRef<number | null>(null);
  const notFoundCountRef = useRef(0);
  const hasReceivedDataRef = useRef(false);

  const {
    gameState: replayGameState,
    currentTurn,
    currentTurnIndex,
    totalTurns,
    isPlaying,
    playbackSpeed,
    setIsPlaying,
    setPlaybackSpeed,
    seekToTurn,
  } = useReplayPlayer(replay);

  // Use live state or replay state depending on mode
  const gameState = mode === 'live' ? liveGameState : replayGameState;

  // Poll for live match state
  useEffect(() => {
    if (mode !== 'live' || !tournamentId) return;

    async function fetchLiveState() {
      try {
        const res = await fetch(`${API_BASE}/api/fleet-commander/tournaments/${tournamentId}/live`);
        if (res.status === 404) {
          notFoundCountRef.current++;
          // Only consider match ended if we've received data before AND got multiple 404s
          // OR if we've been waiting a while without any data
          if (hasReceivedDataRef.current && notFoundCountRef.current >= 3) {
            setMatchEnded(true);
            setLoading(false);
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          } else if (!hasReceivedDataRef.current && notFoundCountRef.current >= 15) {
            // Waited 3+ seconds without data, match probably ended before we connected
            setMatchEnded(true);
            setLoading(false);
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }
          return;
        }
        if (!res.ok) throw new Error('Failed to fetch live state');
        const data = await res.json();

        // Reset not found counter and mark that we've received data
        notFoundCountRef.current = 0;
        hasReceivedDataRef.current = true;

        setLiveGameState({
          turn: data.game_state.turn,
          phase: data.game_state.phase,
          player1_ships: data.game_state.player1_ships,
          player2_ships: data.game_state.player2_ships,
          storm: data.game_state.storm,
          current_player: data.game_state.current_player,
          winner: data.game_state.winner,
        });

        if (data.game_state.config?.grid_size) {
          setGridSize(data.game_state.config.grid_size);
        }
        setError(null);
        setLoading(false);
      } catch (e) {
        // Don't show error on first poll failure - might just be starting
        if (!loading && hasReceivedDataRef.current) {
          setError('Lost connection to live match');
        }
      }
    }

    // Initial fetch
    fetchLiveState();

    // Poll every 200ms for smooth updates
    pollRef.current = window.setInterval(fetchLiveState, 200);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [mode, tournamentId, loading]);

  // Load replay
  useEffect(() => {
    if (mode !== 'replay' || !replayId) {
      if (mode === 'replay') setLoading(false);
      return;
    }

    async function loadReplay() {
      try {
        const res = await fetch(`${API_BASE}/api/fleet-commander/replays/${replayId}`);
        if (!res.ok) throw new Error('Replay not found');
        const data = await res.json();
        setReplay(data);
        if (data.config?.grid_size) {
          setGridSize(data.config.grid_size);
        }
        setError(null);
      } catch (e) {
        setError('Failed to load replay');
      } finally {
        setLoading(false);
      }
    }

    loadReplay();
  }, [mode, replayId]);

  // Download replay as JSON
  const handleDownload = useCallback(() => {
    if (!replay) return;

    const blob = new Blob([JSON.stringify(replay, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `replay_${replay.replay_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [replay]);

  // Download as training data format
  const handleDownloadTrainingData = useCallback(() => {
    if (!replay) return;

    // Convert to training data format: each turn as a separate training example
    const trainingData = replay.events
      .filter(e => e.event_type === 'turn_result')
      .map(event => {
        const data = event.data as {
          game_state?: unknown;
          actions_taken?: unknown[];
        };
        return {
          turn: event.turn,
          player: event.player_id,
          game_state: data.game_state,
          actions: data.actions_taken,
        };
      });

    const blob = new Blob([JSON.stringify(trainingData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `training_data_${replay.replay_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [replay]);

  if (loading) {
    return (
      <div className="match-viewer">
        <div className="match-viewer-loading">
          {mode === 'live' ? 'Connecting to live match...' : 'Loading replay...'}
        </div>
      </div>
    );
  }

  if (matchEnded && mode === 'live') {
    return (
      <div className="match-viewer">
        <div className="match-viewer-error">
          <p>Match has ended</p>
          <button onClick={onClose}>Back to Tournament</button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="match-viewer">
        <div className="match-viewer-error">
          <p>{error}</p>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  const isLive = mode === 'live';

  return (
    <div className="match-viewer">
      <header className="match-viewer-header">
        <button className="close-btn" onClick={onClose}>
          ← Back
        </button>
        <div className="match-info">
          <span className="player1">{player1Name}</span>
          <span className="vs">vs</span>
          <span className="player2">{player2Name}</span>
          {isLive && <span className="live-badge-header">● LIVE</span>}
        </div>
        <div className="match-actions">
          {!isLive && (
            <>
              <button className="download-btn" onClick={handleDownload} title="Download full replay">
                📥 Replay
              </button>
              <button className="download-btn" onClick={handleDownloadTrainingData} title="Download as training data">
                🧠 Training Data
              </button>
            </>
          )}
        </div>
      </header>

      <div className="match-viewer-canvas">
        {gameState && (
          <Canvas
            camera={{ position: [25, 20, 25], fov: 50 }}
            gl={{ antialias: true }}
          >
            <BattleScene
              gameState={gameState}
              currentTurn={currentTurn}
              gridSize={gridSize}
              player1Name={player1Name}
              player2Name={player2Name}
            />
          </Canvas>
        )}

        {/* Winner overlay */}
        {gameState?.winner !== undefined && (
          <div className="winner-overlay">
            <div className="winner-text">
              🏆 {gameState.winner === 0 ? player1Name : player2Name} Wins!
            </div>
          </div>
        )}
      </div>

      {isLive ? (
        <div className="playback-controls live-controls">
          <div className="live-info">
            <span className="live-indicator-big">● LIVE</span>
            <span className="turn-counter">Turn {gameState?.turn || 0}</span>
          </div>
          <div className="live-status">
            Watching live match in progress...
          </div>
        </div>
      ) : (
        <div className="playback-controls">
          <div className="playback-buttons">
            <button
              className="control-btn"
              onClick={() => seekToTurn(0)}
              disabled={currentTurnIndex === 0}
            >
              ⏮
            </button>
            <button
              className="control-btn"
              onClick={() => seekToTurn(Math.max(0, currentTurnIndex - 1))}
              disabled={currentTurnIndex === 0}
            >
              ◀
            </button>
            <button
              className="control-btn play-btn"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button
              className="control-btn"
              onClick={() => seekToTurn(Math.min(totalTurns - 1, currentTurnIndex + 1))}
              disabled={currentTurnIndex >= totalTurns - 1}
            >
              ▶
            </button>
            <button
              className="control-btn"
              onClick={() => seekToTurn(totalTurns - 1)}
              disabled={currentTurnIndex >= totalTurns - 1}
            >
              ⏭
            </button>
          </div>

          <div className="timeline">
            <input
              type="range"
              min={0}
              max={Math.max(0, totalTurns - 1)}
              value={currentTurnIndex}
              onChange={(e) => seekToTurn(parseInt(e.target.value))}
              className="timeline-slider"
            />
            <span className="turn-counter">
              Turn {currentTurnIndex + 1} / {totalTurns}
            </span>
          </div>

          <div className="speed-control">
            <label>Speed:</label>
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
              <option value={8}>8x</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
