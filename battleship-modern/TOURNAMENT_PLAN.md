# TOURNAMENT_PLAN.md — Fleet Commander Turnering-Klar Refactor

**Oprettet:** 2026-04-20
**Status:** Afventer godkendelse (Fase 0)

---

## 1. Hvad Bliver Fjernet

### Backend — Hele Moduler

| Fil/Mappe | Linjer | Begrundelse |
|-----------|--------|-------------|
| `backend/app/game/board.py` | 142 | Classic 2D Battleship — erstattet af Fleet Commander |
| `backend/app/game/ship.py` | 89 | 2D ship placement — Fleet Commander har sin egen `models.py` |
| `backend/app/game/game.py` | 173 | 2D game controller — ubrugt af Fleet Commander |
| `backend/app/game/player.py` | 200 | 2D AI players — Fleet Commander har egne bots |
| `backend/app/game/adaptive_player.py` | 262 | Pattern-learning AI til 2D — irrelevant |
| `backend/app/game/board3d.py` | 216 | 3D grid (12×12×8) — Fleet Commander har sit eget 3D grid |
| `backend/app/game/ship3d.py` | 118 | 3D ship — erstattet |
| `backend/app/game/game3d.py` | 172 | 3D game controller — erstattet |
| `backend/app/game/player3d.py` | 233 | 3D AI players — erstattet |
| `backend/app/strategic/` (hele mappen) | ~1,526 | Strategic v2 engine + 5 bots — et helt separat spilkoncept |
| `backend/app/ml/` (hele mappen) | ~754 | RL-træning (Gymnasium + DQN) — træner kun 2D/3D, ikke Fleet Commander |
| `backend/app/api/tournament.py` | 255 | Gammel turnerings-klasse — importerer fra `game/` og `ml/`. Fleet Commander har `fleet_commander/tournament.py` |
| `backend/app/game/__init__.py` | ~5 | Package init |
| `backend/app/strategic/__init__.py` | ~5 | Package init |
| `backend/app/ml/__init__.py` | ~5 | Package init |
| `backend/app/api/__init__.py` | ~5 | Package init |

**Samlet fjernet backend:** ~3,965 linjer (~35% af backend)

### Backend — Dele af main.py

`main.py` er 1,895 linjer. Linje 1-675 indeholder:
- Import af `game/`, `game3d/`, `api/tournament` (linje 11-22)
- Pydantic models til classic tournament (linje 56-67)
- `/api/player-types` endpoint (linje 81-91) — gammel 2D AI types
- `/api/tournaments` CRUD (linje 94-178) — gammel turnering
- `/api/quick-game` (linje 180-195) — 2D quick match
- `/ws/tournament/{id}` (linje 197-227) — gammel turnerings-WS
- `/ws/game` (linje 228-293) — 2D single game WS
- `/ws/space-game` (linje 294-356) — 3D space game WS
- `/ws/match` (linje 357-674) — 50-round match WS
- `/api/strategic/bot-types` (linje 503-516) — strategic bot types
- `/ws/strategic-game` (linje 517-674) — strategic game WS

**Alt dette fjernes.** Linje 676+ (Fleet Commander sektion) beholdes og rykkes op.

### Frontend — Komponenter

