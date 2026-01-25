import { useState, useEffect, useCallback, useRef } from 'react';
import './FleetCommanderTournament.css';

// ============================================================================
// TYPES
// ============================================================================

interface Participant {
  id: string;
  name: string;
  is_ready: boolean;
  is_internal_bot: boolean;
  internal_bot_type?: string;
}

interface Standing {
  participant_id: string;
  wins: number;
  losses: number;
  draws: number;
  points: number;
  ships_destroyed: number;
  ships_lost: number;
}

interface MatchResult {
  winner_id: string | null;
  loser_id: string | null;
  turns: number;
  winner_ships_remaining: number;
  loser_ships_remaining: number;
  replay_id: string | null;
}

interface Match {
  id: string;
  player1_id: string;
  player2_id: string;
  round_number: number;
  state: string;
  result: MatchResult | null;
  best_of: number;
}

interface Tournament {
  id: string;
  name: string;
  format: string;
  best_of: number;
  max_participants: number;
  state: string;
  participants: Participant[];
  matches: Match[];
  standings: Standing[];
  current_match: Match | null;
  current_round: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = 'http://localhost:8000';

async function fetchTournaments(includeCompleted = false): Promise<Tournament[]> {
  const res = await fetch(`${API_BASE}/api/fleet-commander/tournaments?include_completed=${includeCompleted}`);
  const data = await res.json();
  return data.tournaments;
}

async function fetchTournament(id: string): Promise<Tournament> {
  const res = await fetch(`${API_BASE}/api/fleet-commander/tournaments/${id}`);
  const data = await res.json();
  return data.tournament;
}

async function createTournament(
  name: string,
  format: string,
  bestOf: number,
  includeBots: string[]
): Promise<Tournament> {
  const res = await fetch(`${API_BASE}/api/fleet-commander/tournaments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      format,
      best_of: bestOf,
      include_bots: includeBots,
    }),
  });
  const data = await res.json();
  return data.tournament;
}

async function addBotToTournament(tournamentId: string, botType: string): Promise<Tournament> {
  const res = await fetch(`${API_BASE}/api/fleet-commander/tournaments/${tournamentId}/add-bot?bot_type=${botType}`, {
    method: 'POST',
  });
  const data = await res.json();
  return data.tournament;
}

async function runTournament(tournamentId: string): Promise<void> {
  await fetch(`${API_BASE}/api/fleet-commander/tournaments/${tournamentId}/run`, {
    method: 'POST',
  });
}

async function deleteTournament(tournamentId: string): Promise<void> {
  await fetch(`${API_BASE}/api/fleet-commander/tournaments/${tournamentId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// UI COMPONENTS
// ============================================================================

function TournamentCard({
  tournament,
  onSelect,
  onDelete,
}: {
  tournament: Tournament;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const stateColors: Record<string, string> = {
    lobby: '#ffaa00',
    in_progress: '#00ff88',
    completed: '#4488ff',
    cancelled: '#ff4444',
  };

  return (
    <div className="tournament-card" onClick={onSelect}>
      <div className="tournament-card-header">
        <h3>{tournament.name}</h3>
        <span
          className="tournament-state"
          style={{ backgroundColor: stateColors[tournament.state] || '#888' }}
        >
          {tournament.state.replace('_', ' ')}
        </span>
      </div>

      <div className="tournament-card-info">
        <div>
          <span className="label">Format:</span>
          <span>{tournament.format.replace('_', ' ')}</span>
        </div>
        <div>
          <span className="label">Participants:</span>
          <span>{tournament.participants.length}/{tournament.max_participants}</span>
        </div>
        {tournament.best_of > 1 && (
          <div>
            <span className="label">Best of:</span>
            <span>{tournament.best_of}</span>
          </div>
        )}
      </div>

      <div className="tournament-card-participants">
        {tournament.participants.slice(0, 4).map((p) => (
          <span key={p.id} className="participant-badge">
            {p.name}
          </span>
        ))}
        {tournament.participants.length > 4 && (
          <span className="participant-badge more">
            +{tournament.participants.length - 4}
          </span>
        )}
      </div>

      {tournament.state === 'lobby' && (
        <button
          className="delete-btn"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}

function CreateTournamentModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (tournament: Tournament) => void;
}) {
  const [name, setName] = useState('New Tournament');
  const [format, setFormat] = useState('round_robin');
  const [bestOf, setBestOf] = useState(1);
  const [selectedBots, setSelectedBots] = useState<string[]>([
    'tactical',
    'aggressive',
    'defensive',
    'random',
  ]);

  const availableBots = [
    { id: 'tactical', name: 'Tactical Bot', description: 'Balanced strategy' },
    { id: 'aggressive', name: 'Aggressive Bot', description: 'Maximum firepower' },
    { id: 'defensive', name: 'Defensive Bot', description: 'Survival focused' },
    { id: 'random', name: 'Random Bot', description: 'Baseline' },
  ];

  const toggleBot = (botId: string) => {
    setSelectedBots((prev) =>
      prev.includes(botId) ? prev.filter((b) => b !== botId) : [...prev, botId]
    );
  };

  const handleCreate = async () => {
    const tournament = await createTournament(name, format, bestOf, selectedBots);
    onCreate(tournament);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>Create Tournament</h2>

        <div className="form-group">
          <label>Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Tournament name"
          />
        </div>

        <div className="form-group">
          <label>Format</label>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="round_robin">Round Robin</option>
            <option value="single_elimination">Single Elimination</option>
          </select>
        </div>

        <div className="form-group">
          <label>Best of</label>
          <select value={bestOf} onChange={(e) => setBestOf(Number(e.target.value))}>
            <option value={1}>1 game</option>
            <option value={3}>Best of 3</option>
            <option value={5}>Best of 5</option>
          </select>
        </div>

        <div className="form-group">
          <label>Include Bots</label>
          <div className="bot-selection">
            {availableBots.map((bot) => (
              <label key={bot.id} className="bot-checkbox">
                <input
                  type="checkbox"
                  checked={selectedBots.includes(bot.id)}
                  onChange={() => toggleBot(bot.id)}
                />
                <span className="bot-name">{bot.name}</span>
                <span className="bot-desc">{bot.description}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleCreate}
            disabled={selectedBots.length < 2}
          >
            Create Tournament
          </button>
        </div>
      </div>
    </div>
  );
}

function StandingsTable({
  standings,
  participants,
}: {
  standings: Standing[];
  participants: Participant[];
}) {
  const getParticipantName = (id: string) => {
    return participants.find((p) => p.id === id)?.name || 'Unknown';
  };

  return (
    <div className="standings-table">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Bot</th>
            <th>W</th>
            <th>L</th>
            <th>Pts</th>
            <th>Ships ⚔️</th>
          </tr>
        </thead>
        <tbody>
          {standings.map((s, i) => (
            <tr key={s.participant_id} className={i === 0 ? 'leader' : ''}>
              <td className="rank">
                {i === 0 && '🥇'}
                {i === 1 && '🥈'}
                {i === 2 && '🥉'}
                {i > 2 && i + 1}
              </td>
              <td className="name">{getParticipantName(s.participant_id)}</td>
              <td className="wins">{s.wins}</td>
              <td className="losses">{s.losses}</td>
              <td className="points">{s.points}</td>
              <td className="ships">{s.ships_destroyed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MatchList({
  matches,
  participants,
  currentMatchId,
  tournamentCompleted,
}: {
  matches: Match[];
  participants: Participant[];
  currentMatchId?: string;
  tournamentCompleted: boolean;
}) {
  const getParticipantName = (id: string) => {
    return participants.find((p) => p.id === id)?.name || 'Unknown';
  };

  return (
    <div className="match-list">
      {matches.map((match) => {
        const isCurrent = match.id === currentMatchId && !tournamentCompleted;
        const isCompleted = match.state === 'completed';
        const winnerId = match.result?.winner_id;

        return (
          <div
            key={match.id}
            className={`match-item ${isCurrent ? 'current' : ''} ${isCompleted ? 'completed' : ''}`}
          >
            <div className="match-players">
              <span className={winnerId === match.player1_id ? 'winner' : ''}>
                {getParticipantName(match.player1_id)}
              </span>
              <span className="vs">vs</span>
              <span className={winnerId === match.player2_id ? 'winner' : ''}>
                {getParticipantName(match.player2_id)}
              </span>
            </div>
            {isCompleted && match.result && (
              <div className="match-result">
                {match.result.turns} turns
              </div>
            )}
            {isCurrent && <span className="live-badge">LIVE</span>}
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// TOURNAMENT DETAIL VIEW
// ============================================================================

function TournamentDetail({
  tournamentId,
  onBack,
}: {
  tournamentId: string;
  onBack: () => void;
}) {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadTournament = useCallback(async () => {
    try {
      const t = await fetchTournament(tournamentId);
      setTournament(t);
      setError(null);
    } catch (e) {
      setError('Failed to load tournament');
    }
  }, [tournamentId]);

  useEffect(() => {
    loadTournament();
  }, [loadTournament]);

  // Poll for updates only when tournament is in progress
  useEffect(() => {
    // Stop polling if tournament is completed or cancelled
    if (tournament?.state === 'completed' || tournament?.state === 'cancelled') {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    // Start polling if not already polling
    if (!pollRef.current) {
      pollRef.current = window.setInterval(() => {
        loadTournament();
      }, 2000);
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [tournament?.state, loadTournament]);

  const handleRun = async () => {
    if (!tournament) return;
    try {
      await runTournament(tournament.id);
      loadTournament();
    } catch (e) {
      setError('Failed to start tournament');
    }
  };

  const handleAddBot = async (botType: string) => {
    if (!tournament) return;
    try {
      await addBotToTournament(tournament.id, botType);
      loadTournament();
    } catch (e) {
      setError('Failed to add bot');
    }
  };

  if (error) {
    return (
      <div className="tournament-detail error">
        <p>{error}</p>
        <button onClick={onBack}>Back</button>
      </div>
    );
  }

  if (!tournament) {
    return <div className="tournament-detail loading">Loading...</div>;
  }

  const isLobby = tournament.state === 'lobby';
  const isRunning = tournament.state === 'in_progress';
  const isCompleted = tournament.state === 'completed';

  return (
    <div className="tournament-detail">
      <header className="tournament-header">
        <button className="back-btn" onClick={onBack}>
          ← Back
        </button>
        <div className="tournament-title">
          <h2>{tournament.name}</h2>
          <span className={`state-badge ${tournament.state}`}>
            {tournament.state.replace('_', ' ')}
          </span>
        </div>
      </header>

      <div className="tournament-content">
        {/* Left: Standings & Matches */}
        <div className="tournament-left">
          <section className="standings-section">
            <h3>Standings</h3>
            <StandingsTable
              standings={tournament.standings}
              participants={tournament.participants}
            />
          </section>

          <section className="matches-section">
            <h3>Matches</h3>
            <MatchList
              matches={tournament.matches}
              participants={tournament.participants}
              currentMatchId={tournament.current_match?.id}
              tournamentCompleted={isCompleted}
            />
          </section>
        </div>

        {/* Right: Live View / Controls */}
        <div className="tournament-right">
          {isLobby && (
            <div className="lobby-controls">
              <h3>Add Bots</h3>
              <div className="bot-buttons">
                {['tactical', 'aggressive', 'defensive', 'random'].map((botType) => {
                  const alreadyAdded = tournament.participants.some(
                    (p) => p.internal_bot_type === botType
                  );
                  return (
                    <button
                      key={botType}
                      onClick={() => handleAddBot(botType)}
                      disabled={alreadyAdded || tournament.participants.length >= tournament.max_participants}
                      className={alreadyAdded ? 'added' : ''}
                    >
                      {alreadyAdded ? '✓' : '+'} {botType}
                    </button>
                  );
                })}
              </div>

              <button
                className="run-btn"
                onClick={handleRun}
                disabled={tournament.participants.length < 2}
              >
                🚀 Start Tournament
              </button>
            </div>
          )}

          {isRunning && tournament.current_match && (
            <div className="live-match">
              <h3>
                Live Match
                <span className="live-indicator">●</span>
              </h3>
              <div className="match-info">
                <span className="player1">
                  {tournament.participants.find((p) => p.id === tournament.current_match?.player1_id)?.name}
                </span>
                <span className="vs">VS</span>
                <span className="player2">
                  {tournament.participants.find((p) => p.id === tournament.current_match?.player2_id)?.name}
                </span>
              </div>
              {/* 3D Mini view would go here */}
            </div>
          )}

          {isCompleted && (
            <div className="winner-display">
              <h3>🏆 Tournament Complete!</h3>
              {tournament.standings[0] && (
                <div className="winner-name">
                  {tournament.participants.find(
                    (p) => p.id === tournament.standings[0].participant_id
                  )?.name}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function FleetCommanderTournament() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedTournamentId, setSelectedTournamentId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTournaments = useCallback(async () => {
    try {
      const list = await fetchTournaments(includeCompleted);
      setTournaments(list);
      setError(null);
    } catch (e) {
      setError('Failed to connect to server. Make sure backend is running.');
    }
  }, [includeCompleted]);

  useEffect(() => {
    loadTournaments();
    const interval = setInterval(loadTournaments, 5000);
    return () => clearInterval(interval);
  }, [loadTournaments]);

  const handleCreate = (tournament: Tournament) => {
    setTournaments((prev) => [tournament, ...prev]);
    setSelectedTournamentId(tournament.id);
  };

  const handleDelete = async (tournamentId: string) => {
    try {
      await deleteTournament(tournamentId);
      setTournaments((prev) => prev.filter((t) => t.id !== tournamentId));
    } catch (e) {
      setError('Failed to delete tournament');
    }
  };

  if (selectedTournamentId) {
    return (
      <TournamentDetail
        tournamentId={selectedTournamentId}
        onBack={() => setSelectedTournamentId(null)}
      />
    );
  }

  return (
    <div className="fleet-tournament-view">
      <header className="tournament-list-header">
        <h2>Fleet Commander Tournaments</h2>
        <div className="header-actions">
          <label className="show-completed">
            <input
              type="checkbox"
              checked={includeCompleted}
              onChange={(e) => setIncludeCompleted(e.target.checked)}
            />
            Show completed
          </label>
          <button className="create-btn" onClick={() => setShowCreateModal(true)}>
            + Create Tournament
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={loadTournaments}>Retry</button>
        </div>
      )}

      {tournaments.length === 0 ? (
        <div className="empty-state">
          <p>No tournaments yet</p>
          <button onClick={() => setShowCreateModal(true)}>Create your first tournament</button>
        </div>
      ) : (
        <div className="tournament-grid">
          {tournaments.map((t) => (
            <TournamentCard
              key={t.id}
              tournament={t}
              onSelect={() => setSelectedTournamentId(t.id)}
              onDelete={() => handleDelete(t.id)}
            />
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreateTournamentModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  );
}
