import { useState, useRef, useCallback } from 'react'
import { GameBoard } from './GameBoard'
import './GameView.css'

interface GameEvent {
  turn: number
  player: string
  action: string
  position: [number, number]
  details?: { ship?: string }
  timestamp: string
}

interface GameState {
  state: string
  turn: number
  current_player: string
  player1: {
    name: string
    board: { grid: string[][]; size: number }
    stats: { shots_fired: number; hits: number; accuracy: number }
  }
  player2: {
    name: string
    board: { grid: string[][]; size: number }
    stats: { shots_fired: number; hits: number; accuracy: number }
  }
  winner: string | null
  events: GameEvent[]
}

const AI_TYPES = [
  { id: 'random', name: 'Random AI' },
  { id: 'hunter', name: 'Hunter AI' },
  { id: 'rl', name: 'RL Agent' },
]

export function GameView() {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [player1Type, setPlayer1Type] = useState('hunter')
  const [player2Type, setPlayer2Type] = useState('random')
  const [events, setEvents] = useState<GameEvent[]>([])
  const [lastShot, setLastShot] = useState<{ row: number; col: number } | null>(null)
  const [speed, setSpeed] = useState(100)
  const [showLog, setShowLog] = useState(true)
  const wsRef = useRef<WebSocket | null>(null)

  const startGame = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/game`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          action: 'start_game',
          player1_type: player1Type,
          player2_type: player2Type,
        })
      )
      setIsPlaying(true)
      setEvents([])
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)

      if (message.type === 'game_start') {
        setGameState(message.data)
      } else if (message.type === 'turn') {
        setGameState(message.data.state)
        const evt = message.data.event as GameEvent
        setEvents((prev) => [...prev.slice(-50), evt]) // Keep last 50
        setLastShot({ row: evt.position[0], col: evt.position[1] })
      } else if (message.type === 'game_end') {
        setIsPlaying(false)
      }
    }

    ws.onerror = () => setIsPlaying(false)
    ws.onclose = () => setIsPlaying(false)
  }, [player1Type, player2Type])

  const getEventIcon = (action: string) => {
    switch (action) {
      case 'hit': return '💥'
      case 'miss': return '·'
      case 'sunk': return '🔥'
      default: return '•'
    }
  }

  return (
    <div className={`game-view ${showLog ? 'with-sidebar' : ''}`}>
      {/* Main content */}
      <div className="game-main">
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
                  <option key={ai.id} value={ai.id}>{ai.name}</option>
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
                  <option key={ai.id} value={ai.id}>{ai.name}</option>
                ))}
              </select>
            </label>
          </div>

          <button
            className="start-button"
            onClick={startGame}
            disabled={isPlaying}
          >
            {isPlaying ? 'Battle in Progress...' : 'Start Battle'}
          </button>

          <div className="speed-control">
            <label>
              Speed
              <input
                type="range"
                min="10"
                max="500"
                step="10"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
              />
              <span className="speed-value">{speed}ms</span>
            </label>
          </div>

          <button
            className="log-toggle"
            onClick={() => setShowLog(!showLog)}
          >
            {showLog ? '◀ Hide Log' : '▶ Show Log'}
          </button>
        </div>

        {gameState ? (
          <div className="game-arena">
            {gameState.winner && (
              <div className="winner-banner">
                🏆 {gameState.winner} Wins! 🏆
              </div>
            )}

            <div className="turn-display">
              Turn {gameState.turn}
            </div>

            <div className="boards-container">
              <div className="board-wrapper">
                <GameBoard
                  grid={gameState.player1.board.grid}
                  size={gameState.player1.board.size}
                  title={gameState.player1.name}
                  lastShot={
                    gameState.current_player === gameState.player2.name
                      ? lastShot
                      : null
                  }
                />
                <div className="player-stats">
                  <span className="stat">
                    <span className="stat-label">Shots</span>
                    <span className="stat-value">{gameState.player1.stats.shots_fired}</span>
                  </span>
                  <span className="stat">
                    <span className="stat-label">Hits</span>
                    <span className="stat-value">{gameState.player1.stats.hits}</span>
                  </span>
                  <span className="stat">
                    <span className="stat-label">Acc</span>
                    <span className="stat-value">{gameState.player1.stats.accuracy}%</span>
                  </span>
                </div>
              </div>

              <div className="vs-divider">⚔️</div>

              <div className="board-wrapper">
                <GameBoard
                  grid={gameState.player2.board.grid}
                  size={gameState.player2.board.size}
                  title={gameState.player2.name}
                  lastShot={
                    gameState.current_player === gameState.player1.name
                      ? lastShot
                      : null
                  }
                />
                <div className="player-stats">
                  <span className="stat">
                    <span className="stat-label">Shots</span>
                    <span className="stat-value">{gameState.player2.stats.shots_fired}</span>
                  </span>
                  <span className="stat">
                    <span className="stat-label">Hits</span>
                    <span className="stat-value">{gameState.player2.stats.hits}</span>
                  </span>
                  <span className="stat">
                    <span className="stat-label">Acc</span>
                    <span className="stat-value">{gameState.player2.stats.accuracy}%</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="game-placeholder">
            <span className="placeholder-icon">⚓</span>
            <p>Select AI players and start a battle!</p>
          </div>
        )}
      </div>

      {/* Collapsible sidebar */}
      {showLog && (
        <aside className="battle-log-sidebar">
          <h4>Battle Log</h4>
          <div className="events-list">
            {events.slice(-30).map((evt, i) => (
              <div key={i} className={`event-item ${evt.action}`}>
                <span className="event-icon">{getEventIcon(evt.action)}</span>
                <span className="event-player">{evt.player.split(' ')[0]}</span>
                <span className="event-action">
                  {evt.action === 'sunk' ? `💀 ${evt.details?.ship}` : evt.action}
                </span>
              </div>
            ))}
          </div>
        </aside>
      )}
    </div>
  )
}