| Fil | Linjer | Begrundelse |
|-----|--------|-------------|
| `GameBoard.tsx` | 139 | 2D board rendering — bruges i HomeView demo |
| `GameView.tsx` | 260 | 2D single game controller |
| `SpaceGameView.tsx` | 281 | 3D space game view |
| `SpaceBoard.tsx` | 224 | Three.js 3D board (ikke Fleet Commander's) |
| `MatchView.tsx` | 232 | 50-round match viewer (2D) |
| `StrategicGameView.tsx` | 387 | Strategic v2 controller |
| `Strategic3DBoard.tsx` | 558 | Strategic 3D rendering |
| `TournamentSetup.tsx` | 197 | Gammel tournament wizard (til 2D) |
| `TournamentView.tsx` | 231 | Gammel tournament display (til 2D) |

**Samlet fjernet frontend:** ~2,509 linjer (~38% af frontend)

### Frontend — CSS

| Fil | Begrundelse |
|-----|-------------|
| `GameBoard.css` | Hører til fjernet GameBoard |
| `GameView.css` | Hører til fjernet GameView |
| `SpaceBoard.css` | Hører til fjernet SpaceBoard |
| `SpaceGameView.css` | Hører til fjernet SpaceGameView |
| `MatchView.css` | Hører til fjernet MatchView |
| `StrategicGameView.css` | Hører til fjernet StrategicGameView |
| `TournamentSetup.css` | Hører til fjernet TournamentSetup |
| `TournamentView.css` | Hører til fjernet TournamentView |

### Andre Filer

| Fil | Begrundelse |
|-----|-------------|
| `backend/replays/*.json` (113 filer) | Gamle replay-filer fra development — ikke nødvendige i repo |
| `src/` (rod-niveau Java) | Legacy Java Battleship fra ~2010. Ikke relateret til moderne projekt |
| `nbproject/`, `build.xml`, `manifest.mf` | NetBeans Java build filer — legacy |

### Backend Dependencies at Fjerne (requirements.txt)

| Package | Begrundelse |
|---------|-------------|
| `gymnasium>=0.29.0` | Kun brugt af `ml/` |
| `torch>=2.1.0` | Kun brugt af `ml/` |
| `stable-baselines3>=2.2.0` | Kun brugt af `ml/` |
| `numpy>=1.26.0` | Verificér om Fleet Commander bruger det — sandsynligvis ikke |

---

## 2. Hvad Bliver Beholdt (og hvorfor)

### Backend

| Fil/Mappe | Linjer | Hvorfor |
|-----------|--------|---------|
| `backend/app/fleet_commander/engine.py` | 899 | Kernen: game loop, combat, abilities, storm, fog of war |
| `backend/app/fleet_commander/models.py` | 700 | Alle data types, ship configs, actions, game config |
| `backend/app/fleet_commander/bot_interface.py` | 511 | Bot API — `place_fleet()`, `get_actions()`, `on_turn_result()` |
| `backend/app/fleet_commander/websocket_bot.py` | 496 | WebSocket protokol for eksterne bots |
| `backend/app/fleet_commander/tournament.py` | 505 | Fleet Commander turnerings-logik |
| `backend/app/fleet_commander/replay.py` | 296 | Replay recording/playback system |
| `backend/app/fleet_commander/bots/random_bot.py` | 125 | Baseline bot |
| `backend/app/fleet_commander/bots/aggressive_bot.py` | 288 | Aggressiv bot |
| `backend/app/fleet_commander/bots/defensive_bot.py` | 375 | Defensiv bot |
| `backend/app/fleet_commander/bots/tactical_bot.py` | 422 | Mest avanceret bot |
| `backend/app/main.py` | ~1,200 (efter oprydning) | Slanket: kun Fleet Commander endpoints + WS |
| `backend/tests/test_tournament.py` | ~400 | Test suite — opdateres til kun Fleet Commander |

### Frontend

| Fil | Linjer | Hvorfor |
|-----|--------|---------|
| `FleetCommander3DView.tsx` | 1,793 | Hoved-3D view med Three.js rendering |
| `FleetCommanderTournament.tsx` | 875 | Tournament management UI |
| `TournamentMatchViewer.tsx` | 1,156 | Live match viewer med WebSocket |
| `App.tsx` | ~80 (efter oprydning) | Slanket navigation: kun Fleet Commander + Tournament |
| `App.css` | Beholdes | Global styling |
| `FleetCommanderTournament.css` | Beholdes | Tournament styling |
| `TournamentMatchViewer.css` | Beholdes | Match viewer styling |
| `index.css` | Beholdes | Base styling |
| `main.tsx` | 10 | React entry point |

### Scripts & Bots

| Fil | Hvorfor |
|-----|---------|
| `scripts/run_tournament.py` | Tournament launcher — opdateres |
| `example_bot/simple_bot.py` | WebSocket bot template — udvides i Ward 6 |
| `example_bot/requirements.txt` | Bot dependencies |
| `Makefile` | Opdateres: fjern train/gammel test targets |
| `CLAUDE.md` | Opdateres til kun Fleet Commander |
| `README.md` | Skrives om til tournament-fokus |

---

## 3. Ward-Struktur

### Fase 1: Oprydning (én samlet Ward)

**Scope:** Slet alt fra sektion 1, opdatér alt fra sektion 2, verificér end-to-end.

**Tests der skal passe efter oprydning:**
- Eksisterende Fleet Commander tests i `test_tournament.py`
- `npm run lint` i frontend
- Manuel E2E: start backend + frontend, opret tournament, kør match, se resultat

**Commit:** `refactor: remove non-fleet-commander engines, focus repo for tournament`

---

### Fase 2: Turnerings-Features (7 Wards)

#### Ward 1: Deterministisk Seeding

**Mål:** Bit-for-bit reproducerbare matches givet samme seed + input.

**Grænse:** `FleetCommanderGame` + interne bots. Ingen ændring af WebSocket-protokol.

**BDD Tests (skrives først):**
```
Given et nyt spil med seed=42 og to RandomBots
When spillet køres til slut
Then er replay identisk med et andet spil med seed=42 og to RandomBots

Given et spil med seed=42
When bot'en beder om random tal via game.rng
Then er sekvensen deterministisk

Given en bot der bruger global random.random()
When get_actions() kaldes
Then bruges game.rng i stedet (bots modtager rng som argument)
```

**Ændringer:**
- `FleetCommanderGame` får `self.rng = random.Random(seed)`
- Alle `random.random()`/`random.choice()`/etc. i engine.py → `self.rng.*`
- `BotInterface.get_actions()` signatur udvides med `rng: random.Random`
- Alle 4 interne bots opdateres
- `GameConfig` får `seed: Optional[int]` felt
- Storm-spawning, ability-effekter etc. bruger `self.rng`

**Risiko:** Lav — Fleet Commander er allerede isoleret.

---

#### Ward 2: Tidsbudget per Match

**Mål:** Bots har et samlet tidsbudget. Overskridelse = tab af tur.

**Grænse:** Engine + WebSocket protokol. Frontend viser `time_remaining_ms` men ingen ny UI.

**BDD Tests (skrives først):**
```
Given en bot med 60s budget
When den bruger 59s og svarer inden for budget
Then accepteres dens actions

Given en bot der overskrider sit budget
When get_actions() returnerer efter budget er opbrugt
Then ignoreres dens actions for den tur (ingen moves)

Given en WebSocket bot der rapporterer thinking_time_ms=100
When server måler round-trip=500ms
Then trækkes kun 100ms fra budgettet (netværk isoleret)

Given en bot der rapporterer thinking_time_ms=1 men round-trip=5000ms
When server validerer
Then bruges server-side tid (cheat-detection: thinking > round_trip er umuligt,
     men urealistisk lavt ift. round_trip flagges)

Given en GameConfig med match_time_budget_ms=30000
When turneringen startes
Then har begge bots 30s budget
```

**Ændringer:**
- `GameConfig` får `match_time_budget_ms: int = 60_000`
- `PlayerState` får `time_used_ms: int = 0`
- Engine måler tid per `get_actions()` kald
- `get_actions` message udvides med `time_remaining_ms`
- WebSocket protokol: bot svarer med `thinking_time_ms` felt
- Ny `TimeBudgetExceeded` action result type

**Risiko:** Middel — timing i tests kan være flaky. Brug mock-tid i unit tests.

---

#### Ward 3: Scoring med Tid som Faktor

**Mål:** Leaderboard med konfigurerbar scoring inkl. tidsbonus.

**Grænse:** `MatchResult` + `tournament.py`. Minimal frontend-ændring (vis scores).

**BDD Tests (skrives først):**
```
Given en vundet match hvor vinder brugte 20s
When scoring beregnes med default model (win=3, tidsbonus=max(0,30-sek))
Then er vinderens score 3 + 10 = 13 point

Given en vundet match hvor vinder brugte 45s
When scoring beregnes med default model
Then er vinderens score 3 + 0 = 3 point (ingen tidsbonus over 30s)

Given en turnering med scoring_model="win_only"
When matches beregnes
Then tæller kun wins (3 per win, 0 ellers)

Given et leaderboard med to spillere med samme antal wins
When tiebreaker er "time"
Then rangeres den med lavest total tid højest
```

**Ændringer:**
- `MatchResult` udvides med `winner_time_used_ms`, `loser_time_used_ms`
- Ny `ScoringModel` enum/config i tournament
- `FleetCommanderTournament` scorer matches efter config
- Leaderboard-beregning understøtter flere modeller

---

#### Ward 4: Bot-Divisioner

**Mål:** Turneringer kan have divisioner som etikette-system.

**Grænse:** Tournament config + matchmaking. Ingen teknisk håndhævelse.

**BDD Tests (skrives først):**
```
Given en turnering med division="deterministic"
When en participant tilmeldes
Then registreres division-attestering på participant

Given en turnering med division="open"
When matchmaking køres
Then matches bots primært inden for samme division

Given divisioner [deterministic, open]
When leaderboard genereres
Then vises separate leaderboards per division + samlet
```

**Ændringer:**
- Ny `Division` enum: `deterministic`, `open`, `local_llm`, `tiny_model`
- `Participant` får `division: Division` felt
- `FleetCommanderTournament` config får `division: Optional[Division]`
- Matchmaking-logik i `tournament.py` prioriterer same-division

---

#### Ward 5: Fleet Commander Lite

**Mål:** Simpel variant der er overkommelig for små LLM'er.

**Grænse:** Ny `GameConfig.lite()` + eksisterende engine. Ingen ny engine.

**BDD Tests (skrives først):**
```
Given en Lite game config
When config inspiceres
Then har den 3 skibstyper (Destroyer, Cruiser, Support), 16x16x8 grid, ingen storm

Given et Lite spil
When en bot forsøger at bruge abilities
Then er der ingen abilities tilgængelige (kun move og fire)

Given et Lite spil med RandomBot vs RandomBot
When spillet køres til slut
Then terminerer det korrekt med en vinder

Given et Lite spil med TacticalBot vs RandomBot
When 10 spil køres
Then vinder TacticalBot mindst 7/10
```

**Ændringer:**
- `GameConfig` classmethod `lite()` med reducerede settings
- `LITE_SHIP_CONFIGS` subset i `models.py`
- Engine respekterer config (allerede designet til det, men verificér)
- Muligvis reducér ability-system for Lite (ingen abilities = simplere)

---

#### Ward 6: LLM-Bot Reference Wrapper

**Mål:** Template i `example_bot/` der viser hvordan man bygger en LLM-drevet bot.

**Grænse:** Kun `example_bot/` mappen. Ingen engine-ændringer.

**BDD Tests (skrives først):**
```
Given llm_bot_template.py
When den importeres
Then er der ingen syntax errors og alle dependencies er optional

Given en mock LLM der returnerer gyldigt JSON
When bot'en spiller en Lite match
Then parser den korrekt og returnerer gyldige actions

Given en mock LLM der returnerer ugyldigt JSON
When bot'en forsøger at parse
Then retries med fallback og vælger random actions til sidst

Given en bot med 10s remaining budget
When den genererer prompt
Then er prompten kortere end med 60s budget (tids-bevidst)
```

**Ændringer:**
- Ny `example_bot/llm_bot_template.py`
- Dokumentation i filen selv
- Generisk LLM-interface (ingen hardcoded provider)

---

#### Ward 7: Turnerings-Dokumentation

**Mål:** Alt en deltager behøver for at bygge en bot.

**Grænse:** Kun dokumentation. Ingen kode-ændringer.

**Deliverables:**
- `TOURNAMENT_README.md` med:
  - Regler (Lite vs Full)
  - Divisioner
  - Scoring-modeller
  - WebSocket-protokol (inkl. `time_remaining_ms`, `thinking_time_ms`)
  - Trin-for-trin guide til at deltage
  - Links til `/api/fleet-commander/rules` og `example_bot/`
- Opdateret `CLAUDE.md`
- Opdateret `README.md`

**Verifikation:** Giv dokumentationen + rules-endpoint output til en LLM og bed den skrive en bot. Botten skal kunne connecte og spille.

---

## 4. Identificerede Risici

### Oprydnings-risici

| Risiko | Sandsynlighed | Konsekvens | Mitigation |
|--------|---------------|------------|------------|
| **test_tournament.py tester gammel turnering** | Høj | Tests fejler efter sletning | Gennemgå tests, behold kun Fleet Commander-relaterede, slet resten |
| **main.py import-fejl efter sletning** | Høj | Backend starter ikke | Fjern imports + endpoints i én atomisk commit, test umiddelbart |
| **Frontend lint-fejl fra ubrugte imports** | Middel | `npm run lint` fejler | Kør lint efter hver sletning, fix løbende |
| **Replay-filer refererer til gammel game-struktur** | Lav | Replays virker ikke | De 113 replay-filer er alle Fleet Commander — verificér inden sletning |
| **scripts/run_tournament.py bruger gammel API** | Middel | Script fejler | Læs scriptet og opdatér endpoints |

### Feature-risici (Fase 2)

| Risiko | Ward | Sandsynlighed | Mitigation |
|--------|------|---------------|------------|
| **random.Random er ikke thread-safe** | 1 | Lav (single-threaded game loop) | Dokumentér at game loop er single-threaded; brug Lock hvis nødvendigt |
| **Timing-tests er flaky** | 2 | Høj | Mock `time.time()` i tests, brug store marginer |
| **Scoring-balancering er svær at vurdere** | 3 | Middel | Defaults er konservative (3+max30), gør det konfigurérbart |
| **Lite-variant er for simpel/for svær** | 5 | Middel | Test med faktiske bots, justér grid-størrelse og skibstyper |
| **LLM-template kræver netværk i tests** | 6 | Middel | Mock LLM responses, test kun parsing/fallback-logik |

### Arkitektur-noter

- **Fleet Commander har INGEN afhængigheder til de fjernede moduler.** Import-analyse bekræfter at `fleet_commander/` er 100% selvstændig. Oprydningen er kirurgisk ren.
- **`api/tournament.py` vs `fleet_commander/tournament.py`:** Disse er to helt forskellige systemer. Førstnævnte importerer fra `game/` og `ml/` (gammel). Sidstnævnte er Fleet Commander's egen. Vi sletter den gamle.
- **main.py er monolitisk (1,895 linjer).** Efter oprydning reduceres den til ~1,200 linjer. Fremtidig refactor til separate routers (FastAPI `APIRouter`) er oplagt men out-of-scope.
- **Legacy Java-kode i `src/`:** Fuldstændig uafhængig, historisk artefakt. Kan slettes eller ignoreres.

---

## 5. Opdagede Problemer (logges løbende)

*(Tom — vil blive udfyldt under implementation)*

---

## 6. Branch-Strategi

**Forslag:**
1. Commit nuværende ændringer på `claude/fleet-commander-OejNC`
2. Opret ny branch `refactor/tournament-ready` fra `master`
3. Fase 1 (oprydning) som én commit
4. Fase 2: én commit per Ward
