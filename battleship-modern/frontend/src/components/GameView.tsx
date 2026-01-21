import { useState, useEffect, useRef, useCallback } from 'react'
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
    stats: { shots_fired: number; hits: number }
  }
  player2: {
    name: string
    board: { grid: string[][]; size: number }
    stats: { shots_fired: number; hits: number }
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
  const [speed, setSpeed] = useState(300)
  const wsRef = useRef<WebSocket | null>(null)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [events])

  const startGame = useCallback(() => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    const ws = new WebSocket(`ws://${window.location.host}/ws/game`)
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
        setEvents((prev) => [...prev, evt])
        setLastShot({ row: evt.position[0], col: evt.position[1] })
      } else if (message.type === 'game_end') {
        setIsPlaying(false)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setIsPlaying(false)
    }

    ws.onclose = () => {
      setIsPlaying(false)
    }
  }, [player1Type, player2Type])

  const getEventIcon = (action: string) => {
    switch (action) {
      case 'hit':
        return '💥'
      case 'miss':
        return '○'
      case 'sunk':
        return '🔥'
      default:
        return '•'
    }
  }

  return (
    <div className="game-view">
      <div className="game-controls">
        <div className="player-select">
          <label>
            Player 1:
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
            Player 2:
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
          {isPlaying ? 'Game in Progress...' : 'Start Game'}
        </button>

        <div className="speed-control">
          <label>
            Speed:
            <input
              type="range"
              min="50"
              max="1000"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            />
            <span>{speed}ms</span>
          </label>
        </div>
      </div>

      {gameState && (
        <div className="game-arena">
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
                <span>Shots: {gameState.player1.stats.shots_fired}</span>
                <span>Hits: {gameState.player1.stats.hits}</span>
              </div>
            </div>

            <div className="vs-divider">
              <span>VS</span>
              <div className="turn-indicator">
                Turn {gameState.turn}
              </div>
            </div>

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
                <span>Shots: {gameState.player2.stats.shots_fired}</span>
                <span>Hits: {gameState.player2.stats.hits}</span>
              </div>
            </div>
          </div>

          {gameState.winner && (
            <div className="winner-banner">
              🏆 {gameState.winner} Wins! 🏆
            </div>
          )}

          <div className="events-log">
            <h4>Battle Log</h4>
            <div className="events-list">
              {events.map((evt, i) => (
                <div key={i} className={`event-item ${evt.action}`}>
                  <span className="event-icon">{getEventIcon(evt.action)}</span>
                  <span className="event-player">{evt.player}</span>
                  <span className="event-action">
                    {evt.action === 'sunk'
                      ? `sunk ${evt.details?.ship}!`
                      : evt.action}
                  </span>
                  <span className="event-pos">
                    ({evt.position[0]}, {evt.position[1]})
                  </span>
                </div>
              ))}
              <div ref={eventsEndRef} />
            </div>
          </div>
        </div>
      )}

      {!gameState && (
        <div className="game-placeholder">
          <p>Select AI players and start a game to watch the battle!</p>
        </div>
      )}
    </div>
  )
}
