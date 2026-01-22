import { useState } from 'react'
import { GameBoard } from './components/GameBoard'
import { TournamentSetup } from './components/TournamentSetup'
import { TournamentView } from './components/TournamentView'
import { GameView } from './components/GameView'
import { SpaceGameView } from './components/SpaceGameView'
import { MatchView } from './components/MatchView'
import { StrategicGameView } from './components/StrategicGameView'
import { FleetCommander3DView } from './components/FleetCommander3DView'
import './App.css'

type View = 'home' | 'tournament-setup' | 'tournament' | 'game' | 'space-game' | 'match' | 'strategic' | 'fleet-commander'

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
          SpaceBattleship AI Tournament
        </h1>
        <nav>
          <button
            className={view === 'home' ? 'active' : ''}
            onClick={() => setView('home')}
          >
            Home
          </button>
          <button
            className={view === 'match' ? 'active' : ''}
            onClick={() => setView('match')}
          >
            Match (50 rounds)
          </button>
          <button
            className={view === 'game' ? 'active' : ''}
            onClick={() => setView('game')}
          >
            Single Game
          </button>
          <button
            className={view === 'space-game' ? 'active' : ''}
            onClick={() => setView('space-game')}
          >
            3D Space
          </button>
          <button
            className={view === 'strategic' ? 'active' : ''}
            onClick={() => setView('strategic')}
          >
            Strategic v2
          </button>
          <button
            className={view === 'fleet-commander' ? 'active' : ''}
            onClick={() => setView('fleet-commander')}
          >
            Fleet Commander
          </button>
        </nav>
      </header>

      <main className="app-main">
        {view === 'home' && <HomeView onNavigate={setView} />}
        {view === 'match' && <MatchView />}
        {view === 'space-game' && <SpaceGameView />}
        {view === 'strategic' && <StrategicGameView />}
        {view === 'fleet-commander' && <FleetCommander3DView />}
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
          <h2>3D Space Combat</h2>
          <p>
            Battle in a 12×12×8 three-dimensional grid with 1,152 cells.
            Watch AI agents navigate 3D space to hunt and destroy enemy fleets.
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
        <div className="feature-card highlight" onClick={() => onNavigate('match')}>
          <h3>50-Round Match</h3>
          <p>Watch AIs battle over 50 rounds - who adapts best?</p>
          <span className="feature-icon">🏆</span>
        </div>

        <div className="feature-card" onClick={() => onNavigate('game')}>
          <h3>Single Game</h3>
          <p>Watch one game turn-by-turn</p>
          <span className="feature-icon">🎮</span>
        </div>

        <div className="feature-card" onClick={() => onNavigate('space-game')}>
          <h3>3D Space Battle</h3>
          <p>Full 3D battlefield (12×12×8)</p>
          <span className="feature-icon">🚀</span>
        </div>

        <div className="feature-card highlight" onClick={() => onNavigate('strategic')}>
          <h3>Strategic v2</h3>
          <p>Fire, Move, Scan - ships can dodge!</p>
          <span className="feature-icon">🎮</span>
        </div>

        <div className="feature-card highlight" onClick={() => onNavigate('fleet-commander')}>
          <h3>Fleet Commander</h3>
          <p>24×24×12 space, 7 ship types, abilities, storm!</p>
          <span className="feature-icon">⚔️</span>
        </div>
      </div>

      <div className="ai-types">
        <h3>Space Fleet AI Players</h3>
        <div className="ai-grid">
          <div className="ai-card">
            <h4>Random AI</h4>
            <p>Shoots randomly in 3D space. Baseline opponent.</p>
            <div className="ai-stats">
              <span>Difficulty: Easy</span>
            </div>
          </div>
          <div className="ai-card">
            <h4>Hunter AI</h4>
            <p>3D checkerboard pattern + 6-directional hunting.</p>
            <div className="ai-stats">
              <span>Difficulty: Medium</span>
            </div>
          </div>
          <div className="ai-card highlight">
            <h4>Adaptive Hunter</h4>
            <p>Learns enemy patterns with heat maps. Adapts across rounds!</p>
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
