import { useRef, useState, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Box, Sphere } from '@react-three/drei';
import * as THREE from 'three';

interface CellProps {
  position: [number, number, number];
  state: string;
  isRecent?: boolean;
}

function Cell({ position, state, isRecent }: CellProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  // Animate recent shots
  useFrame((_, delta) => {
    if (meshRef.current && isRecent) {
      meshRef.current.rotation.x += delta * 2;
      meshRef.current.rotation.y += delta * 2;
    }
  });

  // Determine color based on state
  const color = useMemo(() => {
    switch (state) {
      case 'hit':
        return '#ff4444';
      case 'sunk':
        return '#ff0000';
      case 'miss':
        return '#4a4a6a';
      case 'ship':
        return '#44ff44';
      default:
        return hovered ? '#4a9eff33' : '#4a9eff11';
    }
  }, [state, hovered]);

  const opacity = state === 'empty' ? 0.1 : 0.8;
  const scale = isRecent ? 1.2 : 1;

  if (state === 'empty' && !hovered) {
    // Show grid lines only for empty cells
    return (
      <Box
        ref={meshRef}
        position={position}
        args={[0.9, 0.9, 0.9]}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <meshBasicMaterial color={color} transparent opacity={0.05} wireframe />
      </Box>
    );
  }

  if (state === 'hit' || state === 'sunk') {
    return (
      <group position={position}>
        <Sphere ref={meshRef} args={[0.4 * scale, 16, 16]}>
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.5}
            transparent
            opacity={opacity}
          />
        </Sphere>
        {isRecent && (
          <Sphere args={[0.6, 8, 8]}>
            <meshBasicMaterial color={color} transparent opacity={0.2} wireframe />
          </Sphere>
        )}
      </group>
    );
  }

  if (state === 'miss') {
    return (
      <Box ref={meshRef} position={position} args={[0.3, 0.3, 0.3]} scale={scale}>
        <meshStandardMaterial color={color} transparent opacity={opacity} />
      </Box>
    );
  }

  // Ship or hovered empty
  return (
    <Box
      ref={meshRef}
      position={position}
      args={[0.8, 0.8, 0.8]}
      scale={scale}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <meshStandardMaterial color={color} transparent opacity={opacity} />
    </Box>
  );
}

interface GridProps {
  size: { x: number; y: number; z: number };
  layers: string[][][];
  recentShot?: [number, number, number];
}

function Grid({ size, layers, recentShot }: GridProps) {
  const cells = useMemo(() => {
    const result: JSX.Element[] = [];
    const offsetX = -size.x / 2;
    const offsetY = -size.y / 2;
    const offsetZ = -size.z / 2;

    for (let x = 0; x < size.x; x++) {
      for (let y = 0; y < size.y; y++) {
        for (let z = 0; z < size.z; z++) {
          const state = layers[z]?.[x]?.[y] || 'empty';
          const isRecent = recentShot &&
            recentShot[0] === x &&
            recentShot[1] === y &&
            recentShot[2] === z;

          // Only render non-empty cells or every 2nd cell for grid visibility
          if (state !== 'empty' || (x + y + z) % 3 === 0) {
            result.push(
              <Cell
                key={`${x}-${y}-${z}`}
                position={[x + offsetX, z + offsetZ, y + offsetY]}
                state={state}
                isRecent={isRecent}
              />
            );
          }
        }
      }
    }
    return result;
  }, [size, layers, recentShot]);

  return <group>{cells}</group>;
}

function AxisLabels({ size }: { size: { x: number; y: number; z: number } }) {
  return (
    <group>
      {/* X axis label */}
      <Text
        position={[size.x / 2 + 1, 0, 0]}
        fontSize={0.5}
        color="#4a9eff"
      >
        X
      </Text>
      {/* Y axis label */}
      <Text
        position={[0, 0, size.y / 2 + 1]}
        fontSize={0.5}
        color="#44ff44"
      >
        Y
      </Text>
      {/* Z axis label */}
      <Text
        position={[0, size.z / 2 + 1, 0]}
        fontSize={0.5}
        color="#ff4444"
      >
        Z
      </Text>
    </group>
  );
}

interface SpaceBoardProps {
  playerName: string;
  board: {
    size: { x: number; y: number; z: number };
    layers: string[][][];
  };
  recentShot?: [number, number, number];
}

export function SpaceBoard({ playerName, board, recentShot }: SpaceBoardProps) {
  return (
    <div className="space-board">
      <h3 className="board-title">{playerName}</h3>
      <div className="canvas-container">
        <Canvas
          camera={{ position: [15, 12, 15], fov: 50 }}
          style={{ background: '#0a0a1a' }}
        >
          <ambientLight intensity={0.3} />
          <pointLight position={[10, 10, 10]} intensity={1} />
          <pointLight position={[-10, -10, -10]} intensity={0.5} color="#4a9eff" />

          <Grid
            size={board.size}
            layers={board.layers}
            recentShot={recentShot}
          />

          <AxisLabels size={board.size} />

          {/* Grid helper */}
          <gridHelper
            args={[board.size.x, board.size.x, '#333', '#222']}
            position={[0, -board.size.z / 2 - 0.5, 0]}
          />

          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            minDistance={5}
            maxDistance={50}
          />
        </Canvas>
      </div>
    </div>
  );
}

export default SpaceBoard;
