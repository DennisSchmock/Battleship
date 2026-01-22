import { useState, useEffect, useRef, useCallback } from 'react';
import { SpaceBoard } from './SpaceBoard';
import './SpaceBoard.css';
import './SpaceGameView.css';

const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000';

interface GameEvent {
  turn: number;
  player: string;
  action: 'hit' | 'miss' | 'sunk';
  position: [number, number, number];
  details?: { ship?: string };
}

interface BoardState {
  size: { x: number; y: number; z: number };
  layers: string[][][];
  total_cells: number;
}

interface PlayerState {
  name: string;
  board: BoardState;
  stats: {
    shots_fired: number;
    hits: number;
    misses: number;
    accuracy: number;
    ships_remaining: number;
  };
}

interface GameState {
  state: 'setup' | 'playing' | 'finished';
  turn: number;
  current_player: string;
  player1: PlayerState;
  player2: PlayerState;
  winner: string | null;
  events: GameEvent[];
}

const AI_TYPES = [
  { id: 'random3d', name: 'Random AI', description: 'Shoots randomly in 3D space' },
  { id: 'hunter3d', name: 'Hunter AI', description: '3D checkerboard + 6-directional hunting' },
  { id: 'smart3d', name: 'Smart Hunter', description: 'Directional tracking + line continuation' },
];

export function SpaceGameView() {
  const [player1Type, setPlayer1Type] = useState('smart3d');
  const [player2Type, setPlayer2Type] = useState('random3d');
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(300);
  const [recentShot, setRecentShot] = useState<[number, number, number] | undefined>();

  const wsRef = useRef<WebSocket | null>(null);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [events, scrollToBottom]);

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/space-game`);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Connected to SpaceBattleship server');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'game_start') {
        setGameState(message.data);
        setEvents([]);
      } else if (message.type === 'turn') {
        setGameState(message.data.state);
        const newEvent = message.data.event as GameEvent;
        setEvents((prev) => [...prev, newEvent]);
        setRecentShot(newEvent.position);
      } else if (message.type === 'game_end') {
        setGameState((prev) => prev ? { ...prev, winner: message.data.winner } : null);
        setIsPlaying(false);
        setRecentShot(undefined);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('Disconnected from server');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const startGame = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
      setTimeout(() => startGame(), 500);
      return;
    }

    setIsPlaying(true);
    setEvents([]);
    setRecentShot(undefined);

    wsRef.current.send(JSON.stringify({
      action: 'start_game',
      player1_type: player1Type,
      player2_type: player2Type,
      delay: speed,
    }));
  }, [player1Type, player2Type, speed, connectWebSocket]);

  const getEventIcon = (action: string) => {
    switch (action) {
      case 'hit': return '💥';
      case 'sunk': return '🔥';
      case 'miss': return '💨';
      default: return '•';
    }
  };

  const formatPosition = (pos: [number, number, number]) => {
    return `(${pos[0]}, ${pos[1]}, ${pos[2]})`;
  };

  return (
    <div className="space-game-view">
      {/* Controls */}
      <div className="game-controls">
        <div className="player-select">
          <label>
            Player 1
            <select
              value={player1Type}
              onChange={(e) => setPlayer1Type(e.target.value)}
              disabled={isPlaying}
            >
              {AI_TYPES.map((ai) => (
                <option key={ai.id} value={ai.id}>
                  {ai.name}
                </option>
              ))}
            </select>
          </label>

          <span className="vs">VS</span>

          <label>
            Player 2
            <select
              value={player2Type}
              onChange={(e) => setPlayer2Type(e.target.value)}
              disabled={isPlaying}
            >
              {AI_TYPES.map((ai) => (
                <option key={ai.id} value={ai.id}>
                  {ai.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          className="start-button"
          onClick={startGame}
          disabled={isPlaying}
        >
          {isPlaying ? 'Battle in Progress...' : 'Launch Battle'}
        </button>

        <div className="speed-control">
          <label>
            Speed: {speed}ms
            <input
              type="range"
              min="50"
              max="1000"
              step="50"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              disabled={isPlaying}
            />
          </label>
        </div>

        <div className="connection-status">
          <span className={`status-dot ${isConnected ? 'connected' : ''}`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      {/* Game Arena */}
      {gameState ? (
        <div className="space-arena">
          {gameState.winner && (
            <div className="winner-banner">
              🏆 {gameState.winner} Wins! 🏆
            </div>
          )}

          <div className="boards-container">
            <SpaceBoard
              playerName={gameState.player1.name}
              board={gameState.player1.board}
              recentShot={gameState.current_player === gameState.player2.name ? recentShot : undefined}
            />

            <div className="vs-divider">
              <div className="turn-indicator">
                Turn {gameState.turn}
              </div>
              <span>⚔️</span>
              <div className="stats-summary">
                <div>{gameState.player1.stats.ships_remaining} ships</div>
                <div>vs</div>
                <div>{gameState.player2.stats.ships_remaining} ships</div>
              </div>
            </div>

            <SpaceBoard
              playerName={gameState.player2.name}
              board={gameState.player2.board}
              recentShot={gameState.current_player === gameState.player1.name ? recentShot : undefined}
            />
          </div>

          {/* Events Log */}
          <div className="events-log">
            <h4>Battle Log</h4>
            <div className="events-list">
              {events.slice(-20).map((event, index) => (
                <div key={index} className={`event-item ${event.action}`}>
                  <span className="event-icon">{getEventIcon(event.action)}</span>
                  <span className="event-player">{event.player}</span>
                  <span className="event-action">
                    {event.action === 'sunk'
                      ? `destroyed ${event.details?.ship}`
                      : event.action}
                  </span>
                  <span className="event-pos">{formatPosition(event.position)}</span>
                </div>
              ))}
              <div ref={eventsEndRef} />
            </div>
          </div>
        </div>
      ) : (
        <div className="game-placeholder">
          <div className="placeholder-content">
            <span className="placeholder-icon">🚀</span>
            <h3>SpaceBattleship Arena</h3>
            <p>12×12×8 3D battlefield with 1,152 cells</p>
            <p>Select your AI combatants and launch the battle!</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default SpaceGameView;
