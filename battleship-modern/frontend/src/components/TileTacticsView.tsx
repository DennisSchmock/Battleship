import { useState } from 'react'
import './TileTacticsView.css'

const API = 'http://localhost:8000'

type BotType = 'random' | 'greedy' | 'blocking'

type GameResult = {
  winner: number | null
  scores: Record<string, number>
  turns: number
  replay_id: string
  final_board: (number | null)[][]
  seed: number
}

const BOT_OPTIONS: { id: BotType; label: string }[] = [
  { id: 'random', label: 'Random' },
  { id: 'greedy', label: 'Greedy' },
  { id: 'blocking', label: 'Blocking' },
]

export function TileTacticsView() {
  const [p1, setP1] = useState<BotType>('greedy')
  const [p2, setP2] = useState<BotType>('blocking')
  const [result, setResult] = useState<GameResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const runGame = async () => {
    setLoading(true)
    setError(null)
    const seed = Math.floor(Math.random() * 1_000_000)
    try {
      const res = await fetch(`${API}/api/tile-tactics/quick-game`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player1_type: p1, player2_type: p2, seed }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
      }
      const data = await res.json()
      setResult({ ...data, seed })
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      setError(`Could not run game. Is the backend running on ${API}?\n${message}`)
    } finally {
      setLoading(false)
    }
  }

  const score = (id: 0 | 1): number => {
    if (!result) return 0
    return result.scores[String(id)] ?? result.scores[id as unknown as string] ?? 0
  }

  return (
    <div className="tile-wrap">
      <h2>Tile Tactics</h2>
      <p className="lede">
        Beginner-friendly agent arena. Two bots place polyominoes on a 7×7 board with limited inventory.
      </p>
      <p className="wip">
        Proof-of-concept: bots and engine are minimal — UI is intentionally lean.
      </p>

      <div className="controls">
        <label>
          Player 0
          <select value={p1} onChange={(e) => setP1(e.target.value as BotType)}>
            {BOT_OPTIONS.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Player 1
          <select value={p2} onChange={(e) => setP2(e.target.value as BotType)}>
            {BOT_OPTIONS.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <button onClick={runGame} disabled={loading}>
          {loading ? 'Running…' : 'Start quick game'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="results">
          <div className="summary">
            <h3>Result</h3>
            <div className="winner">
              {result.winner === null ? 'Draw' : `Player ${result.winner} wins`}
            </div>
            <div className="scores">
              <div className="score p0">
                <div className="label">P0 ({p1})</div>
                <div className="value">{score(0)}</div>
              </div>
              <div className="score p1">
                <div className="label">P1 ({p2})</div>
                <div className="value">{score(1)}</div>
              </div>
            </div>
            <div className="meta">
              {result.turns} turns · seed <code>{result.seed}</code> · replay{' '}
              <code>{result.replay_id.slice(0, 8)}</code>
            </div>
          </div>
          <div
            className="board"
            aria-label="Final board"
            style={{ ['--board-size' as string]: result.final_board.length }}
          >
            {result.final_board.map((row, y) =>
              row.map((c, x) => (
                <div
                  key={`${x}-${y}`}
                  className={`cell ${c === 0 ? 'p0' : c === 1 ? 'p1' : ''}`}
                  title={`(${x}, ${y})`}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
