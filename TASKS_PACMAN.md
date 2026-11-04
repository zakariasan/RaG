# Pac-Man project — TASKS

## PROGRESS (updated 2026-11-04)

| # | Task | Status |
|---|------|--------|
| 2 | Pacgums: placement, eating, score, HUD update | DONE (tested) |
| 3 | Ghost collision, lives, respawn | DONE (tested) |
| 4 | Afraid mode, eat ghost, ghost respawn, blue color, hide eaten | DONE (9/9 tests pass) |
| 5 | Levels, timer, win/lose | IN PROGRESS: only 5a (`config.seed` in `__main__.py`) done. Left: 5b–5f + `self.level = 1` (`game.py:41`) |
| 1 | Config loader | PARTIAL: `#`/`//` comments done. Left: unknown keys ignored, bad value → default + message, no traceback, remove `check_consistency` |
| 6 | Game state machine (Menu → Game → End → Name → Menu, new-game reset) | TODO |
| 7 | Pause menu (+ pause-safe timers for afraid/respawn) | TODO |
| 8 | Highscores JSON (top 10, name input, shown in menu) | TODO |
| 9 | Game Over / Victory / Instructions screens | TODO |
| 10 | Cheat mode (keys) | TODO |
| 11 | `pac-man.py` entry, Makefile, PyInstaller, itch.io | TODO |
| 12 | Lint: type hints, docstrings, flake8, mypy | TODO (do at end) |
| 13 | Tests (pytest) | TODO (optional, not graded) |
| 14 | README + `docs/project_management/` | TODO |

Bugs from section 0 still open: B1, B3, B4, B6, B7, B8, B9, B10, B11, B13, B14–B22.
Fixed: B2 (seed), B5 (comments), B12 (pacgum placement).
Extra found during work:
- Config comment strip shifts JSON error line numbers → replace comment lines with `"\n"` instead of dropping them.
- After game over, "Start Game" resumes with `lives = 0` → task 6 must reset score/lives/level/maze.
- Timers use `pygame.time.get_ticks()` → keep running during pause → fix in task 7.
- State names used in code: `"MENU"`, `"PLAYING"`, `"GaMe 0vER"`, `"VICTORY"` — reuse exactly.

Order of remaining work: **5 → 6 → 9 → 8 → 7 → 10 → 1 → 11 → 12 → 14**.

---

Original snapshot (branch `zak_features`, commit `4025a02`), kept for history:

| Done | Partially done | Not started |
|------|----------------|-------------|
| Maze drawn from generator | Config loader (no comments, crashes on errors) | Eating pacgums / score |
| Pacman moves (arrows) | Main menu (only "Start Game" button works) | Ghost/Pacman collision, lives, respawn |
| 4 ghosts with chase/scatter AI | HUD (values never update) | Frightened mode (super pacgum) |
| Pacgums + super pacgums drawn | Makefile (`run`/`debug` wrong) | Levels, timer, win/lose |
| | | Pause menu, game over / victory screens |
| | | Name input + highscores (json) |
| | | Cheat mode |
| | | `pac-man.py` entry, README, packaging, itch.io, project mgmt docs |

Order below = recommended order. Each task: **what**, **where**, **how**, **done when**.

---

## 0. Bugs / problems found in current code (fix first)

