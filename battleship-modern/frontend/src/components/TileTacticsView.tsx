import { useState } from 'react'
import './TileTacticsView.css'

const API = 'http://localhost:8000'

export function TileTacticsView() {
  const [p1, setP1] = useState('greedy')
  const [p2, setP2] = useState('blocking')
  const [result, setResult] = useState<any>(null)

  const runGame = async () => {
    const res = await fetch(`${API}/api/tile-tactics/quick-game`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player1_type: p1, player2_type: p2, seed: 42 }) })
    setResult(await res.json())
  }

  return <div className='tile-wrap'>
    <h2>Tile Tactics</h2>
    <p>Beginner-friendly agent arena.</p>
    <div>
      <select value={p1} onChange={e => setP1(e.target.value)}><option>random</option><option>greedy</option><option>blocking</option></select>
      <select value={p2} onChange={e => setP2(e.target.value)}><option>random</option><option>greedy</option><option>blocking</option></select>
      <button onClick={runGame}>Start quick game</button>
    </div>
    {result && <>
      <p>Winner: {result.winner === null ? 'Draw' : `Player ${result.winner}`}</p>
      <p>Score P0: {result.scores['0'] ?? result.scores[0]} - P1: {result.scores['1'] ?? result.scores[1]}</p>
      <div className='board'>{result.final_board.map((row: any[], y: number) => row.map((c, x) => <div key={`${x}-${y}`} className={`cell ${c === 0 ? 'p0' : c === 1 ? 'p1' : ''}`}></div>))}</div>
    </>}
  </div>
}
