import { useEffect, useState } from 'react'
import './GameBoard.css'

interface GameBoardProps {
  grid: string[][]
  size: number
  showShips?: boolean
  animated?: boolean
  lastShot?: { row: number; col: number } | null
  title?: string
}

export function GameBoard({
  grid,
  size,
  showShips = false,
  animated = false,
  lastShot = null,
  title,
}: GameBoardProps) {
  const [animatedCells, setAnimatedCells] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (animated) {
      // Randomly animate cells for demo effect
      const interval = setInterval(() => {
        const row = Math.floor(Math.random() * size)
        const col = Math.floor(Math.random() * size)
        const key = `${row}-${col}`

        setAnimatedCells((prev) => {
          const next = new Set(prev)
          next.add(key)
          setTimeout(() => {
            setAnimatedCells((p) => {
              const n = new Set(p)
              n.delete(key)
              return n
            })
          }, 500)
          return next
        })
      }, 300)

      return () => clearInterval(interval)
    }
  }, [animated, size])

  const getCellClass = (row: number, col: number): string => {
    const state = grid[row]?.[col] || 'empty'
    const classes = ['cell', state]

    if (lastShot?.row === row && lastShot?.col === col) {
      classes.push('last-shot')
    }

    if (animatedCells.has(`${row}-${col}`)) {
      classes.push('animating')
    }

    return classes.join(' ')
  }

  const getCellContent = (state: string): string => {
    switch (state) {
      case 'hit':
        return '💥'
      case 'miss':
        return '○'
      case 'sunk':
        return '🔥'
      case 'ship':
        return showShips ? '█' : ''
      default:
        return ''
    }
  }

  return (
    <div className="game-board-container">
      {title && <h3 className="board-title">{title}</h3>}
      <div className="game-board" style={{ '--size': size } as React.CSSProperties}>
        {/* Column headers */}
        <div className="header-row">
          <div className="corner"></div>
          {Array.from({ length: size }, (_, i) => (
            <div key={i} className="header-cell">
              {i}
            </div>
          ))}
        </div>

        {/* Grid rows */}
        {Array.from({ length: size }, (_, row) => (
          <div key={row} className="board-row">
            <div className="row-header">{row}</div>
            {Array.from({ length: size }, (_, col) => (
              <div
                key={col}
                className={getCellClass(row, col)}
                data-row={row}
                data-col={col}
              >
                {getCellContent(grid[row]?.[col] || 'empty')}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// Compact version for tournament view
export function CompactBoard({
  grid,
  size = 10,
  playerName,
}: {
  grid: string[][]
  size?: number
  playerName: string
}) {
  return (
    <div className="compact-board">
      <div className="compact-board-header">{playerName}</div>
      <div
        className="compact-grid"
        style={{ '--size': size } as React.CSSProperties}
      >
        {grid.map((row, i) =>
          row.map((cell, j) => (
            <div key={`${i}-${j}`} className={`compact-cell ${cell}`} />
          ))
        )}
      </div>
    </div>
  )
}
