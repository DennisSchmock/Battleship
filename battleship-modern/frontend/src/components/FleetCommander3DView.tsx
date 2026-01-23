import { useRef, useMemo, useState, useEffect, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Line, Stars, Trail } from '@react-three/drei';
import * as THREE from 'three';

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
  speed?: number;
  abilities?: Record<string, { can_use: boolean }>;
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

interface MoveResult {
  ship_id: string;
  success: boolean;
  path: Position[];
}

interface ScanResult {
  ship_id: string;
  center: Position;
  revealed_cells: Position[];
  detected_ships: string[];
}

interface AbilityResult {
  ship_id: string;
  ability: string;
  success: boolean;
  details: Record<string, unknown>;
}

interface TurnData {
  turn: number;
  player: number;
  player_name: string;
  fire_results: FireResult[];
  move_results: MoveResult[];
  scan_results: ScanResult[];
  ability_results: AbilityResult[];
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

interface ReplayInfo {
  replay_id: string;
  player1_name: string;
  player2_name: string;
  winner?: number;
  total_turns: number;
  created_at: string;
}

// Ship type colors
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
// ANIMATED COMPONENTS
// ============================================================================

// Floating ship with bobbing animation and engine glow
function AnimatedShip({
  ship,
  playerColor,
  offset,
  isEnemy,
}: {
  ship: ShipData;
  playerColor: string;
  offset: [number, number, number];
  isEnemy: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const baseY = useRef(0);
  const phaseOffset = useRef(Math.random() * Math.PI * 2);

  const shipColor = SHIP_COLORS[ship.type] || playerColor;
  const emissive = SHIP_EMISSIVE[ship.type] || '#222222';
  const healthRatio = ship.hp / ship.max_hp;

  useFrame((state) => {
    if (groupRef.current && !ship.is_destroyed) {
      // Bobbing motion
      const bob = Math.sin(state.clock.elapsedTime * 1.5 + phaseOffset.current) * 0.1;
      groupRef.current.position.y = baseY.current + bob;

      // Subtle rotation for damaged ships
      if (healthRatio < 0.5) {
        groupRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 2) * 0.05 * (1 - healthRatio);
      }
    }
  });

  if (ship.is_destroyed) {
    // Debris visualization
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

  // Calculate ship center for label
  const center = ship.positions.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y, z: acc.z + p.z }),
    { x: 0, y: 0, z: 0 }
  );
  const shipCenter = {
    x: center.x / ship.positions.length,
    y: center.y / ship.positions.length,
    z: center.z / ship.positions.length,
  };

  return (
    <group
      ref={groupRef}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      {ship.positions.map((pos, i) => (
        <group key={i}>
          {/* Main ship body */}
          <mesh
            position={[pos.x + offset[0], pos.z + offset[2], pos.y + offset[1]]}
          >
            <boxGeometry args={[0.8, 0.8, 0.8]} />
            <meshStandardMaterial
              color={shipColor}
              emissive={isEnemy ? '#ff2200' : emissive}
              emissiveIntensity={hovered ? 0.8 : isEnemy ? 0.4 : 0.3}
              transparent
              opacity={isEnemy ? 0.75 : 0.95}
              metalness={0.6}
              roughness={0.3}
            />
          </mesh>

          {/* Enemy indicator ring */}
          {isEnemy && (
            <mesh
              position={[pos.x + offset[0], pos.z + offset[2], pos.y + offset[1]]}
              rotation={[Math.PI / 2, 0, 0]}
            >
              <ringGeometry args={[0.5, 0.6, 16]} />
              <meshBasicMaterial color="#ff4444" transparent opacity={0.6} side={2} />
            </mesh>
          )}

          {/* Engine glow */}
          <pointLight
            position={[pos.x + offset[0], pos.z + offset[2] - 0.3, pos.y + offset[1]]}
            color={isEnemy ? '#ff4400' : shipColor}
            intensity={hovered ? 1 : 0.3}
            distance={2}
          />

          {/* Damage indicator */}
          {healthRatio < 1 && (
            <mesh
              position={[pos.x + offset[0], pos.z + offset[2] + 0.6, pos.y + offset[1]]}
            >
              <boxGeometry args={[0.8 * healthRatio, 0.05, 0.1]} />
              <meshBasicMaterial color={healthRatio > 0.5 ? '#44ff44' : healthRatio > 0.25 ? '#ffaa00' : '#ff4444'} />
            </mesh>
          )}
        </group>
      ))}

      {/* Ship connector lines */}
      {ship.positions.length > 1 && (
        <Line
          points={ship.positions.map(p => [
            p.x + offset[0],
            p.z + offset[2],
            p.y + offset[1]
          ] as [number, number, number])}
          color={shipColor}
          lineWidth={3}
          opacity={isEnemy ? 0.3 : 0.8}
          transparent
        />
      )}

      {/* Ship info label - always visible for enemies, hover for own */}
      {(hovered || isEnemy) && (
        <Text
          position={[
            shipCenter.x + offset[0],
            shipCenter.z + offset[2] + 1.2,
            shipCenter.y + offset[1]
          ]}
          fontSize={isEnemy ? 0.3 : 0.4}
          color={isEnemy ? '#ff6666' : shipColor}
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.05}
          outlineColor="#000000"
        >
          {ship.type.toUpperCase()} {hovered ? `(${ship.hp}/${ship.max_hp})` : ''}
        </Text>
      )}
    </group>
  );
}