| # | File:line | Problem | Fix |
|---|-----------|---------|-----|
| B1 | `src/__main__.py:13` | `Config.from_json_file` raises `ConfigError` → **traceback** (subject: no traceback ever). | Wrap in `try/except ConfigError as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1)` — or better, see task 1 (clamp + continue). |
| B2 | `src/__main__.py:18` | `seed=42` hardcoded, ignores `config.seed`. | `seed=config.seed` for level 1, random for next levels (task 5). |
| B3 | `src/__main__.py:12` | Accepts 0 args. Subject: **exactly one** argument. | `if len(sys.argv) != 2: print("Usage: python3 pac-man.py config.json"); sys.exit(1)` |
| B4 | `src/__main__.py:24-29` | Game errors not caught (try/except commented out). | Restore try/except + also catch `KeyboardInterrupt`. Call `pygame.quit()` in `finally`. |
| B5 | `src/parser/load_config.py:44` | `json.load` fails on `#` comment lines (mandatory feature). | Strip comment lines before `json.loads` (task 1). |
| B6 | `src/parser/load_config.py:13` | `extra='forbid'` → unknown keys crash. Subject: **unknown keys ignored**. | `extra='ignore'`. |
| B7 | `src/parser/load_config.py:58-61` | Invalid value → whole config rejected. Subject: **clamp to default, log, continue**. | Validate key by key (task 1). |
| B8 | `mazegenerator` | 60x60 maze → `RecursionError` (recursive DFS). Not caught by anything except generic `Exception`. | Clamp `width`/`height` in config (e.g. 5..40), keep try/except around generator. |
| B9 | `mazegenerator/` in repo | Subject: generator must be **another group's package, installed as-is**, re-installed at review. Living as source folder in repo looks like "your own generator". | Install it as dependency (wheel / git URL in `pyproject.toml`), delete folder from repo, keep only `import`. Check with team who gave the package. |
| B10 | `src/logic/game.py:41` | `self.run()` called inside `__init__` — object never finished building, hard to test. | Remove from `__init__`; call `game.run()` from `__main__`. |
| B11 | `src/logic/game.py:39` | Game starts in `"PLAYING"`; SPACE sends to MENU. Subject flow: Menu → Game. | Start in `"MENU"`. Use `ESCAPE`/`P` for pause (task 7). |
| B12 | `src/logic/game.py:136-142` | `for i in range(...)` + `i += 1` does nothing → duplicates skipped → fewer pacgums than config. Also can land on Pacman start cell. | Build list of free cells, `random.sample(free, k)` (task 2). |
| B13 | `src/logic/game.py:92-99` | No WASD. | Add `pygame.K_w/a/s/d` (map dict, task 2). |
| B14 | `src/graphic/pacgums/pacgum.py:14` | `MazeEnv.config` may be `None` → mypy error. | `assert MazeEnv.config is not None`. |
| B15 | `src/graphic/characters/character.py:31-32` | `self.y: int` but becomes float on move → mypy/logic confusion. | Type as `float`. |
| B16 | `src/graphic/characters/pacman.py:10` | Start fallback only tries 3 cells, all could be `15` (closed "42" cell) with other sizes. | BFS from center to nearest cell `!= 15`. |
| B17 | `src/logic/game.py:20` | `minimum_size = (1500, 1000)` → bigger than many laptop screens / reviewer VM. | Lower to e.g. `(800, 600)`. |
| B18 | `Makefile` | `run` passes no config; `debug` uses `pudb main.py` (subject: `pdb`, real entry). `clean` misses `.pytest_cache`, `dist`, `build`. | See task 11. |
| B19 | `main.py` | Leftover `uv init` stub. | Delete; create `pac-man.py` (task 11). |
| B20 | flake8 | `src/__main__.py:4 F401 'pygame' imported but unused`, `W292` missing final newline in `src/__main__.py`, `src/logic/maze_env.py`. | Fix. |
| B21 | everywhere | Many functions without type hints/docstrings (`ghost.py`, widgets, menus, `game.py`). `mypy --disallow-untyped-defs` will fail. | Task 12. |
| B22 | `src/logic/ghosts_move.py` | Empty file. | Delete or use it for ghost AI logic. |

---

## 1. Config loader (mandatory, reviewer WILL edit config during defense)

**Where:** `src/parser/load_config.py`, `setting.json` → rename `config.json`.

**How:**
1. Read file in `with open(...)`, drop comment lines:
   ```python
   lines = [ln for ln in f if not ln.lstrip().startswith(("#", "//"))]
   data = json.loads("".join(lines))
   ```
2. File missing / not JSON / top-level not dict → print clear message, **use all defaults** (or exit cleanly — choose one, document it in README).
3. Per-key validation, not global. Simple way with pydantic: validate each field alone; on error, log + keep default:
   ```python
   clean: dict[str, object] = {}
   for name, field in cls.model_fields.items():
       if name not in data:
           continue
       try:
           cls.__pydantic_validator__.validate_assignment(
               cls.model_construct(), name, data[name])
           clean[name] = data[name]
       except ValidationError as e:
           print(f"[config] '{name}'={data[name]!r} invalid "
                 f"({e.errors()[0]['msg']}), using default {field.default!r}")
   for key in data.keys() - cls.model_fields.keys():
       print(f"[config] unknown key '{key}' ignored")
   return cls(**clean)
   ```
   (Or do it without pydantic: a dict `{key: (type, min, max, default)}` + loop. Easier to explain at defense.)
