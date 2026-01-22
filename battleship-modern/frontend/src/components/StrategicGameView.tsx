import { useState, useEffect, useRef, useCallback } from 'react';
import './StrategicGameView.css';

const WS_URL = 'ws://localhost:8000';

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
}

interface ScanResult {
  center: [number, number, number];
  revealed: Record<string, string>;
}

interface TurnData {
  turn: number;
  player: string;
  actions: Array<{
    type: string;
    target?: [number, number, number];
    center?: [number, number, number];
    ship_id?: string;
    direction?: string;
  }>;
  results: {
    fires: FireResult[];
    moves: MoveResult[];
    scans: ScanResult[];
  };
  state: {
    player1: { ships: Ship[] };
    player2: { ships: Ship[] };
  };
}

interface GameConfig {
  grid_size: [number, number, number];
  actions_per_turn: number;
}

interface GameStartData {
  config: GameConfig;
  player1: { name: string; ships: Ship[] };
  player2: { name: string; ships: Ship[] };
}

interface GameEndData {
  winner: string;
  turns: number;
  player1_ships_remaining: number;
  player2_ships_remaining: number;
}

const BOT_TYPES = [
  { id: 'random', name: 'Random Bot', description: 'Random actions' },
  { id: 'hunter', name: 'Hunter Bot', description: 'Checkerboard + hunt' },
  { id: 'scout', name: 'Scout Bot', description: 'Scan-heavy recon' },
  { id: 'evasive', name: 'Evasive Bot', description: 'Moves to avoid hits' },
];