// Storm boundary visualization
function StormBoundary({
  storm,
  gridSize,
  offset,
}: {
  storm: StormData;
  gridSize: [number, number, number];
  offset: [number, number, number];
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [pulseIntensity, setPulseIntensity] = useState(0);

  useFrame((state) => {
    setPulseIntensity(Math.sin(state.clock.elapsedTime * 2) * 0.3 + 0.7);
  });

  // Calculate safe zone dimensions
  const safeWidth = storm.max.x - storm.min.x + 1;
  const safeHeight = storm.max.y - storm.min.y + 1;
  const safeDepth = storm.max.z - storm.min.z + 1;

  const safeCenterX = (storm.min.x + storm.max.x) / 2 + 0.5;
  const safeCenterY = (storm.min.y + storm.max.y) / 2 + 0.5;
  const safeCenterZ = (storm.min.z + storm.max.z) / 2 + 0.5;

  // Storm particles at the boundary
  const stormParticles = useMemo(() => {
    const particles: { pos: [number, number, number]; delay: number }[] = [];
    const numParticles = 100;

    for (let i = 0; i < numParticles; i++) {
      const side = Math.floor(Math.random() * 6);
      let x = 0, y = 0, z = 0;

      switch (side) {
        case 0: // -X face
          x = storm.min.x;
          y = storm.min.y + Math.random() * safeHeight;
          z = storm.min.z + Math.random() * safeDepth;
          break;
        case 1: // +X face
          x = storm.max.x + 1;
          y = storm.min.y + Math.random() * safeHeight;
          z = storm.min.z + Math.random() * safeDepth;
          break;
        case 2: // -Y face
          x = storm.min.x + Math.random() * safeWidth;
          y = storm.min.y;
          z = storm.min.z + Math.random() * safeDepth;
          break;
        case 3: // +Y face
          x = storm.min.x + Math.random() * safeWidth;
          y = storm.max.y + 1;
          z = storm.min.z + Math.random() * safeDepth;
          break;
        case 4: // -Z face
          x = storm.min.x + Math.random() * safeWidth;
          y = storm.min.y + Math.random() * safeHeight;
          z = storm.min.z;
          break;
        case 5: // +Z face
          x = storm.min.x + Math.random() * safeWidth;
          y = storm.min.y + Math.random() * safeHeight;
          z = storm.max.z + 1;
          break;
      }

      particles.push({
        pos: [x + offset[0], z + offset[2], y + offset[1]],
        delay: Math.random() * Math.PI * 2,
      });
    }
    return particles;
  }, [storm, offset, safeWidth, safeHeight, safeDepth]);

  return (
    <group>
      {/* Safe zone wireframe */}
      <mesh
        ref={meshRef}
        position={[
          safeCenterX + offset[0],
          safeCenterZ + offset[2],
          safeCenterY + offset[1]
        ]}
      >
        <boxGeometry args={[safeWidth, safeDepth, safeHeight]} />
        <meshBasicMaterial
          color="#00ff88"
          transparent
          opacity={0.1 * pulseIntensity}
          wireframe
        />
      </mesh>

      {/* Storm boundary edges */}
      <lineSegments
        position={[
          safeCenterX + offset[0],
          safeCenterZ + offset[2],
          safeCenterY + offset[1]
        ]}
      >
        <edgesGeometry args={[new THREE.BoxGeometry(safeWidth, safeDepth, safeHeight)]} />
        <lineBasicMaterial color="#ff4444" opacity={pulseIntensity} transparent linewidth={2} />
      </lineSegments>

      {/* Storm particles */}
      {stormParticles.map((particle, i) => (
        <StormParticle key={i} position={particle.pos} delay={particle.delay} />
      ))}

      {/* Storm warning indicator */}
      <Text
        position={[
          safeCenterX + offset[0],
          safeCenterZ + offset[2] + safeDepth / 2 + 1,
          safeCenterY + offset[1]
        ]}
        fontSize={0.5}
        color="#ff4444"
        anchorX="center"
      >
        STORM: {storm.turns_until_shrink} turns
      </Text>
    </group>
  );
}

function StormParticle({ position, delay }: { position: [number, number, number]; delay: number }) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      const t = state.clock.elapsedTime + delay;
      meshRef.current.position.y = position[1] + Math.sin(t * 3) * 0.5;
      meshRef.current.scale.setScalar(0.1 + Math.sin(t * 5) * 0.05);
    }
  });

  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[0.1, 8, 8]} />
      <meshBasicMaterial color="#ff6644" transparent opacity={0.6} />
    </mesh>
  );
}

// Laser projectile with trail
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
  const [progress, setProgress] = useState(0);
  const [exploding, setExploding] = useState(false);
  const [explosionProgress, setExplosionProgress] = useState(0);

  useFrame((_, delta) => {
    if (exploding) {
      setExplosionProgress(p => {
        const newP = p + delta * 4;
        if (newP > 1) onComplete();
        return newP;
      });
    } else {
      setProgress(p => {
        const newP = p + delta * 5; // Fast projectile
        if (newP >= 1) {
          setExploding(true);
          return 1;
        }
        return newP;
      });

      if (meshRef.current) {
        meshRef.current.position.x = start[0] + (target[0] - start[0]) * progress;
        meshRef.current.position.y = start[1] + (target[1] - start[1]) * progress;
        meshRef.current.position.z = start[2] + (target[2] - start[2]) * progress;
      }
    }
  });

  if (exploding) {
    return (
      <Explosion
        position={target}
        isHit={hit}
        progress={explosionProgress}
      />
    );
  }

  return (
    <Trail
      width={0.5}
      length={6}
      color={hit ? '#ff4400' : '#4488ff'}
      attenuation={(t) => t * t}
    >
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.1, 8, 8]} />
        <meshStandardMaterial
          color={hit ? '#ff6600' : '#66aaff'}
          emissive={hit ? '#ff4400' : '#4488ff'}
          emissiveIntensity={3}
        />
      </mesh>
    </Trail>
  );
}

