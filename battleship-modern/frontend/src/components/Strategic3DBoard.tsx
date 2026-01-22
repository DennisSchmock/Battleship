import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Line } from '@react-three/drei';
import * as THREE from 'three';

// Types
interface Ship {
  id: string;
  name: string;
  size?: number;
  health?: number;
  positions: [number, number, number][];
  is_destroyed?: boolean;
}

interface FireResult {
  target: [number, number, number];
  hit: boolean;
  destroyed: string | null;
}

interface MoveResult {
  ship: string;
  success: boolean;
  new_positions: [number, number, number][] | null;
  old_positions?: [number, number, number][];
}

interface ScanResult {
  center: [number, number, number];
  revealed: Record<string, string>;
}

interface TurnData {
  turn: number;
  player: string;
  results: {
    fires: FireResult[];
    moves: MoveResult[];
    scans: ScanResult[];
  };
}

interface Strategic3DBoardProps {
  gridSize: [number, number, number];
  player1Ships: Ship[];
  player2Ships: Ship[];
  player1Name: string;
  player2Name: string;
  currentTurn?: TurnData | null;
  showPlayer1Ships?: boolean;
  showPlayer2Ships?: boolean;
}

// Animated projectile for fire actions
function Projectile({
  start,
  target,
  hit,
  onComplete
}: {
  start: [number, number, number];
  target: [number, number, number];
  hit: boolean;
  onComplete: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [progress, setProgress] = useState(0);
  const [exploding, setExploding] = useState(false);
  const [explosionScale, setExplosionScale] = useState(0);

  useFrame((_, delta) => {
    if (exploding) {
      setExplosionScale(s => {
        const newScale = s + delta * 8;
        if (newScale > 2) {
          onComplete();
        }
        return newScale;
      });
    } else {
      setProgress(p => {
        const newP = p + delta * 3;
        if (newP >= 1) {
          setExploding(true);
          return 1;
        }
        return newP;
      });

      if (meshRef.current) {
        meshRef.current.position.x = start[0] + (target[0] - start[0]) * progress;
        meshRef.current.position.y = start[2] + (target[2] - start[2]) * progress;
        meshRef.current.position.z = start[1] + (target[1] - start[1]) * progress;
      }
    }
  });

  if (exploding) {
    return (
      <mesh position={[target[0], target[2], target[1]]}>
        <sphereGeometry args={[explosionScale * 0.3, 16, 16]} />
        <meshBasicMaterial
          color={hit ? '#ff4400' : '#4488ff'}
          transparent
          opacity={Math.max(0, 1 - explosionScale / 2)}
        />
      </mesh>
    );
  }

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.15, 8, 8]} />
      <meshStandardMaterial
        color={hit ? '#ff6600' : '#66aaff'}
        emissive={hit ? '#ff3300' : '#3388ff'}
        emissiveIntensity={2}
      />
    </mesh>
  );
}

// Scan zone visualization
function ScanZone({
  center,
  onComplete
}: {
  center: [number, number, number];
  onComplete: () => void;
}) {
  const [scale, setScale] = useState(0.1);
  const [opacity, setOpacity] = useState(0.6);

  useFrame((_, delta) => {
    setScale(s => Math.min(s + delta * 4, 3));
    setOpacity(o => {
      const newO = o - delta * 0.8;
      if (newO <= 0) onComplete();
      return Math.max(0, newO);
    });
  });

  return (
    <mesh position={[center[0], center[2], center[1]]}>
      <boxGeometry args={[scale, scale, scale]} />
      <meshBasicMaterial
        color="#00ff88"
        transparent
        opacity={opacity}
        wireframe
      />
    </mesh>
  );
}

