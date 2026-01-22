import { useState, useRef, useCallback } from 'react'
import './MatchView.css'

interface RoundResult {
  round: number
  winner: string
  turns: number
  p1_shots: number
  p1_hits: number
  p1_accuracy: number
  p2_shots: number
  p2_hits: number
  p2_accuracy: number
}

interface Standings {
  p1_wins: number
  p2_wins: number
  rounds_played: number
}

const AI_TYPES = [
  { id: 'random', name: 'Random AI' },
  { id: 'hunter', name: 'Hunter AI' },
  { id: 'adaptive', name: 'Adaptive Hunter' },
  { id: 'rl', name: 'RL Agent' },
]

export function MatchView() {
  const [player1Type, setPlayer1Type] = useState('adaptive')
  const [player2Type, setPlayer2Type] = useState('hunter')
  const [numRounds, setNumRounds] = useState(50)
  const [delay, setDelay] = useState(50)
  const [isRunning, setIsRunning] = useState(false)

  const [player1Name, setPlayer1Name] = useState('')
  const [player2Name, setPlayer2Name] = useState('')
  const [standings, setStandings] = useState<Standings | null>(null)
  const [results, setResults] = useState<RoundResult[]>([])
  const [matchWinner, setMatchWinner] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  const startMatch = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    setResults([])
    setStandings(null)
    setMatchWinner(null)

    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/match`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        action: 'start_match',
        player1_type: player1Type,
        player2_type: player2Type,
        rounds: numRounds,
        delay: delay
      }))
      setIsRunning(true)
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)

      if (message.type === 'match_start') {
        setPlayer1Name(message.data.player1)
        setPlayer2Name(message.data.player2)
      } else if (message.type === 'round_end') {
        setResults(prev => [...prev, message.data.result])
        setStandings(message.data.standings)
      } else if (message.type === 'match_end') {
        setMatchWinner(message.data.winner)
        setIsRunning(false)
      }
    }

    ws.onerror = () => setIsRunning(false)
    ws.onclose = () => setIsRunning(false)
  }, [player1Type, player2Type, numRounds, delay])

  const getWinRate = (wins: number, total: number) => {
    if (total === 0) return 0
    return Math.round((wins / total) * 100)
  }

  return (
    <div className="match-view">
      {/* Controls */}
      <div className="match-controls">
        <div className="player-select">
          <label>
            Player 1
            <select
              value={player1Type}
              onChange={(e) => setPlayer1Type(e.target.value)}
              disabled={isRunning}
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
              disabled={isRunning}
            >
              {AI_TYPES.map((ai) => (
                <option key={ai.id} value={ai.id}>{ai.name}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="match-settings">
          <label>
            Rounds
            <input
              type="number"
              min="1"
              max="100"
              value={numRounds}
              onChange={(e) => setNumRounds(Number(e.target.value))}
              disabled={isRunning}
            />
          </label>

          <label>
            Delay
            <input
              type="range"
              min="0"
              max="500"
              step="10"
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
              disabled={isRunning}
            />
            <span>{delay}ms</span>
          </label>
        </div>

        <button
          className="start-button"
          onClick={startMatch}
          disabled={isRunning}
        >
          {isRunning ? `Round ${standings?.rounds_played || 0}/${numRounds}...` : 'Start Match'}
        </button>
      </div>

      {/* Scoreboard */}
      {standings && (
        <div className="scoreboard">
          <div className={`player-score ${standings.p1_wins > standings.p2_wins ? 'leading' : ''}`}>
            <span className="player-name">{player1Name}</span>
            <span className="wins">{standings.p1_wins}</span>
            <span className="win-rate">{getWinRate(standings.p1_wins, standings.rounds_played)}%</span>
          </div>

          <div className="score-divider">
            <span className="rounds-played">{standings.rounds_played}/{numRounds}</span>
          </div>

          <div className={`player-score ${standings.p2_wins > standings.p1_wins ? 'leading' : ''}`}>
            <span className="wins">{standings.p2_wins}</span>
            <span className="player-name">{player2Name}</span>
            <span className="win-rate">{getWinRate(standings.p2_wins, standings.rounds_played)}%</span>
          </div>
        </div>
      )}

      {/* Winner Banner */}
      {matchWinner && (
        <div className="match-winner">
          🏆 {matchWinner} wins the match! 🏆
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="results-container">
          <table className="results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Winner</th>
                <th>Turns</th>
                <th>{player1Name} Shots</th>
                <th>{player1Name} Acc</th>
                <th>{player2Name} Shots</th>
                <th>{player2Name} Acc</th>
              </tr>
            </thead>
            <tbody>
              {results.slice().reverse().map((r) => (
                <tr key={r.round} className={r.winner === player1Name ? 'p1-win' : 'p2-win'}>
                  <td>{r.round}</td>
                  <td className="winner-cell">{r.winner}</td>
                  <td>{r.turns}</td>
                  <td>{r.p1_shots}</td>
                  <td>{r.p1_accuracy}%</td>
                  <td>{r.p2_shots}</td>
                  <td>{r.p2_accuracy}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Placeholder */}
      {!standings && !isRunning && (
        <div className="match-placeholder">
          <span className="placeholder-icon">🎯</span>
          <h3>Multi-Round Match</h3>
          <p>Select two AI opponents and run {numRounds} rounds to see who dominates!</p>
        </div>
      )}
    </div>
  )
}