// Explosion effect
function Explosion({
  position,
  isHit,
  progress,
}: {
  position: [number, number, number];
  isHit: boolean;
  progress: number;
}) {
  const scale = progress * (isHit ? 1.5 : 0.8);
  const opacity = Math.max(0, 1 - progress);

  return (
    <group position={position}>
      {/* Core explosion */}
      <mesh scale={[scale, scale, scale]}>
        <sphereGeometry args={[0.5, 16, 16]} />
        <meshBasicMaterial
          color={isHit ? '#ffaa00' : '#4488ff'}
          transparent
          opacity={opacity}
        />
      </mesh>

      {/* Outer ring */}
      <mesh scale={[scale * 1.5, scale * 1.5, scale * 1.5]}>
        <ringGeometry args={[0.3, 0.5, 16]} />
        <meshBasicMaterial
          color={isHit ? '#ff4400' : '#88aaff'}
          transparent
          opacity={opacity * 0.5}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Light flash */}
      <pointLight
        color={isHit ? '#ff6600' : '#4488ff'}
        intensity={5 * opacity}
        distance={3}
      />
    </group>
  );
}

// Scan wave effect
function ScanWave({
  center,
  onComplete,
}: {
  center: [number, number, number];
  onComplete: () => void;
}) {
  const [scale, setScale] = useState(0.1);
  const [opacity, setOpacity] = useState(0.8);

  useFrame((_, delta) => {
    setScale(s => s + delta * 6);
    setOpacity(o => {
      const newO = o - delta * 1.2;
      if (newO <= 0) onComplete();
      return Math.max(0, newO);
    });
  });

  return (
    <group position={center}>
      {/* Expanding scan sphere */}
      <mesh scale={[scale, scale, scale]}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial
          color="#00ff88"
          transparent
          opacity={opacity * 0.3}
          wireframe
        />
      </mesh>

      {/* Inner glow */}
      <mesh scale={[scale * 0.8, scale * 0.8, scale * 0.8]}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshBasicMaterial
          color="#88ffaa"
          transparent
          opacity={opacity * 0.2}
        />
      </mesh>

      <pointLight
        color="#00ff88"
        intensity={3 * opacity}
        distance={scale * 2}
      />
    </group>
  );
}

// Grid with fog of war
function GridWithFog({
  gridSize,
  knownCells,
  offset,
}: {
  gridSize: [number, number, number];
  knownCells?: Set<string>;
  offset: [number, number, number];
}) {
  const [x, y, z] = gridSize;

  // Grid edges
  const edges = useMemo(() => {
    const lines: [number, number, number][][] = [];
    const halfX = x / 2;
    const halfY = y / 2;
    const halfZ = z / 2;

    // Bottom face
    lines.push([[-halfX, -halfZ, -halfY], [halfX, -halfZ, -halfY]]);
    lines.push([[halfX, -halfZ, -halfY], [halfX, -halfZ, halfY]]);
    lines.push([[halfX, -halfZ, halfY], [-halfX, -halfZ, halfY]]);
    lines.push([[-halfX, -halfZ, halfY], [-halfX, -halfZ, -halfY]]);

    // Top face
    lines.push([[-halfX, halfZ, -halfY], [halfX, halfZ, -halfY]]);
    lines.push([[halfX, halfZ, -halfY], [halfX, halfZ, halfY]]);
    lines.push([[halfX, halfZ, halfY], [-halfX, halfZ, halfY]]);
    lines.push([[-halfX, halfZ, halfY], [-halfX, halfZ, -halfY]]);

    // Vertical edges
    lines.push([[-halfX, -halfZ, -halfY], [-halfX, halfZ, -halfY]]);
    lines.push([[halfX, -halfZ, -halfY], [halfX, halfZ, -halfY]]);
    lines.push([[halfX, -halfZ, halfY], [halfX, halfZ, halfY]]);
    lines.push([[-halfX, -halfZ, halfY], [-halfX, halfZ, halfY]]);

    return lines;
  }, [x, y, z]);

  return (
    <group>
      {/* Grid boundary */}
      {edges.map((edge, i) => (
        <Line
          key={i}
          points={edge}
          color="#223344"
          lineWidth={1}
          opacity={0.5}
          transparent
        />
      ))}

      {/* Floor grid */}
      <gridHelper
        args={[x, x, '#112233', '#0a1520']}
        position={[0, -z / 2 - 0.5, 0]}
      />

      {/* Axis labels */}
      <Text position={[x / 2 + 1.5, 0, 0]} fontSize={0.6} color="#4488ff">X</Text>
      <Text position={[0, 0, y / 2 + 1.5]} fontSize={0.6} color="#44ff88">Y</Text>
      <Text position={[0, z / 2 + 1.5, 0]} fontSize={0.6} color="#ff4488">Z</Text>
    </group>
  );
}