// Ship mesh with health visualization
function ShipMesh({
  ship,
  color,
  isEnemy,
  offset
}: {
  ship: Ship;
  color: string;
  isEnemy: boolean;
  offset: [number, number, number];
}) {
  const meshRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);

  // Pulse effect for damaged ships
  useFrame((state) => {
    if (meshRef.current && ship.health && ship.size && ship.health < ship.size) {
      const damage = 1 - ship.health / ship.size;
      meshRef.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 3) * 0.05 * damage);
    }
  });

  if (ship.is_destroyed) {
    // Show destroyed ship as debris
    return (
      <group ref={meshRef}>
        {ship.positions.map((pos, i) => (
          <mesh
            key={i}
            position={[pos[0] + offset[0], pos[2] + offset[2], pos[1] + offset[1]]}
          >
            <boxGeometry args={[0.4, 0.4, 0.4]} />
            <meshStandardMaterial
              color="#333333"
              transparent
              opacity={0.5}
            />
          </mesh>
        ))}
      </group>
    );
  }

  const healthRatio = ship.health && ship.size ? ship.health / ship.size : 1;
  const damageColor = new THREE.Color(color).lerp(new THREE.Color('#ff0000'), 1 - healthRatio);

  return (
    <group
      ref={meshRef}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      {ship.positions.map((pos, i) => (
        <mesh
          key={i}
          position={[pos[0] + offset[0], pos[2] + offset[2], pos[1] + offset[1]]}
        >
          <boxGeometry args={[0.85, 0.85, 0.85]} />
          <meshStandardMaterial
            color={isEnemy ? '#888888' : `#${damageColor.getHexString()}`}
            emissive={hovered ? color : '#000000'}
            emissiveIntensity={hovered ? 0.3 : 0}
            transparent={isEnemy}
            opacity={isEnemy ? 0.3 : 0.9}
          />
        </mesh>
      ))}
      {/* Ship connector lines */}
      {ship.positions.length > 1 && (
        <Line
          points={ship.positions.map(p => [p[0] + offset[0], p[2] + offset[2], p[1] + offset[1]] as [number, number, number])}
          color={color}
          lineWidth={2}
          opacity={isEnemy ? 0.2 : 0.8}
          transparent
        />
      )}
      {/* Ship name label */}
      {hovered && ship.positions.length > 0 && (
        <Text
          position={[
            ship.positions[0][0] + offset[0],
            ship.positions[0][2] + offset[2] + 1.5,
            ship.positions[0][1] + offset[1]
          ]}
          fontSize={0.4}
          color={color}
          anchorX="center"
          anchorY="middle"
        >
          {ship.name} ({ship.health}/{ship.size})
        </Text>
      )}
    </group>
  );
}

// Grid boundaries
function GridBoundary({ size }: { size: [number, number, number] }) {
  const [x, y, z] = size;
  const halfX = x / 2;
  const halfY = y / 2;
  const halfZ = z / 2;

  // Create edge lines for the grid boundary
  const edges = useMemo(() => {
    const lines: [number, number, number][][] = [];

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
  }, [halfX, halfY, halfZ]);

  return (
    <group>
      {edges.map((edge, i) => (
        <Line
          key={i}
          points={edge}
          color="#334455"
          lineWidth={1}
          opacity={0.5}
          transparent
        />
      ))}
    </group>
  );
}

// Hit/Miss markers
function HitMarker({
  position,
  isHit
}: {
  position: [number, number, number];
  isHit: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current && isHit) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 2;
    }
  });

  return (
    <mesh ref={meshRef} position={[position[0], position[2], position[1]]}>
      {isHit ? (
        <>
          <octahedronGeometry args={[0.3]} />
          <meshStandardMaterial
            color="#ff4400"
            emissive="#ff2200"
            emissiveIntensity={0.5}
          />
        </>
      ) : (
        <>
          <sphereGeometry args={[0.15, 8, 8]} />
          <meshStandardMaterial
            color="#4466aa"
            transparent
            opacity={0.6}
          />
        </>
      )}
    </mesh>
  );
}