4. Clamp, don't reject: `width`/`height` 5..40 (see B8), `lives` 1..99, `level_max_time` 10..999, `pacgum` ≤ free cells (clamp at runtime when placing).
5. Add keys you need later: `levels` (≥10 per subject), `frightened_time`, `ghost_respawn_time`, `pacman_speed`, `ghost_speed`, `cheat_mode` (bool).
6. `highscore_filename` default `"highscores.json"`.

**Done when:** config with `# comment`, unknown key, `"lives": -4`, `"width": "abc"`, missing file → game still starts, clear message printed, no traceback.

---

## 2. Pacgums: placement + eating + score

**Where:** `src/logic/game.py` (`set_pacgums`, new `check_pacgum_collision`), `src/graphic/menus/hud_menu.py`.

**How:**
1. Placement (fix B12):
   ```python
   rows, cols = len(self.maze), len(self.maze[0])
   corners = [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]
   forbidden = set(corners) | {self.pacman.current_cell}
   free = [(y, x) for y in range(rows) for x in range(cols)
           if self.maze[y][x] != 15 and (y, x) not in forbidden]
   k = min(self.config.pacgum, len(free))
   self.pacgums = [Pacgum(True, c) for c in corners]
   self.pacgums += [Pacgum(False, c) for c in random.sample(free, k)]
   ```
   Note: pacman must be created **before** `set_pacgums`. Also: subject says pacgums in "most corridors" — option: `pacgum = -1` means fill every free cell.
2. Store pacgums in a dict `{(y, x): Pacgum}` → O(1) lookup.
3. Eating: each frame, after `pacman.move()`:
   ```python
   cell = (round(self.pacman.y), round(self.pacman.x))
   gum = self.pacgums.pop(cell, None)
   if gum:
       self.score += gum.points
       if gum.is_super:
           self.start_frightened()   # task 4
   if not self.pacgums:
       self.level_won()              # task 5
   ```
4. Score lives in `Game` (or a `GameState` dataclass), not in HUD. HUD only displays.
5. HUD update: add `HudMenu.update(score, lives, level, time_left)` that calls `self.score_value.update_text(str(score))` etc.

**Done when:** dots disappear when eaten, score increases by `points_per_pacgum` / `points_per_super_pacgum`, HUD shows it.

---

## 3. Ghost ↔ Pacman collision, lives, respawn

**Where:** `src/logic/game.py`, `src/graphic/characters/character.py` (add `reset()`).

**How:**
1. Collision with float positions:
   ```python
   def collides(a: Character, b: Character) -> bool:
       return abs(a.x - b.x) < 0.5 and abs(a.y - b.y) < 0.5
   ```
2. If ghost normal → `self.lives -= 1` (skip if cheat invincible).
   - `lives == 0` → state `"GAME_OVER"`.
   - else → `pacman.reset()` + all `ghost.reset()` + short "READY" delay (~1.5 s).
3. `Character.reset()`: `current_cell = target_cell = get_start_pos()`, `y, x = current_cell`, `direction = new_direction = NONE`.
4. If ghost frightened → `score += points_per_ghost`, ghost → `EATEN` state (task 4).

**Done when:** touching ghost removes 1 life, pacman back at center, ghosts back at corners; 0 lives → game over screen.

---

## 4. Frightened mode + eaten ghosts

**Where:** `src/graphic/characters/ghost.py`.

**How:**
1. Add ghost state enum in `init.py`: `GhostState.CHASE / SCATTER / FRIGHTENED / EATEN`.
2. `ghost.frighten(duration_ms)`: state=FRIGHTENED, `frightened_until = now + duration`, reverse direction, lower speed (e.g. 0.03), color blue (blink white last 2 s).
3. In `next_direction()`: if FRIGHTENED → pick direction that **maximizes** distance to pacman (same loop, `dist > max_dist`), or random valid direction.
4. Eaten: state=EATEN, not drawn (or only eyes), not colliding, `respawn_at = now + config.ghost_respawn_time`. When time passes → `reset()` to its corner, state CHASE.
5. Timers: use `pygame.time.get_ticks()` like existing `update_mode()`. **Careful with pause**: ticks keep running during pause → store "remaining ms" or keep your own game clock that only advances while PLAYING (recommended: `self.game_time += dt` in `Game`, pass it to ghosts).
6. Optional: points double per ghost in same frightened period (200, 400, 800…).