// ============================================================================
// MAIN SCENE
// ============================================================================

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

  const [scanWaves, setScanWaves] = useState<Array<{
    id: number;
    center: [number, number, number];
  }>>([]);

  const projectileId = useRef(0);
  const scanId = useRef(0);

  const offset: [number, number, number] = useMemo(() => [
    -gridSize[0] / 2 + 0.5,
    -gridSize[1] / 2 + 0.5,
    -gridSize[2] / 2 + 0.5,
  ], [gridSize]);

  // Process turn events
  useEffect(() => {
    if (!currentTurn) return;

    // Spawn projectiles for fire actions
    currentTurn.fire_results.forEach((fire, i) => {
      setTimeout(() => {
        // Find the ship that fired to get its position
        const isPlayer1 = currentTurn.player === 0;
        const ships = isPlayer1 ? gameState.player1_ships : gameState.player2_ships;
        const firingShip = ships.find(s => s.id === fire.ship_id);

        let startPos: [number, number, number];
        if (firingShip && firingShip.positions.length > 0) {
          // Use the center of the firing ship
          const shipCenter = firingShip.positions[Math.floor(firingShip.positions.length / 2)];
          startPos = [
            shipCenter.x + offset[0],
            shipCenter.z + offset[2],
            shipCenter.y + offset[1],
          ];
        } else {
          // Fallback to edge position
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

    // Spawn scan waves
    currentTurn.scan_results.forEach((scan, i) => {
      setTimeout(() => {
        setScanWaves(prev => [...prev, {
          id: scanId.current++,
          center: [
            scan.center.x + offset[0],
            scan.center.z + offset[2],
            scan.center.y + offset[1],
          ],
        }]);
      }, i * 100 + currentTurn.fire_results.length * 150);
    });
  }, [currentTurn, gridSize, offset, gameState]);

  const removeProjectile = (id: number) => {
    setProjectiles(prev => prev.filter(p => p.id !== id));
  };

  const removeScanWave = (id: number) => {
    setScanWaves(prev => prev.filter(s => s.id !== id));
  };

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.3} />
      <pointLight position={[20, 30, 20]} intensity={1.2} color="#ffffff" />
      <pointLight position={[-20, -10, -20]} intensity={0.4} color="#4488ff" />
      <pointLight position={[20, -10, -20]} intensity={0.4} color="#ff4488" />

      {/* Starfield background */}
      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={0.5} />

      {/* Grid */}
      <GridWithFog gridSize={gridSize} offset={offset} />

      {/* Storm boundary */}
      {gameState.storm && (
        <StormBoundary
          storm={gameState.storm}
          gridSize={gridSize}
          offset={offset}
        />
      )}

      {/* Player 1 ships */}
      {gameState.player1_ships.map(ship => (
        <AnimatedShip
          key={ship.id}
          ship={ship}
          playerColor="#4488ff"
          offset={offset}
          isEnemy={false}
        />
      ))}

      {/* Player 2 ships */}
      {gameState.player2_ships.map(ship => (
        <AnimatedShip
          key={ship.id}
          ship={ship}
          playerColor="#ff4488"
          offset={offset}
          isEnemy={false}
        />
      ))}

      {/* Projectiles */}
      {projectiles.map(p => (
        <LaserProjectile
          key={p.id}
          start={p.start}
          target={p.target}
          hit={p.hit}
          onComplete={() => removeProjectile(p.id)}
        />
      ))}

      {/* Scan waves */}
      {scanWaves.map(s => (
        <ScanWave
          key={s.id}
          center={s.center}
          onComplete={() => removeScanWave(s.id)}
        />
      ))}

      {/* Player labels */}
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

      {/* Turn info */}
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
        autoRotate={false}
        target={[0, 0, 0]}
      />
    </>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface BotType {
  id: string;
  name: string;
  description: string;
}

interface ActionInfo {
  type: string;
  ship_id: string;
  ship_type: string;
  success: boolean;
  damage?: number;
  ships_hit?: string[];
  ships_destroyed?: string[];
  target?: Position;
}

const DEFAULT_BOTS: BotType[] = [
  { id: 'tactical', name: 'Tactical Bot', description: 'Uses all ship abilities strategically' },
  { id: 'aggressive', name: 'Aggressive Bot', description: 'Focuses on maximum firepower' },
  { id: 'defensive', name: 'Defensive Bot', description: 'Prioritizes survival and repairs' },
  { id: 'random', name: 'Random Bot', description: 'Baseline - random actions' },
];

export function FleetCommander3DView() {
  const [wsConnected, setWsConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [currentTurn, setCurrentTurn] = useState<TurnData | null>(null);
  const [player1Name, setPlayer1Name] = useState('Player 1');
  const [player2Name, setPlayer2Name] = useState('Player 2');
  const [gridSize, setGridSize] = useState<[number, number, number]>([24, 24, 12]);
  const [log, setLog] = useState<string[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [replays, setReplays] = useState<ReplayInfo[]>([]);
  const [selectedReplay, setSelectedReplay] = useState<string | null>(null);
  const [replayData, setReplayData] = useState<any>(null);
  const [replayTurn, setReplayTurn] = useState(0);
  const [mode, setMode] = useState<'live' | 'replay'>('live');

  // Bot selection
  const [botTypes, setBotTypes] = useState<BotType[]>(DEFAULT_BOTS);
  const [player1Bot, setPlayer1Bot] = useState('tactical');
  const [player2Bot, setPlayer2Bot] = useState('aggressive');

  // Current turn actions
  const [currentActions, setCurrentActions] = useState<ActionInfo[]>([]);
  const [actionPoints, setActionPoints] = useState({ p1: 0, p2: 0 });

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch available replays and bot types
  useEffect(() => {
    fetch('/api/fleet-commander/replays')
      .then(res => res.json())
      .then(data => setReplays(data.replays || []))
      .catch(err => console.error('Failed to fetch replays:', err));

    fetch('/api/fleet-commander/bot-types')
      .then(res => res.json())
      .then(data => {
        if (data.types && data.types.length > 0) {
          setBotTypes(data.types);
        }
      })
      .catch(err => console.error('Failed to fetch bot types:', err));
  }, []);

  // Connect to WebSocket for live game
  const connectToGame = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setMode('live');
    setIsPlaying(true);
    setLog([]);

    const ws = new WebSocket(`ws://${window.location.host}/ws/fleet-commander`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      addLog('Connected to Fleet Commander');
      // Send start game message with bot selections
      ws.send(JSON.stringify({
        action: 'start_game',
        player1_type: player1Bot,
        player2_type: player2Bot,
        small_grid: true,
        delay: 400
      }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      switch (msg.type) {
        case 'game_start': {
          const d = msg.data;
          setPlayer1Name(d.player1.name);
          setPlayer2Name(d.player2.name);
          setGridSize([d.config.grid_size[0], d.config.grid_size[1], d.config.grid_size[2]]);

          // Convert ships to GameState format
          const convertShips = (ships: any[]): ShipData[] => ships.map(s => ({
            id: s.id,
            type: s.type,
            positions: s.positions.map((p: any) => ({ x: p[0], y: p[1], z: p[2] })),
            hp: s.hp,
            max_hp: s.max_hp,
            is_destroyed: s.is_destroyed || false,
          }));

          setGameState({
            turn: 0,
            phase: 'playing',
            player1_ships: convertShips(d.player1.ships),
            player2_ships: convertShips(d.player2.ships),
            storm: d.storm ? {
              min: { x: d.storm.min[0], y: d.storm.min[1], z: d.storm.min[2] },
              max: { x: d.storm.max[0], y: d.storm.max[1], z: d.storm.max[2] },
              turns_until_shrink: 5,
              damage: 1,
            } : { min: { x: 0, y: 0, z: 0 }, max: { x: d.config.grid_size[0]-1, y: d.config.grid_size[1]-1, z: d.config.grid_size[2]-1 }, turns_until_shrink: 10, damage: 1 },
            current_player: 0,
          });
          addLog(`Game started: ${d.player1.name} vs ${d.player2.name}`);
          break;
        }

        case 'turn': {
          const d = msg.data;

          // Convert ships to GameState format
          const convertShips = (ships: any[]): ShipData[] => ships.map(s => ({
            id: s.id,
            type: s.type,
            positions: s.positions.map((p: any) => ({ x: p[0], y: p[1], z: p[2] })),
            hp: s.hp,
            max_hp: s.max_hp,
            is_destroyed: s.is_destroyed || false,
          }));

          // Build turn data for animations (only successful actions)
          const fireResults: FireResult[] = d.actions
            .filter((a: any) => a.type === 'fire' && a.data?.target && a.success !== false)
            .map((a: any) => ({
              ship_id: a.data.ship_id,
              target: { x: a.data.target[0], y: a.data.target[1], z: a.data.target[2] },
              hit: a.ships_hit?.length > 0,
              damage: a.damage || 0,
              destroyed_ship: a.ships_destroyed?.[0],
            }));

          const scanResults: ScanResult[] = d.actions
            .filter((a: any) => a.type === 'scan' && a.data?.center)
            .map((a: any) => ({
              ship_id: a.data.ship_id,
              center: { x: a.data.center[0], y: a.data.center[1], z: a.data.center[2] },
              revealed_cells: [],
              detected_ships: [],
            }));

          const turnData: TurnData = {
            turn: d.turn,
            player: d.player_id,
            player_name: d.player,
            fire_results: fireResults,
            move_results: [],
            scan_results: scanResults,
            ability_results: [],
            ships_destroyed: d.actions.flatMap((a: any) => a.ships_destroyed || []),
            storm_damage_dealt: d.storm_damage || {},
          };

          setCurrentTurn(turnData);
          setGameState({
            turn: d.turn,
            phase: 'playing',
            player1_ships: convertShips(d.state.player1.ships),
            player2_ships: convertShips(d.state.player2.ships),
            storm: d.state.storm ? {
              min: { x: d.state.storm.min[0], y: d.state.storm.min[1], z: d.state.storm.min[2] },
              max: { x: d.state.storm.max[0], y: d.state.storm.max[1], z: d.state.storm.max[2] },
              turns_until_shrink: d.state.storm.turns_until_shrink,
              damage: 1,
            } : { min: { x: 0, y: 0, z: 0 }, max: { x: 15, y: 15, z: 7 }, turns_until_shrink: 10, damage: 1 },
            current_player: d.player_id,
          });

          // Update action points
          setActionPoints({
            p1: d.state.player1.action_points || 0,
            p2: d.state.player2.action_points || 0,
          });

          // Extract detailed actions
          const actionsInfo: ActionInfo[] = d.actions.map((a: any) => ({
            type: a.type,
            ship_id: a.data?.ship_id || 'unknown',
            ship_type: a.data?.ship_type || '',
            success: a.success ?? true,
            damage: a.damage || 0,
            ships_hit: a.ships_hit || [],
            ships_destroyed: a.ships_destroyed || [],
            target: a.data?.target ? { x: a.data.target[0], y: a.data.target[1], z: a.data.target[2] } : undefined,
          }));
          setCurrentActions(actionsInfo);

          // Log turn summary
          const moveCount = actionsInfo.filter((a: ActionInfo) => a.type === 'move').length;
          const fireCount = actionsInfo.filter((a: ActionInfo) => a.type === 'fire').length;
          const scanCount = actionsInfo.filter((a: ActionInfo) => a.type === 'scan').length;
          const abilityCount = actionsInfo.filter((a: ActionInfo) => a.type === 'ability').length;
          const hits = fireResults.filter(f => f.hit).length;

          let logMsg = `T${d.turn} ${d.player}:`;
          if (moveCount > 0) logMsg += ` ${moveCount} moves`;
          if (fireCount > 0) logMsg += ` ${fireCount} fires (${hits} hits)`;
          if (scanCount > 0) logMsg += ` ${scanCount} scans`;
          if (abilityCount > 0) logMsg += ` ${abilityCount} abilities`;
          addLog(logMsg);

          if (turnData.ships_destroyed.length > 0) {
            addLog(`DESTROYED: ${turnData.ships_destroyed.join(', ')}`);
          }
          break;
        }

        case 'game_end': {
          const d = msg.data;
          setIsPlaying(false);
          addLog(`GAME OVER: ${d.winner} wins! (${d.turns} turns)`);
          if (d.replay_id) {
            addLog(`Replay saved: ${d.replay_id.slice(0, 8)}...`);
            // Refresh replay list
            fetch('/api/fleet-commander/replays')
              .then(res => res.json())
              .then(data => setReplays(data.replays || []));
          }
          break;
        }
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      setIsPlaying(false);
      addLog('Disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      addLog('Connection error');
    };
  }, [player1Bot, player2Bot]);

  // Load and play replay
  const loadReplay = useCallback(async (replayId: string) => {
    try {
      const res = await fetch(`/api/fleet-commander/replays/${replayId}`);
      const data = await res.json();

      if (data.error) {
        addLog(`Error loading replay: ${data.error}`);
        return;
      }

      setMode('replay');
      setSelectedReplay(replayId);
      setReplayData(data);
      setReplayTurn(0);
      setPlayer1Name(data.player1_name);
      setPlayer2Name(data.player2_name);
      setGridSize([data.config.grid_size[0], data.config.grid_size[1], data.config.grid_size[2]]);

      // Convert ships format
      const convertShips = (ships: any[]): ShipData[] => ships.map(s => ({
        id: s.id,
        type: s.type,
        positions: s.positions.map((p: any) => ({ x: p[0], y: p[1], z: p[2] })),
        hp: s.hp,
        max_hp: s.max_hp,
        is_destroyed: s.is_destroyed || false,
      }));

      // Set initial state from initial_ships_p1 and initial_ships_p2
      if (data.initial_ships_p1 && data.initial_ships_p2) {
        setGameState({
          turn: 0,
          phase: 'playing',
          player1_ships: convertShips(data.initial_ships_p1),
          player2_ships: convertShips(data.initial_ships_p2),
          storm: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: data.config.grid_size[0] - 1, y: data.config.grid_size[1] - 1, z: data.config.grid_size[2] - 1 },
            turns_until_shrink: data.config.storm_start_turn || 10,
            damage: 1,
          },
          current_player: 0,
        });
      }

      addLog(`Loaded replay: ${data.player1_name} vs ${data.player2_name}`);
    } catch (err) {
      console.error('Failed to load replay:', err);
      addLog('Failed to load replay');
    }
  }, []);

  // Step through replay
  const stepReplay = useCallback((direction: number) => {
    if (!replayData || !replayData.events) return;

    const newIdx = Math.max(0, Math.min(replayTurn + direction, replayData.events.length - 1));
    setReplayTurn(newIdx);

    const event = replayData.events[newIdx];

    // Convert ships format
    const convertShips = (ships: any[]): ShipData[] => ships.map(s => ({
      id: s.id,
      type: s.type,
      positions: s.positions.map((p: any) => ({ x: p[0], y: p[1], z: p[2] })),
      hp: s.hp,
      max_hp: s.max_hp,
      is_destroyed: s.is_destroyed || false,
    }));

    if (event.event_type === 'turn_result' && event.data.game_state) {
      const gs = event.data.game_state;

      // Build turn data for animations from actions_taken (only successful)
      const fireResults: FireResult[] = (event.data.actions_taken || [])
        .filter((a: any) => a.action?.type === 'fire' && a.success !== false)
        .map((a: any) => ({
          ship_id: a.action.ship_id,
          target: { x: a.action.target[0], y: a.action.target[1], z: a.action.target[2] },
          hit: a.ships_hit?.length > 0 || a.damage_dealt > 0,
          damage: a.damage_dealt || 0,
          destroyed_ship: a.ships_destroyed?.[0],
        }));

      const scanResults: ScanResult[] = (event.data.actions_taken || [])
        .filter((a: any) => a.action?.type === 'scan')
        .map((a: any) => ({
          ship_id: a.action.ship_id,
          center: { x: a.action.center[0], y: a.action.center[1], z: a.action.center[2] },
          revealed_cells: [],
          detected_ships: [],
        }));

      const turnData: TurnData = {
        turn: event.turn,
        player: event.player_id,
        player_name: event.player_id === 0 ? player1Name : player2Name,
        fire_results: fireResults,
        move_results: [],
        scan_results: scanResults,
        ability_results: [],
        ships_destroyed: (event.data.actions_taken || []).flatMap((a: any) => a.ships_destroyed || []),
        storm_damage_dealt: event.data.storm_damage || {},
      };

      setCurrentTurn(turnData);
      setGameState({
        turn: event.turn,
        phase: 'playing',
        player1_ships: convertShips(gs.player1_ships || []),
        player2_ships: convertShips(gs.player2_ships || []),
        storm: gs.storm_bounds ? {
          min: { x: gs.storm_bounds[0][0], y: gs.storm_bounds[0][1], z: gs.storm_bounds[0][2] },
          max: { x: gs.storm_bounds[1][0], y: gs.storm_bounds[1][1], z: gs.storm_bounds[1][2] },
          turns_until_shrink: 5,
          damage: 1,
        } : { min: { x: 0, y: 0, z: 0 }, max: { x: gridSize[0]-1, y: gridSize[1]-1, z: gridSize[2]-1 }, turns_until_shrink: 5, damage: 1 },
        current_player: event.player_id,
      });
    } else if (event.event_type === 'game_start' && event.data) {
      setGameState({
        turn: 0,
        phase: 'playing',
        player1_ships: convertShips(event.data.ships_p1 || replayData.initial_ships_p1 || []),
        player2_ships: convertShips(event.data.ships_p2 || replayData.initial_ships_p2 || []),
        storm: {
          min: { x: 0, y: 0, z: 0 },
          max: { x: gridSize[0] - 1, y: gridSize[1] - 1, z: gridSize[2] - 1 },
          turns_until_shrink: 10,
          damage: 1,
        },
        current_player: 0,
      });
      setCurrentTurn(null);
    }
  }, [replayData, replayTurn, player1Name, player2Name, gridSize]);

  const addLog = (message: string) => {
    setLog(prev => [...prev.slice(-19), message]);
  };

  const cameraDistance = Math.max(gridSize[0], gridSize[1], gridSize[2]) * 1.3;

  return (
    <div className="fleet-commander-view">
      <div className="control-panel">
        <h2>Fleet Commander</h2>

        {/* Bot Selection */}
        <div className="bot-selection">
          <div className="bot-selector">
            <label>Player 1</label>
            <select
              value={player1Bot}
              onChange={(e) => setPlayer1Bot(e.target.value)}
              disabled={isPlaying}
            >
              {botTypes.map(bot => (
                <option key={bot.id} value={bot.id}>{bot.name}</option>
              ))}
            </select>
          </div>
          <div className="vs-label">VS</div>
          <div className="bot-selector">
            <label>Player 2</label>
            <select
              value={player2Bot}
              onChange={(e) => setPlayer2Bot(e.target.value)}
              disabled={isPlaying}
            >
              {botTypes.map(bot => (
                <option key={bot.id} value={bot.id}>{bot.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mode-buttons">
          <button
            onClick={connectToGame}
            disabled={isPlaying}
            className={mode === 'live' && isPlaying ? 'active' : ''}
          >
            {isPlaying ? 'Game Running...' : 'Start New Game'}
          </button>
        </div>

        {/* Current Actions Display */}
        {isPlaying && currentActions.length > 0 && (
          <div className="actions-panel">
            <h3>Turn {gameState?.turn || 0} Actions</h3>
            <div className="actions-list">
              {currentActions.map((action, i) => (
                <div key={i} className={`action-item ${action.type} ${action.ships_hit && action.ships_hit.length > 0 ? 'hit' : ''}`}>
                  <span className="action-type">{action.type.toUpperCase()}</span>
                  <span className="action-ship">{action.ship_id.split('_')[0]}</span>
                  {action.damage > 0 && <span className="action-damage">-{action.damage} HP</span>}
                  {action.ships_destroyed && action.ships_destroyed.length > 0 && (
                    <span className="action-destroyed">DESTROYED!</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="replay-section">
          <h3>Replays</h3>
          <div className="replay-list">
            {replays.length === 0 ? (
              <p className="no-replays">No replays available</p>
            ) : (
              replays.map(replay => (
                <button
                  key={replay.replay_id}
                  onClick={() => loadReplay(replay.replay_id)}
                  className={selectedReplay === replay.replay_id ? 'selected' : ''}
                >
                  <span className="replay-players">
                    {replay.player1_name} vs {replay.player2_name}
                  </span>
                  <span className="replay-info">
                    {replay.total_turns} turns • {replay.winner !== undefined && replay.winner !== null ? (replay.winner === 0 ? replay.player1_name : replay.player2_name) : 'Draw'}
                  </span>
                </button>
              ))
            )}
          </div>

          {mode === 'replay' && replayData && (
            <div className="replay-controls">
              <button onClick={() => stepReplay(-10)}>⏪ -10</button>
              <button onClick={() => stepReplay(-1)}>◀ Prev</button>
              <span className="turn-indicator">
                Turn {replayTurn} / {replayData.events?.length || 0}
              </span>
              <button onClick={() => stepReplay(1)}>Next ▶</button>
              <button onClick={() => stepReplay(10)}>+10 ⏩</button>
            </div>
          )}
        </div>

        <div className="game-log">
          <h3>Battle Log</h3>
          <div className="log-entries">
            {log.map((entry, i) => (
              <div key={i} className="log-entry">{entry}</div>
            ))}
          </div>
        </div>

        {gameState && (
          <div className="stats-panel">
            <h3>Fleet Status</h3>
            <div className="fleet-status">
              <div className="player-status player1">
                <span className="player-name">{player1Name}</span>
                <span className="ship-count">
                  {gameState.player1_ships.filter(s => !s.is_destroyed).length} ships
                </span>
              </div>
              <div className="player-status player2">
                <span className="player-name">{player2Name}</span>
                <span className="ship-count">
                  {gameState.player2_ships.filter(s => !s.is_destroyed).length} ships
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="battle-canvas">
        <Canvas
          camera={{
            position: [cameraDistance, cameraDistance * 0.6, cameraDistance],
            fov: 50,
            near: 0.1,
            far: 300,
          }}
          style={{ background: 'linear-gradient(180deg, #000510 0%, #0a1525 50%, #051020 100%)' }}
        >
          {gameState ? (
            <BattleScene
              gameState={gameState}
              currentTurn={currentTurn}
              gridSize={gridSize}
              player1Name={player1Name}
              player2Name={player2Name}
            />
          ) : (
            <>
              <ambientLight intensity={0.3} />
              <Stars radius={100} depth={50} count={3000} factor={4} saturation={0} fade speed={1} />
              <Text position={[0, 0, 0]} fontSize={1} color="#4488ff" anchorX="center">
                Fleet Commander
              </Text>
              <Text position={[0, -1.5, 0]} fontSize={0.4} color="#88aacc" anchorX="center">
                Start a new game or load a replay
              </Text>
              <OrbitControls enableRotate autoRotate autoRotateSpeed={0.5} />
            </>
          )}
        </Canvas>
      </div>

      <style>{`
        .fleet-commander-view {
          display: flex;
          height: calc(100vh - 120px);
          gap: 20px;
          padding: 20px;
        }

        .control-panel {
          width: 300px;
          display: flex;
          flex-direction: column;
          gap: 15px;
          background: rgba(10, 20, 40, 0.8);
          border-radius: 10px;
          padding: 15px;
          border: 1px solid #234;
        }

        .control-panel h2 {
          margin: 0;
          color: #4488ff;
          text-align: center;
          border-bottom: 1px solid #234;
          padding-bottom: 10px;
        }

        .control-panel h3 {
          margin: 0 0 8px 0;
          color: #88aacc;
          font-size: 14px;
        }

        .mode-buttons button {
          width: 100%;
          padding: 12px;
          background: linear-gradient(135deg, #1a3a5c, #0a2040);
          border: 1px solid #4488ff;
          color: #4488ff;
          border-radius: 5px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .mode-buttons button:hover:not(:disabled) {
          background: linear-gradient(135deg, #2a4a6c, #1a3050);
          box-shadow: 0 0 15px rgba(68, 136, 255, 0.3);
        }

        .mode-buttons button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .mode-buttons button.active {
          background: linear-gradient(135deg, #2a5a8c, #1a4060);
          box-shadow: 0 0 20px rgba(68, 136, 255, 0.5);
        }

        .bot-selection {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px;
          background: rgba(0, 10, 20, 0.5);
          border-radius: 5px;
        }

        .bot-selector {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .bot-selector label {
          font-size: 10px;
          color: #668899;
          text-transform: uppercase;
        }

        .bot-selector select {
          padding: 8px;
          background: rgba(20, 40, 60, 0.8);
          border: 1px solid #345;
          color: #aaccee;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        .bot-selector select:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .vs-label {
          color: #4488ff;
          font-weight: bold;
          font-size: 12px;
          padding-top: 16px;
        }

        .actions-panel {
          background: rgba(0, 10, 20, 0.5);
          border-radius: 5px;
          padding: 10px;
          max-height: 150px;
          overflow: hidden;
        }

        .actions-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          max-height: 120px;
          overflow-y: auto;
        }

        .action-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 8px;
          background: rgba(20, 40, 60, 0.6);
          border-radius: 3px;
          font-size: 11px;
          border-left: 3px solid #456;
        }

        .action-item.fire {
          border-left-color: #ff6644;
        }

        .action-item.fire.hit {
          border-left-color: #ff4400;
          background: rgba(255, 68, 0, 0.15);
        }

        .action-item.move {
          border-left-color: #44ff88;
        }

        .action-item.scan {
          border-left-color: #44aaff;
        }

        .action-item.ability {
          border-left-color: #aa44ff;
        }

        .action-type {
          font-weight: bold;
          color: #aaccee;
          min-width: 50px;
        }

        .action-ship {
          color: #88aacc;
          flex: 1;
        }

        .action-damage {
          color: #ff6644;
          font-weight: bold;
        }

        .action-destroyed {
          color: #ff4400;
          font-weight: bold;
          background: rgba(255, 0, 0, 0.2);
          padding: 2px 6px;
          border-radius: 3px;
          animation: pulse 0.5s ease-in-out infinite alternate;
        }

        @keyframes pulse {
          from { opacity: 0.7; }
          to { opacity: 1; }
        }

        .replay-section {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-height: 0;
        }

        .replay-list {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 5px;
          max-height: 200px;
        }

        .replay-list button {
          display: flex;
          flex-direction: column;
          padding: 8px;
          background: rgba(20, 40, 60, 0.6);
          border: 1px solid #234;
          color: #88aacc;
          border-radius: 5px;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s;
        }

        .replay-list button:hover {
          background: rgba(30, 50, 70, 0.8);
          border-color: #4488ff;
        }

        .replay-list button.selected {
          background: rgba(40, 60, 90, 0.8);
          border-color: #4488ff;
        }

        .replay-players {
          font-weight: bold;
          color: #aaccee;
          font-size: 12px;
        }

        .replay-info {
          font-size: 10px;
          color: #668899;
          margin-top: 2px;
        }

        .no-replays {
          color: #556677;
          font-style: italic;
          text-align: center;
          padding: 20px;
        }

        .replay-controls {
          display: flex;
          align-items: center;
          gap: 5px;
          margin-top: 10px;
          flex-wrap: wrap;
          justify-content: center;
        }

        .replay-controls button {
          padding: 5px 10px;
          background: rgba(20, 40, 60, 0.8);
          border: 1px solid #345;
          color: #88aacc;
          border-radius: 3px;
          cursor: pointer;
          font-size: 12px;
        }

        .replay-controls button:hover {
          background: rgba(30, 50, 70, 0.9);
          border-color: #4488ff;
        }

        .turn-indicator {
          color: #88aacc;
          font-size: 12px;
          padding: 0 10px;
        }

        .game-log {
          max-height: 150px;
          overflow: hidden;
        }

        .log-entries {
          height: 120px;
          overflow-y: auto;
          background: rgba(0, 10, 20, 0.5);
          border-radius: 5px;
          padding: 8px;
        }

        .log-entry {
          font-size: 11px;
          color: #88aacc;
          padding: 2px 0;
          border-bottom: 1px solid rgba(68, 136, 255, 0.1);
        }

        .log-entry:last-child {
          border-bottom: none;
          color: #aaccee;
        }

        .stats-panel {
          background: rgba(0, 10, 20, 0.5);
          border-radius: 5px;
          padding: 10px;
        }

        .fleet-status {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .player-status {
          display: flex;
          justify-content: space-between;
          padding: 5px 10px;
          border-radius: 3px;
        }

        .player-status.player1 {
          background: rgba(68, 136, 255, 0.2);
          border-left: 3px solid #4488ff;
        }

        .player-status.player2 {
          background: rgba(255, 68, 136, 0.2);
          border-left: 3px solid #ff4488;
        }

        .player-name {
          font-weight: bold;
          color: #aaccee;
          font-size: 12px;
        }

        .ship-count {
          color: #88aacc;
          font-size: 12px;
        }

        .battle-canvas {
          flex: 1;
          border-radius: 10px;
          overflow: hidden;
          border: 1px solid #234;
        }
      `}</style>
    </div>
  );
}

export default FleetCommander3DView;
