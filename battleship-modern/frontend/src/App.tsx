import { useState } from 'react'
import { FleetCommander3DView } from './components/FleetCommander3DView'
import { FleetCommanderTournament } from './components/FleetCommanderTournament'
import { TileTacticsView } from './components/TileTacticsView'
import './App.css'

type View = 'home' | 'fleet-commander' | 'fleet-tournament' | 'tile-tactics'

function App() {
  const [view, setView] = useState<View>('home')

  return (
    <div className="app">
      <header className="app-header">
        <h1 onClick={() => setView('home')} style={{ cursor: 'pointer' }}>
          Fleet Commander
        </h1>
        <nav>
          <button
            className={view === 'home' ? 'active' : ''}
            onClick={() => setView('home')}
          >
            Home
          </button>
          <button
            className={view === 'fleet-commander' ? 'active' : ''}
            onClick={() => setView('fleet-commander')}
          >
            Play
          </button>
          <button
            className={view === 'fleet-tournament' ? 'active' : ''}
            onClick={() => setView('fleet-tournament')}
          >
            Fleet Tournament
          </button>
          <button
            className={view === 'tile-tactics' ? 'active' : ''}
            onClick={() => setView('tile-tactics')}
          >
            Tile Tactics
          </button>
        </nav>
      </header>

      <main className="app-main">
        {view === 'home' && <HomeView onNavigate={setView} />}
        {view === 'fleet-commander' && <FleetCommander3DView />}
        {view === 'fleet-tournament' && <FleetCommanderTournament />}
        {view === 'tile-tactics' && <TileTacticsView />}
      </main>

      <footer className="app-footer">
        <p>Fleet Commander - AI Bot Tournament Platform</p>
      </footer>
    </div>
  )
}

function HomeView({ onNavigate }: { onNavigate: (view: View) => void }) {
  return (
    <div className="home-view">
      <div className="hero">
        <div className="hero-content">
          <h2>Agent Arena</h2>
          <p>
            3D space combat with 7 ship types, unique abilities, and a shrinking storm.
            Build your AI bot and compete in tournaments against other bots.
          </p>
        </div>
      </div>

      <div className="features">
        <div className="feature-card highlight" onClick={() => onNavigate('fleet-commander')}>
          <h3>Watch a Match</h3>
          <p>Watch AI bots battle in a 24x24x12 3D space with abilities and storm mechanics</p>
        </div>

        <div className="feature-card highlight" onClick={() => onNavigate('fleet-tournament')}>
          <h3>Tournament</h3>
          <p>Run a tournament between multiple bots and watch them compete live</p>
        </div>

        <div className="feature-card highlight" onClick={() => onNavigate('tile-tactics')}>
          <h3>Tile Tactics</h3>
          <p>Beginner-friendly agent arena where bots pick legal action IDs</p>
        </div>
      </div>

      <div className="ai-types">
        <h3>Built-in Bots</h3>
        <div className="ai-grid">
          <div className="ai-card">
            <h4>Random Bot</h4>
            <p>Baseline - takes random actions each turn.</p>
            <div className="ai-stats">
              <span>Difficulty: Easy</span>
            </div>
          </div>
          <div className="ai-card">
            <h4>Aggressive Bot</h4>
            <p>Maximum firepower, pushes forward relentlessly.</p>
            <div className="ai-stats">
              <span>Difficulty: Medium</span>
            </div>
          </div>
          <div className="ai-card">
            <h4>Defensive Bot</h4>
            <p>Prioritizes survival with shields and repairs.</p>
            <div className="ai-stats">
              <span>Difficulty: Medium</span>
            </div>
          </div>
          <div className="ai-card highlight">
            <h4>Tactical Bot</h4>
            <p>Uses all ship abilities strategically. The bot to beat.</p>
            <div className="ai-stats">
              <span>Difficulty: Hard</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