// Main 3D scene
function Scene({
  gridSize,
  player1Ships,
  player2Ships,
  player1Name,
  player2Name,
  currentTurn,
  showPlayer1Ships = true,
  showPlayer2Ships = true,
}: Strategic3DBoardProps) {
  const [projectiles, setProjectiles] = useState<Array<{
    id: number;
    start: [number, number, number];
    target: [number, number, number];
    hit: boolean;
  }>>([]);

  const [scanZones, setScanZones] = useState<Array<{
    id: number;
    center: [number, number, number];
  }>>([]);

  const [hitMarkers, setHitMarkers] = useState<Array<{
    position: [number, number, number];
    isHit: boolean;
  }>>([]);

  const projectileId = useRef(0);
  const scanId = useRef(0);

  // Grid offset to center at origin
  const offset: [number, number, number] = useMemo(() => [
    -gridSize[0] / 2 + 0.5,
    -gridSize[1] / 2 + 0.5,
    -gridSize[2] / 2 + 0.5
  ], [gridSize]);

  // Process turn events
  useEffect(() => {
    if (!currentTurn) return;

    // Spawn projectiles for fire actions
    currentTurn.results.fires.forEach((fire, i) => {
      setTimeout(() => {
        const startPos: [number, number, number] = currentTurn.player === player1Name
          ? [-gridSize[0] / 2 - 2, gridSize[2] / 2, 0]
          : [gridSize[0] / 2 + 2, gridSize[2] / 2, 0];

        setProjectiles(prev => [...prev, {
          id: projectileId.current++,
          start: startPos,
          target: [fire.target[0] + offset[0], fire.target[2] + offset[2], fire.target[1] + offset[1]],
          hit: fire.hit
        }]);
      }, i * 200);
    });

    // Spawn scan zones
    currentTurn.results.scans.forEach((scan, i) => {
      setTimeout(() => {
        setScanZones(prev => [...prev, {
          id: scanId.current++,
          center: [scan.center[0] + offset[0], scan.center[2] + offset[2], scan.center[1] + offset[1]]
        }]);
      }, i * 100);
    });

    // Add hit markers for fires
    const newMarkers = currentTurn.results.fires.map(fire => ({
      position: [fire.target[0] + offset[0], fire.target[2] + offset[2], fire.target[1] + offset[1]] as [number, number, number],
      isHit: fire.hit
    }));

    setTimeout(() => {
      setHitMarkers(prev => [...prev, ...newMarkers].slice(-50)); // Keep last 50 markers
    }, 500);

  }, [currentTurn, player1Name, gridSize, offset]);

  const removeProjectile = (id: number) => {
    setProjectiles(prev => prev.filter(p => p.id !== id));
  };

  const removeScanZone = (id: number) => {
    setScanZones(prev => prev.filter(s => s.id !== id));
  };

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 15, 10]} intensity={1} color="#ffffff" />
      <pointLight position={[-10, -5, -10]} intensity={0.3} color="#4488ff" />
      <pointLight position={[10, -5, -10]} intensity={0.3} color="#ff4488" />

      {/* Grid boundary */}
      <GridBoundary size={gridSize} />

      {/* Floor grid */}
      <gridHelper
        args={[gridSize[0], gridSize[0], '#223344', '#112233']}
        position={[0, -gridSize[2] / 2 - 0.5, 0]}
        rotation={[0, 0, 0]}
      />

      {/* Player 1 ships (blue) */}
      {showPlayer1Ships && player1Ships.map(ship => (
        <ShipMesh
          key={ship.id}
          ship={ship}
          color="#4488ff"
          isEnemy={false}
          offset={offset}
        />
      ))}

      {/* Player 2 ships (red) */}
      {showPlayer2Ships && player2Ships.map(ship => (
        <ShipMesh
          key={ship.id}
          ship={ship}
          color="#ff4488"
          isEnemy={false}
          offset={offset}
        />
      ))}

      {/* Projectiles */}
      {projectiles.map(p => (
        <Projectile
          key={p.id}
          start={p.start}
          target={p.target}
          hit={p.hit}
          onComplete={() => removeProjectile(p.id)}
        />
      ))}

      {/* Scan zones */}
      {scanZones.map(s => (
        <ScanZone
          key={s.id}
          center={s.center}
          onComplete={() => removeScanZone(s.id)}
        />
      ))}

      {/* Hit markers */}
      {hitMarkers.map((marker, i) => (
        <HitMarker key={i} position={marker.position} isHit={marker.isHit} />
      ))}

      {/* Axis labels */}
      <Text position={[gridSize[0] / 2 + 1, 0, 0]} fontSize={0.6} color="#4488ff">
        X
      </Text>
      <Text position={[0, 0, gridSize[1] / 2 + 1]} fontSize={0.6} color="#44ff88">
        Y
      </Text>
      <Text position={[0, gridSize[2] / 2 + 1, 0]} fontSize={0.6} color="#ff4488">
        Z
      </Text>

      {/* Player labels */}
      <Text
        position={[-gridSize[0] / 2 - 2, gridSize[2] / 2 + 1, 0]}
        fontSize={0.5}
        color="#4488ff"
        anchorX="center"
      >
        {player1Name}
      </Text>
      <Text
        position={[gridSize[0] / 2 + 2, gridSize[2] / 2 + 1, 0]}
        fontSize={0.5}
        color="#ff4488"
        anchorX="center"
      >
        {player2Name}
      </Text>

      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={5}
        maxDistance={60}
        autoRotate={false}
        target={[0, 0, 0]}
      />
    </>
  );
}

export function Strategic3DBoard(props: Strategic3DBoardProps) {
  const cameraDistance = Math.max(props.gridSize[0], props.gridSize[1], props.gridSize[2]) * 1.5;

  return (
    <div className="strategic-3d-board">
      <Canvas
        camera={{
          position: [cameraDistance, cameraDistance * 0.8, cameraDistance],
          fov: 50,
          near: 0.1,
          far: 200
        }}
        style={{ background: 'linear-gradient(180deg, #0a0a1a 0%, #1a1a2e 100%)' }}
      >
        <Scene {...props} />
      </Canvas>
    </div>
  );
}

export default Strategic3DBoard;