**Done when:** after super pacgum ghosts turn blue and flee; eating one gives points; it reappears in its corner after N seconds.

---

## 5. Levels, timer, win / lose

**Where:** `src/logic/game.py` (new `load_level(n)`), maybe new `src/logic/level.py`.

**How:**
1. `load_level(n)`:
   ```python
   seed = self.config.seed if n == 1 else random.randint(1, 10**9)
   try:
       gen = MazeGenerator(size=(w, h), seed=seed, perfect=False)
   except Exception as e:      # RecursionError, ValueError, ...
       -> show error screen / back to menu, never crash
   self.maze = gen.maze
   MazeEnv.setup(...)          # recompute cellsize
   recreate pacman, ghosts, pacgums
   self.level_time_left = self.config.level_max_time
   ```
   Note: generator seed `0` = random, and it calls global `random.seed(...)` → affects your own `random` too. Seed with value > 0.
   Note: subject suggests per-level `width`/`height` (array `levels: [{width, height}, ...]`). Optional; at least support `levels` count ≥ 10.
2. Timer: `dt = self.clock.tick(60) / 1000` → `self.level_time_left -= dt` only while PLAYING. Show `int(...)` in HUD.
3. Time up → your choice (document in README): e.g. lose 1 life and restart level, or game over.
4. All pacgums eaten → `level += 1`; if `level > config.levels` → `"VICTORY"` else `load_level(level)`. Keep score + lives.
5. Movement speed: currently per-frame (0.1 cell/frame). OK at fixed 60 fps; better `speed * dt * 60` so it doesn't depend on FPS.

**Done when:** can play 10 levels in a row, level 1 always same maze, others different, timer counts down, HUD level updates.

---

## 6. Game state machine (clean up `Game.run`)

**Where:** `src/logic/game.py`.

States: `MENU → PLAYING ⇄ PAUSED → GAME_OVER / VICTORY → NAME_INPUT → MENU`, plus `HIGHSCORES`, `INSTRUCTIONS`.

**How:**
1. Use an `Enum` for states (no strings).
2. Split loop:
   ```python
   while self.running:
       dt = self.clock.tick(60) / 1000
       self.handle_events()       # dispatch by state
       self.update(dt)            # only logic when PLAYING
       self.draw()                # dispatch by state
       self.window.flip()
   ```
3. Each screen = class with `handle_event(event)`, `draw(surface)` (reuse `MenuWidget`). Game keeps a `self.screens: dict[State, Screen]`.
4. "Start Game" → reset score/lives/level → `load_level(1)` → PLAYING.
5. "Exit" button → `self.running = False`.

**Done when:** full loop Main Menu → game → win/lose → enter name → main menu works without restarting program.

---

## 7. Pause menu

**Where:** new `src/graphic/menus/pause_menu.py`.

**How:** `ESC` or `P` in PLAYING → PAUSED. Draw game frozen + semi-transparent overlay (`Surface` with `set_alpha`) + buttons "Resume", "Main Menu". No `update()` while paused (timer, ghosts, frightened timers frozen — see task 4.5).

---

## 8. Highscores (persistent JSON)

**Where:** new `src/logic/highscores.py`, new menus `highscore_menu.py`, `name_input_menu.py`.

**How:**
1. Class `HighscoreManager(path)`:
   - `load()`: `try: with open(...) as f: data = json.load(f)` → keep only entries where `name` is str matching `^[A-Za-z0-9 ]{1,10}$` and `score` is int ≥ 0. Missing / corrupted file → empty list + log message. Never crash.
   - `add(name, score)`: append, sort desc by score, keep top 10.
   - `save()`: write to temp file then `os.replace` (atomic) in try/except `OSError`.
   - `is_highscore(score)`: `len < 10 or score > lowest`.
