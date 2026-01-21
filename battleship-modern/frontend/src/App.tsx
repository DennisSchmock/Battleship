import { useState } from 'react'
import { GameBoard } from './components/GameBoard'
import { TournamentSetup } from './components/TournamentSetup'
import { TournamentView } from './components/TournamentView'
import { GameView } from './components/GameView'
import './App.css'

type View = 'home' | 'tournament-setup' | 'tournament' | 'game'

function App() {
  const [view, setView] = useState<View>('home')
  const [tournamentId, setTournamentId] = useState<string | null>(null)

  const handleStartTournament = (id: string) => {
    setTournamentId(id)
    setView('tournament')
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 onClick={() => setView('home')} style={{ cursor: 'pointer' }}>
          Battleship AI Tournament
        </h1>
        <nav>
          <button
            className={view === 'home' ? 'active' : ''}
            onClick={() => setView('home')}
          >
            Home
          </button>
          <button
            className={view === 'game' ? 'active' : ''}
            onClick={() => setView('game')}
          >
            Watch Game
          </button>
          <button
            className={view === 'tournament-setup' ? 'active' : ''}
            onClick={() => setView('tournament-setup')}
          >
            New Tournament
          </button>
        </nav>
      </header>

      <main className="app-main">
        {view === 'home' && <HomeView onNavigate={setView} />}
        {view === 'game' && <GameView />}
        {view === 'tournament-setup' && (
          <TournamentSetup onStart={handleStartTournament} />
        )}
        {view === 'tournament' && tournamentId && (
          <TournamentView tournamentId={tournamentId} />
        )}
      </main>

      <footer className="app-footer">
        <p>Modern Battleship with Reinforcement Learning</p>
      </footer>
    </div>
  )
}

function HomeView({ onNavigate }: { onNavigate: (view: View) => void }) {
  return (
    <div className="home-view">
      <div className="hero">
        <div className="hero-content">
          <h2>AI vs AI Combat</h2>
          <p>
            Watch intelligent agents battle it out in classic Battleship.
            Featuring reinforcement learning AI that learns to hunt and destroy.
          </p>
        </div>
        <div className="hero-visual">
          <GameBoard
            grid={generateDemoGrid()}
            size={10}
            showShips={false}
            animated={true}
          />
        </div>
      </div>

      <div className="features">
        <div className="feature-card" onClick={() => onNavigate('game')}>
          <h3>Quick Game</h3>
          <p>Watch a single game between two AI players in real-time</p>
          <span className="feature-icon">🎮</span>
        </div>

        <div className="feature-card" onClick={() => onNavigate('tournament-setup')}>
          <h3>Tournament</h3>
          <p>Set up a round-robin tournament with multiple AI types</p>
          <span className="feature-icon">🏆</span>
        </div>

        <div className="feature-card">
          <h3>Train AI</h3>
          <p>Train your own RL agent using deep Q-learning</p>
          <span className="feature-icon">🧠</span>
        </div>
      </div>

      <div className="ai-types">
        <h3>Available AI Players</h3>
        <div className="ai-grid">
          <div className="ai-card">
            <h4>Random AI</h4>
            <p>Shoots randomly. Simple baseline.</p>
            <div className="ai-stats">
              <span>Difficulty: Easy</span>
            </div>
          </div>
          <div className="ai-card">
            <h4>Hunter AI</h4>
            <p>Hunts ships systematically after a hit.</p>
            <div className="ai-stats">
              <span>Difficulty: Medium</span>
            </div>
          </div>
          <div className="ai-card highlight">
            <h4>RL Agent</h4>
            <p>Deep Q-Network trained through self-play.</p>
            <div className="ai-stats">
              <span>Difficulty: Hard</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function generateDemoGrid(): string[][] {
  const grid: string[][] = []
  for (let i = 0; i < 10; i++) {
    const row: string[] = []
    for (let j = 0; j < 10; j++) {
      const rand = Math.random()
      if (rand < 0.1) row.push('hit')
      else if (rand < 0.25) row.push('miss')
      else if (rand < 0.3) row.push('sunk')
      else row.push('empty')
    }
    grid.push(row)
  }
  return grid
}

export default App
