import { useState, useEffect, useRef } from 'react'
import './TournamentView.css'

interface PlayerStats {
  name: string
  wins: number
  losses: number
  games_played: number
  win_rate: number
  accuracy: number
  total_shots: number
  total_hits: number
}

interface TournamentState {
  name: string
  format: string
  games_per_match: number
  is_running: boolean
  players: string[]
  leaderboard: PlayerStats[]
  total_matches: number
}

interface TournamentEvent {
  type: string
  data: any
}

interface TournamentViewProps {
  tournamentId: string
}

export function TournamentView({ tournamentId }: TournamentViewProps) {
  const [tournament, setTournament] = useState<TournamentState | null>(null)
  const [events, setEvents] = useState<TournamentEvent[]>([])
  const [currentMatch, setCurrentMatch] = useState<{
    player1: string
    player2: string
    match: number
    total: number
  } | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket(`ws://${window.location.host}/ws/tournament/${tournamentId}`)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('Connected to tournament')
    }

    ws.onmessage = (event) => {
      const message: TournamentEvent = JSON.parse(event.data)
      setEvents((prev) => [...prev, message])

      switch (message.type) {
        case 'state':
          setTournament(message.data)
          break
        case 'tournament_start':
          setTournament((prev) =>
            prev ? { ...prev, is_running: true } : prev
          )
          break
        case 'match_start':
          setCurrentMatch({
            player1: message.data.player1,
            player2: message.data.player2,
            match: message.data.match,
            total: message.data.total_matches,
          })
          break
        case 'match_end':
          setTournament((prev) =>
            prev
              ? { ...prev, leaderboard: message.data.leaderboard }
              : prev
          )
          break
        case 'tournament_end':
          setTournament((prev) =>
            prev
              ? {
                  ...prev,
                  is_running: false,
                  leaderboard: message.data.leaderboard,
                }
              : prev
          )
          setCurrentMatch(null)
          break
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      ws.close()
    }
  }, [tournamentId])

  // Also fetch initial state via REST
  useEffect(() => {
    fetch(`/api/tournaments/${tournamentId}`)
      .then((res) => res.json())
      .then(setTournament)
      .catch(console.error)
  }, [tournamentId])

  if (!tournament) {
    return <div className="loading">Loading tournament...</div>
  }

  const winner = !tournament.is_running && tournament.leaderboard[0]

  return (
    <div className="tournament-view">
      <div className="tournament-header">
        <h2>{tournament.name}</h2>
        <div className="tournament-info">
          <span>{tournament.players.length} players</span>
          <span>•</span>
          <span>{tournament.format.replace('_', ' ')}</span>
          <span>•</span>
          <span>Best of {tournament.games_per_match}</span>
        </div>
      </div>

      {tournament.is_running && currentMatch && (
        <div className="current-match">
          <div className="match-progress">
            Match {currentMatch.match} of {currentMatch.total}
          </div>
          <div className="match-players">
            <span className="match-player">{currentMatch.player1}</span>
            <span className="match-vs">VS</span>
            <span className="match-player">{currentMatch.player2}</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${(currentMatch.match / currentMatch.total) * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {winner && !tournament.is_running && (
        <div className="winner-announcement">
          <span className="trophy">🏆</span>
          <h3>Tournament Winner</h3>
          <div className="winner-name">{winner.name}</div>
          <div className="winner-stats">
            {winner.wins} wins • {winner.accuracy.toFixed(1)}% accuracy
          </div>
        </div>
      )}

      <div className="leaderboard">
        <h3>Leaderboard</h3>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Player</th>
              <th>W</th>
              <th>L</th>
              <th>Win Rate</th>
              <th>Accuracy</th>
              <th>Shots</th>
            </tr>
          </thead>
          <tbody>
            {tournament.leaderboard.map((player, index) => (
              <tr
                key={player.name}
                className={index === 0 && !tournament.is_running ? 'winner' : ''}
              >
                <td className="rank">
                  {index === 0 && !tournament.is_running ? '🥇' : index + 1}
                </td>
                <td className="player-name">{player.name}</td>
                <td className="wins">{player.wins}</td>
                <td className="losses">{player.losses}</td>
                <td className="win-rate">
                  {(player.win_rate * 100).toFixed(1)}%
                </td>
                <td className="accuracy">
                  {(player.accuracy * 100).toFixed(1)}%
                </td>
                <td className="shots">{player.total_shots}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="event-log">
        <h4>Event Log</h4>
        <div className="event-list">
          {events.slice(-20).map((evt, i) => (
            <div key={i} className={`event ${evt.type}`}>
              {formatEvent(evt)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatEvent(event: TournamentEvent): string {
  switch (event.type) {
    case 'tournament_start':
      return `Tournament started with ${event.data.players.length} players`
    case 'match_start':
      return `Match ${event.data.match}: ${event.data.player1} vs ${event.data.player2}`
    case 'match_end':
      return `${event.data.winner} wins match ${event.data.match}!`
    case 'tournament_end':
      return `Tournament complete! ${event.data.leaderboard[0].name} is the champion!`
    default:
      return event.type
  }
}