2. Load at game start, save at game end (after name entry).
3. Name input screen: handle `pygame.TEXTINPUT` (`event.text`) — accept only `isalnum()` or space, max 10 chars; `BACKSPACE` delete; `ENTER` confirm (empty → "PLAYER").
4. Show top 10 in main menu (subject image shows list directly under title) + "View Highscores" screen.

**Done when:** scores survive restart; delete/corrupt the json → game still runs; name >10 chars or symbols impossible to type.

---

## 9. Game Over / Victory / Instructions screens

**Where:** `src/graphic/menus/`.

- Game Over: "GAME OVER", final score, → name input.
- Victory: congratulation message, final score, → name input.
- Instructions: controls (arrows/WASD, P/ESC pause, cheat keys), rules, points values from config. "Back" button.

---

## 10. Cheat mode

**Where:** `src/logic/game.py` (+ `config.cheat_mode` or toggle key `F1`).

Suggested keys (show list on Instructions screen + "CHEAT ON" in HUD):
| Key | Effect |
|-----|--------|
| `F1` | toggle cheat mode on/off |
| `I` | invincibility (skip life loss in task 3) |
| `N` | skip level (call `level_won()`) |
| `F` | freeze ghosts (skip `ghost.move()`) |
| `L` | +1 life |
| `+` / `-` | pacman speed up / down |
| `T` | +30 s timer |
| `G` | eat all pacgums except one (test win quickly) |

Keys only work when cheat mode on. Make them genuinely useful for reviewer to test each feature fast.

---

## 11. Entry point, Makefile, packaging

**Entry point:** subject: `python3 pac-man.py config.json`.
- Create `pac-man.py` at root: imports `src` main function, wraps all in try/except. (Move `__main__.py` body into `def main() -> int` in e.g. `src/app.py`; both `pac-man.py` and `__main__.py` call it.)
- Rename `setting.json` → `config.json` with `#` comments documenting each key.

**Makefile:**
```make
CONFIG ?= config.json
install:   uv sync
run:       uv run python3 pac-man.py $(CONFIG)
debug:     uv run python3 -m pdb pac-man.py $(CONFIG)
clean:     remove __pycache__ .mypy_cache .pytest_cache build dist *.spec output
lint:      (keep as is)
lint-strict: flake8 . && mypy . --strict
package:   uv run pyinstaller --onefile --name pac-man --add-data "config.json:." pac-man.py
.PHONY: install run debug clean lint lint-strict package
```

**Packaging (Chapter VII):**
1. Add `pyinstaller` as dev dependency.
2. Resource paths: when frozen use `sys._MEIPASS` for bundled files; write highscores next to executable or in user dir (`~/.pacman/highscores.json`) — bundled dir is read-only/temporary.
3. Build Linux (+ Windows if possible), zip with `config.json` + `README.txt` (controls, config).
4. Itch.io: create project, **unlisted/draft**, upload zip (or use `butler push`). Note the link for README.
5. Spec / build script must be at repo root (`pac-man.spec` or `build.sh`).

---

## 12. Code quality (mandatory to pass)

- `make lint` must pass: type hints on **all** functions (`-> None` too), params, widget attributes (`self.font: pygame.font.Font | None`).
- Docstrings (Google style) on every class + function.
- `flake8 .` must pass including `.venv` excluded → add `setup.cfg` / `.flake8` with `exclude = .venv,build,dist`.
- No `assert` for runtime errors that can really happen (asserts disappear with `python -O`); OK for mypy narrowing only.
- Every file open with `with`. No bare `except:`.
- `.gitignore`: add `.pytest_cache`, `build/`, `dist/`, `*.spec` (if generated), `highscores.json`.
- Note about MLX rule: only use pygame features with MLX equivalent (window, image/pixel put, draw, key/mouse hooks, string put, loop). Avoid sound/joystick/fancy transforms. `pygame.Window(resizable=True)` / maximize has no real MLX equivalent — consider fixed window size to be safe; be ready to justify.

---

## 13. Tests (not graded, but use them)

`tests/` with pytest:
- `test_config.py`: comments, unknown keys, bad values clamped, missing file.
- `test_highscores.py`: corrupt file, >10 entries, invalid names, negative score.
- `test_maze.py`: every generated maze (several seeds/sizes) — pacman start cell `!= 15`, all non-15 cells reachable from start (BFS), corners not 15.
- `test_movement.py`: `is_valid_direction` vs wall bits.