export function StrategicGameView() {
  const [player1Type, setPlayer1Type] = useState('hunter');
  const [player2Type, setPlayer2Type] = useState('evasive');
  const [isConnected, setIsConnected] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(200);
  const [useSmallGrid, setUseSmallGrid] = useState(true);

  const [config, setConfig] = useState<GameConfig | null>(null);
  const [player1, setPlayer1] = useState<{ name: string; ships: Ship[] } | null>(null);
  const [player2, setPlayer2] = useState<{ name: string; ships: Ship[] } | null>(null);
  const [turnHistory, setTurnHistory] = useState<TurnData[]>([]);
  const [currentTurn, setCurrentTurn] = useState(0);
  const [winner, setWinner] = useState<string | null>(null);
  const [finalStats, setFinalStats] = useState<{ p1Ships: number; p2Ships: number } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [turnHistory]);

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/strategic-game`);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'game_start') {
        const data = message.data as GameStartData;
        setConfig(data.config);
        setPlayer1({ name: data.player1.name, ships: data.player1.ships });
        setPlayer2({ name: data.player2.name, ships: data.player2.ships });
        setTurnHistory([]);
        setCurrentTurn(0);
        setWinner(null);
        setFinalStats(null);
      } else if (message.type === 'turn') {
        const turnData = message.data as TurnData;
        setTurnHistory((prev) => [...prev, turnData]);
        setCurrentTurn(turnData.turn);
        // Update ship states
        setPlayer1((prev) => prev ? { ...prev, ships: turnData.state.player1.ships } : null);
        setPlayer2((prev) => prev ? { ...prev, ships: turnData.state.player2.ships } : null);
      } else if (message.type === 'game_end') {
        const data = message.data as GameEndData;
        setWinner(data.winner);
        setFinalStats({ p1Ships: data.player1_ships_remaining, p2Ships: data.player2_ships_remaining });
        setIsPlaying(false);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const startGame = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
      setTimeout(() => startGame(), 500);
      return;
    }

    setIsPlaying(true);
    setTurnHistory([]);
    setWinner(null);

    wsRef.current.send(JSON.stringify({
      action: 'start_game',
      player1_type: player1Type,
      player2_type: player2Type,
      delay: speed,
      small_grid: useSmallGrid,
    }));
  }, [player1Type, player2Type, speed, useSmallGrid, connectWebSocket]);

  const getResultIcon = (result: FireResult | MoveResult | ScanResult) => {
    if ('hit' in result) {
      if (result.destroyed) return '💀';
      return result.hit ? '💥' : '💨';
    }
    if ('success' in result) {
      return result.success ? '✓' : '✗';
    }
    return '🔍';
  };

  const formatPos = (pos: [number, number, number]) => `(${pos[0]},${pos[1]},${pos[2]})`;

  const countAliveShips = (ships: Ship[] | undefined) => {
    if (!ships) return 0;
    return ships.filter(s => !s.is_destroyed).length;
  };

  const gridSize = config?.grid_size || [8, 8, 4];
  const totalCells = gridSize[0] * gridSize[1] * gridSize[2];

  return (
    <div className="strategic-game-view">
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
              {BOT_TYPES.map((bot) => (
                <option key={bot.id} value={bot.id}>{bot.name}</option>
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
              {BOT_TYPES.map((bot) => (
                <option key={bot.id} value={bot.id}>{bot.name}</option>
              ))}
            </select>
          </label>
        </div>

        <button className="start-button" onClick={startGame} disabled={isPlaying}>
          {isPlaying ? 'Battle in Progress...' : 'Launch Strategic Battle'}
        </button>

        <div className="options-row">
          <label className="grid-toggle">
            <input
              type="checkbox"
              checked={useSmallGrid}
              onChange={(e) => setUseSmallGrid(e.target.checked)}
              disabled={isPlaying}
            />
            Quick Mode (8×8×4)
          </label>

          <div className="speed-control">
            <label>
              Speed: {speed}ms
              <input
                type="range"
                min="50"
                max="500"
                step="50"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                disabled={isPlaying}
              />
            </label>
          </div>
        </div>

        <div className="connection-status">
          <span className={`status-dot ${isConnected ? 'connected' : ''}`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      {/* Game Arena */}
      {player1 && player2 ? (
        <div className="strategic-arena">
          {winner && (
            <div className="winner-banner">
              🏆 {winner} Wins! 🏆
              {finalStats && (
                <div className="final-stats">
                  Ships remaining: {player1.name} ({finalStats.p1Ships}) vs {player2.name} ({finalStats.p2Ships})
                </div>
              )}
            </div>
          )}

          <div className="game-info">
            <div className="turn-display">Turn {currentTurn}</div>
            <div className="grid-info">{gridSize[0]}×{gridSize[1]}×{gridSize[2]} grid ({totalCells} cells)</div>
          </div>

          <div className="players-status">
            <div className="player-card p1">
              <h3>{player1.name}</h3>
              <div className="ships-list">
                {player1.ships.map((ship) => (
                  <div key={ship.id} className={`ship-status ${ship.is_destroyed ? 'destroyed' : ''}`}>
                    <span className="ship-name">{ship.name}</span>
                    <span className="ship-health">
                      {ship.is_destroyed ? '💀' : `❤️ ${ship.health}/${ship.size}`}
                    </span>
                  </div>
                ))}
              </div>
              <div className="ships-alive">
                {countAliveShips(player1.ships)} ships alive
              </div>
            </div>

            <div className="vs-center">
              <span className="vs-icon">⚔️</span>
              <div className="action-legend">
                <div>🎯 Fire</div>
                <div>🚀 Move</div>
                <div>📡 Scan</div>
              </div>
            </div>

            <div className="player-card p2">
              <h3>{player2.name}</h3>
              <div className="ships-list">
                {player2.ships.map((ship) => (
                  <div key={ship.id} className={`ship-status ${ship.is_destroyed ? 'destroyed' : ''}`}>
                    <span className="ship-name">{ship.name}</span>
                    <span className="ship-health">
                      {ship.is_destroyed ? '💀' : `❤️ ${ship.health}/${ship.size}`}
                    </span>
                  </div>
                ))}
              </div>
              <div className="ships-alive">
                {countAliveShips(player2.ships)} ships alive
              </div>
            </div>
          </div>

          {/* Action Log */}
          <div className="action-log" ref={logRef}>
            <h4>Battle Log (Last 30 actions)</h4>
            <div className="log-entries">
              {turnHistory.slice(-30).map((turn, idx) => (
                <div key={idx} className="turn-entry">
                  <div className="turn-header">
                    <span className="turn-num">T{turn.turn}</span>
                    <span className="turn-player">{turn.player}</span>
                  </div>
                  <div className="turn-actions">
                    {turn.results.fires.map((fire, i) => (
                      <span key={`f${i}`} className={`action-badge ${fire.hit ? 'hit' : 'miss'}`}>
                        {getResultIcon(fire)} {formatPos(fire.target)}
                        {fire.destroyed && ` 💀${fire.destroyed}`}
                      </span>
                    ))}
                    {turn.results.moves.map((move, i) => (
                      <span key={`m${i}`} className={`action-badge ${move.success ? 'success' : 'fail'}`}>
                        🚀 {move.ship.split('_')[0]} {move.success ? '✓' : '✗'}
                      </span>
                    ))}
                    {turn.results.scans.map((scan, i) => (
                      <span key={`s${i}`} className="action-badge scan">
                        📡 {formatPos(scan.center)} ({Object.keys(scan.revealed).length} cells)
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="game-placeholder">
          <div className="placeholder-content">
            <span className="placeholder-icon">🎮</span>
            <h3>Strategic SpaceBattleship v2</h3>
            <p>3 actions per turn: Fire, Move, Scan</p>
            <p>Ships can dodge! Scan to find them!</p>
            <div className="rules-summary">
              <div>🎯 <strong>Fire</strong> - Attack a coordinate</div>
              <div>🚀 <strong>Move</strong> - Move a ship (2 turn cooldown)</div>
              <div>📡 <strong>Scan</strong> - Reveal 3×3×3 area</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StrategicGameView;
