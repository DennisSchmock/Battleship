import { useState } from 'react'
import './TournamentSetup.css'

interface PlayerConfig {
  name: string
  type: string
}

interface TournamentSetupProps {
  onStart: (tournamentId: string) => void
}

const AI_TYPES = [
  { id: 'random', name: 'Random AI', description: 'Shoots randomly' },
  { id: 'hunter', name: 'Hunter AI', description: 'Hunts ships systematically' },
  { id: 'rl', name: 'RL Agent', description: 'Reinforcement learning AI' },
]

export function TournamentSetup({ onStart }: TournamentSetupProps) {
  const [tournamentName, setTournamentName] = useState('')
  const [gamesPerMatch, setGamesPerMatch] = useState(3)
  const [players, setPlayers] = useState<PlayerConfig[]>([
    { name: 'Hunter Alpha', type: 'hunter' },
    { name: 'Hunter Beta', type: 'hunter' },
    { name: 'Random Bot', type: 'random' },
  ])
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const addPlayer = () => {
    const types = ['hunter', 'random', 'rl']
    const type = types[players.length % types.length]
    setPlayers([
      ...players,
      { name: `Player ${players.length + 1}`, type },
    ])
  }

  const removePlayer = (index: number) => {
    if (players.length > 2) {
      setPlayers(players.filter((_, i) => i !== index))
    }
  }

  const updatePlayer = (index: number, field: keyof PlayerConfig, value: string) => {
    const updated = [...players]
    updated[index] = { ...updated[index], [field]: value }
    setPlayers(updated)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsCreating(true)

    const name = tournamentName || `Tournament ${Date.now()}`

    try {
      const response = await fetch('/api/tournaments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          format: 'round_robin',
          games_per_match: gamesPerMatch,
          players: players.map((p) => ({
            name: p.name,
            type: p.type,
          })),
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to create tournament')
      }

      const data = await response.json()

      // Start the tournament
      await fetch(`/api/tournaments/${data.tournament_id}/start`, {
        method: 'POST',
      })

      onStart(data.tournament_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setIsCreating(false)
    }
  }

  return (
    <div className="tournament-setup">
      <h2>Create Tournament</h2>

      <form onSubmit={handleSubmit}>
        <div className="form-section">
          <label>
            Tournament Name
            <input
              type="text"
              value={tournamentName}
              onChange={(e) => setTournamentName(e.target.value)}
              placeholder="Enter tournament name..."
            />
          </label>

          <label>
            Games per Match (Best of N)
            <select
              value={gamesPerMatch}
              onChange={(e) => setGamesPerMatch(Number(e.target.value))}
            >
              <option value={1}>Best of 1</option>
              <option value={3}>Best of 3</option>
              <option value={5}>Best of 5</option>
              <option value={7}>Best of 7</option>
            </select>
          </label>
        </div>

        <div className="form-section">
          <div className="section-header">
            <h3>Players</h3>
            <button type="button" className="add-button" onClick={addPlayer}>
              + Add Player
            </button>
          </div>

          <div className="players-list">
            {players.map((player, index) => (
              <div key={index} className="player-row">
                <input
                  type="text"
                  value={player.name}
                  onChange={(e) => updatePlayer(index, 'name', e.target.value)}
                  placeholder="Player name"
                />

                <select
                  value={player.type}
                  onChange={(e) => updatePlayer(index, 'type', e.target.value)}
                >
                  {AI_TYPES.map((ai) => (
                    <option key={ai.id} value={ai.id}>
                      {ai.name}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  className="remove-button"
                  onClick={() => removePlayer(index)}
                  disabled={players.length <= 2}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="tournament-preview">
          <h4>Tournament Preview</h4>
          <p>
            {players.length} players • Round-robin •{' '}
            {(players.length * (players.length - 1)) / 2} matches •{' '}
            {((players.length * (players.length - 1)) / 2) * gamesPerMatch} games
            total
          </p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <button
          type="submit"
          className="submit-button"
          disabled={isCreating || players.length < 2}
        >
          {isCreating ? 'Creating...' : 'Start Tournament'}
        </button>
      </form>

      <div className="ai-info">
        <h4>AI Types</h4>
        <div className="ai-info-grid">
          {AI_TYPES.map((ai) => (
            <div key={ai.id} className="ai-info-card">
              <strong>{ai.name}</strong>
              <p>{ai.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