---

## 14. Docs

**README.md** (currently empty) — required sections:
1. First line italic: `*This project has been created as part of the 42 curriculum by <login1>, <login2>, <login3>.*`
2. Description
3. Instructions (install, run, make rules)
4. Resources + **how AI was used** (which tasks, which parts)
5. Configuration (each key, type, default, clamp range, comment syntax)
6. Highscore (format, location, why)
7. Maze Generation (which group's package, version, how called, `perfect=False`, wall bits 1=N 2=E 4=S 8=W, 15=closed cell, error handling)
8. Implementation (game loop, state machine, ghost AI, collisions, timers)
9. General Software Architecture (modules/classes diagram)
10. Project Management (link to `docs/project_management/`)
11. Itch.io link + cheat keys

**`docs/project_management/`:** timeline/Gantt or Kanban, progress vs plan, team roles (who did what), risk analysis (e.g. generator crash, packaging, MLX rule), acceptance test plan (feature / steps / expected / result / bugs fixed), blocking points & decisions.

---

## Suggested split (3 people)

| Person | Tasks |
|--------|-------|
| A | 0 (bugs in `__main__`/config), 1, 8, 11 |
| B | 2, 3, 4, 10 |
| C | 5, 6, 7, 9, 13 |
| All | 12, 14 |

## Final checklist before defense
- [ ] `python3 pac-man.py config.json` works; 0 or 2 args → usage message
- [ ] Bad config (comments, unknown key, wrong type, missing file) → no traceback
- [ ] Generator error (e.g. size 100) → clean message
- [ ] 10+ levels, level 1 fixed seed, timer, pause
- [ ] Lives, respawn, frightened, ghost respawn after N s
- [ ] Win + lose → name input → highscore saved → main menu
- [ ] Highscores shown in main menu, file corruption handled
- [ ] Cheat mode lets reviewer test everything in < 2 min
- [ ] `make lint` clean
- [ ] Itch.io build downloads and runs on fresh machine
- [ ] README complete, project management folder present

---
---

# CHANGELOG — what was updated, where, how

Line numbers = state on 2026-11-04.

## Task 2 — Pacgums: placement, eating, score

| File | Where | What changed | How it works |
|------|-------|--------------|--------------|
| `src/logic/game.py` | `__init__` (~l.38-43) | Added `self.score`, `self.lives`, `self.level`, `self.pacgums = {}` | Game owns the numbers. HUD only shows them. |
| `src/logic/game.py` | `set_pacgums()` l.148 | Rewritten | 4 corners → `Pacgum(True)` (super). `bad_places = set(corners) \| {pacman cell}` = cells where a normal gum must NOT go. `free_places` = every cell not `15` (closed) and not bad. `random.sample(free_places, n)` → n unique cells, n clamped with `min()` so no crash. Stored as dict `{(y, x): Pacgum}`. |
| `src/logic/game.py` | `eat_pacgum()` l.172 | New | Pacman cell = `(round(y), round(x))` → `dict.pop(cell)`. Found → `score += points`. Super → `start_evil()`. Dict empty → `level_win()`. |
| `src/logic/game.py` | `run()` l.55-84 | Reordered | Update first (move, eat, collide, HUD values) then draw. Removed double `pacman.move()`. Loop over `self.pacgums.values()` (dict). |
| `src/graphic/menus/hud_menu.py` | `update_values()` l.30 | New | Re-renders a text only when its value changed. `self.level` starts at 1. |

## Task 3 — Ghost collision, lives, respawn

| File | Where | What changed | How it works |
|------|-------|--------------|--------------|
| `src/graphic/characters/character.py` | `reset()` l.111 | New | Back to `get_start_pos()`, `current_cell = target_cell`, direction NONE (Pacman waits for a key). |
| `src/logic/game.py` | `collision()` l.186 | New (static) | Overlap when `abs(dx) < 0.5 and abs(dy) < 0.5`. Positions are floats, ghosts can't pass through Pacman (max 0.15 cell per frame). |
| `src/logic/game.py` | `check_ghost_collision()` l.190 | New | For each ghost touching Pacman → `lose_life()` unless `cheat_mode`. `return` after first hit = max 1 life lost per frame. |
| `src/logic/game.py` | `lose_life()` l.205 | New | `lives -= 1`. 0 → prints, `state = "GaMe 0vER"`. Else → reset Pacman + all ghosts. |
| `src/logic/game.py` | `__init__` | Added `self.cheat_mode = False` | Used as invincibility for now (task 10 will extend). |

## Task 4 — Afraid ghosts, eat ghost, ghost respawn

| File | Where | What changed | How it works |
|------|-------|--------------|--------------|
| `src/parser/load_config.py` | `Config` fields | Added `afraid_time` (7 s), `ghost_pwn_time` (5 s) | Optional keys, defaults if missing. |
| `src/graphic/characters/ghost.py` | `__init__` l.19-23 | Added `normal_speed`, `is_afraid`, `is_eaten`, `afraid_until`, `pwn_time` | After `super().__init__` because `self.speed` is created there. |
| `ghost.py` | `afraid_of(duration)` l.157 | New | Not if eaten. `is_afraid = True`, end time = now + duration, speed 0.03. If between cells: target = cell it came from + opposite direction → ghost turns back smoothly (only flipping direction would teleport it). |
| `ghost.py` | `get_eaten(pwn_at)` l.183 | New | `is_eaten = True`, not afraid, respawn time = now + pwn_at. |
| `ghost.py` | `move()` l.171 | New override | Eaten → wait for respawn time → `reset()`; don't move. Afraid time over → normal + normal speed. Then `Character.move()`. |
| `ghost.py` | `reset()` l.147 | New override | `Character.reset()` + clear afraid/eaten/scatter, speed back, restart scatter timer. |
| `ghost.py` | `next_direction()` l.82 | 2 edits | Afraid → target = Pacman cell. `if is_afraid: dist = -dist` → loop picks the FARTHEST cell = run away. |
| `ghost.py` | `draw()` l.41 | Edited | Eaten → draw nothing. Afraid → blue `(33, 33, 255)`. Else own color. |
| `src/logic/game.py` | `start_evil()` l.216 | Filled | Calls `ghost.afraid_of(afraid_time * 1000)` on all ghosts. |
| `src/logic/game.py` | `check_ghost_collision()` | Extended | Skip eaten ghosts. Afraid ghost touched → `get_eaten()` + `points_per_ghost`, `continue` (can eat 2 at once). Normal ghost → lose life. |

## Task 1 (partial) — Config comments

| File | Where | What changed | How it works |
|------|-------|--------------|--------------|
| `src/parser/load_config.py` | `from_json_file()` ~l.46 | `json.load` → filter lines then `json.loads` | Lines starting with `#` or `//` (after spaces) removed before parsing. |

## Task 5 (started)

| File | Where | What changed | How it works |
|------|-------|--------------|--------------|
| `src/__main__.py` | l.18-20 | `seed=config.seed, perfect=False` | Level 1 maze now comes from config seed, not hardcoded 42. |

---

# ROADMAP — how the game works

## 1. Startup (today)

```
python -m src setting.json
   │
   ├─ src/__main__.py
   │    ├─ Config.from_json_file(path)        src/parser/load_config.py
   │    │     read file → drop # and // lines → json → pydantic validates
   │    ├─ MazeGenerator(size, seed, perfect=False).maze     mazegenerator/
   │    │     → list[list[int]], each cell = wall bits
   │    └─ Game(maze, config)                 src/logic/game.py
   │
   └─ Game.__init__
        ├─ pygame window, surfaces (left 30% HUD, right 70% maze)
        ├─ calculate_dimensions() → cellsize + offsets (maze centered)
        ├─ MazeEnv.setup(...)   shared "global" box: maze, surface,
        │                       offsets, cellsize, config
        ├─ Pacman()  (center)   4 ghosts (one per corner)
        ├─ set_pacgums()        4 super in corners + N normal
        └─ run()                main loop (60 fps)
```

## 2. Maze cell format (from generator)

Each cell is an int, bit = wall present:

```
 1 = North wall    2 = East wall    4 = South wall    8 = West wall
15 = all 4 walls = closed cell (the "42" logo) → nobody goes there
```
`is_valid_direction()` (character.py l.83): can move UP if `not cell & 1`, etc.

## 3. One frame of `run()` (state "PLAYING")

```
check_events()          keys → pacman.new_direction, SPACE → MENU, resize
│
├─ UPDATE
│   pacman.move()               move toward target cell; at cell center
│                               take new_direction if no wall
│   eat_pacgum()                pop gum under pacman → score, super → afraid
│   ghost.move() x4             timers (afraid end / respawn) → AI move
│   check_ghost_collision()     afraid → eat ghost; normal → lose life
│   hud_menu.update_values()    score / lives / level / time
│
├─ DRAW
│   maze_graphic.draw()         walls from bits
│   hud_menu.draw()
│   pacgums, ghosts, pacman
│   blit maze + HUD surfaces on screen
│
└─ window.flip(); clock.tick(60)
```

## 4. Movement model (Pacman and ghosts, character.py)

- Position `y, x` = float, in cells. `current_cell` = last cell reached, `target_cell` = next cell.
- Each frame: add `speed` (Pacman 0.1, ghost 0.05, afraid ghost 0.03) toward target.
- Reached target → `align_with_target()` snaps to it → choose next target:
  - Pacman: `new_direction` from keyboard if no wall, else keep direction.
  - Ghost: `next_direction()` (AI below).

## 5. Ghost AI (ghost.py)

At every cell, ghost looks at open directions (never U-turn), picks the one whose next cell is closest to its **target**:

| Mode | Target |
|------|--------|
| Chase (20 s) | Blinky = Pacman cell. Pinky = 4 cells ahead of Pacman. Inky = 2 cells ahead. Clyde = Pacman if far (>8 cells), else its corner. |
| Scatter (5 s) | its own corner |
| Afraid | Pacman cell, but distance negated → goes **away** |
| Eaten | doesn't move, invisible; after `ghost_pwn_time` → back to corner |

## 6. Game rules state

```
eat gum ───────────► score += 10
eat super gum ─────► score += 50, all ghosts afraid (afraid_time s)
touch afraid ghost ► score += 200, ghost eaten → respawn in corner later
touch normal ghost ► lives -1, all back to start   (cheat_mode: nothing)
lives == 0 ────────► state "GaMe 0vER"   (screen TODO task 9)
all gums eaten ────► level_win()         (next level TODO task 5)
```

## 7. Target flow when all tasks done

```
          ┌──────────────────────────────────────────────┐
          ▼                                              │
     MAIN MENU ──Start──► PLAYING ◄──Resume── PAUSED     │
     │  │  │  │            │  │  └──ESC/P──►   │         │
     │  │  │  Exit         │  │            Main Menu ────┤
     │  │  Instructions    │  │                          │
     │  Highscores         │  all gums eaten             │
     │                     │   → next level (new maze)   │
     │                     │   → last level → VICTORY ─┐ │
     │                     │                           │ │
     │                     lives = 0 → GaMe 0vER ──────┤ │
     │                     time = 0  → lose 1 life     │ │
     │                                                 ▼ │
     │                                         NAME INPUT│
     │                                    save highscores│
     └─────────────────────────────────────────────────────┘
```

## 8. Module map

```
src/
├─ __main__.py              entry: config → maze → Game
├─ parser/load_config.py    Config (pydantic), comments, errors
├─ logic/
│   ├─ game.py              Game: loop, events, rules, levels, states
│   └─ maze_env.py          MazeEnv: shared maze/surface/cellsize/config
└─ graphic/
    ├─ maze_graphic.py      draws walls
    ├─ characters/
    │   ├─ init.py          Direction, Corner enums
    │   ├─ character.py     Character: move, walls, draw, reset
    │   ├─ pacman.py        Pacman: start at center
    │   └─ ghost.py         Ghost: AI, afraid, eaten + Blinky/Pinky/Inky/Clyde
    ├─ pacgums/pacgum.py    Pacgum: normal / super, draw
    ├─ menus/               MenuWidget base, MainMenu, HudMenu
    └─ widgets/             TextWidget, ButtonWidget

To add: logic/highscores.py, menus/pause_menu.py, menus/end_menu.py,
        menus/name_input.py, pac-man.py, config.json, docs/project_management/
```
