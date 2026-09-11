# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A NetEase **MCStudio** (Minecraft China Edition / 我的世界中国版) map project — the "对战玩法模板" (battle gameplay template), world name `DiamondPillage`. It is not a conventional software project: the repo root *is* the map save directory that MCStudio opens.

Gameplay per `description.txt`: 2+ players spawn in a forest arena split into teams, each team gets two skills (a melee-range skill and a ranged-damage skill), resources spawn periodically at configured points, players craft gear and fight; a victory condition ends the round.

- Project metadata: `studio.json`, `work.mcscfg` (editor/test settings, written by MCStudio — don't hand-edit)
- Add-on namespace: `wihzo` (see `.mcs/settings.json` → `Arena.Component.Namespace`)
- Python **2.7** ModSDK — `print` statements, `iteritems()`, `xrange` are correct here, not legacy mistakes to "fix"

## No build / test / lint

There is no build system, package manager, test suite, or linter. Iteration happens inside the MCStudio editor GUI:

1. Open the project in MCStudio (it targets the `EXPR` server per `studio.json`)
2. Use the editor's run/test button to launch the map — test flags live in `work.mcscfg` (`Test*` keys: cheats on, keep-inventory on, difficulty 2, etc.)
3. Script `logger.info(...)` / `print` output goes to the editor log at `D:\MCStudioDownload\work\editor\edit.log`

Because scripts run inside the game client/server, changes cannot be verified from the shell — say so rather than claiming a change is tested.

## Architecture: eight independent mods, coordinated by events

`behavior_packs/behavior_pack_864FhZqu_7ec35a94/` holds eight sibling script folders, each a self-contained ModSDK mod registered via `@Mod.Binding`:

| Folder | Mod name | Role |
|---|---|---|
| `script_StartLogic` | `StartLogicMod` | Lobby state machine, ready-check, teleport-to-spawn, round restart |
| `script_EndLogic` | `EndLogicMod` | Victory/end conditions, winner announcement, auto-restart |
| `script_Team` | `TeamMod` | Team allocation, scoreboard, friendly-fire suppression, name prefixes |
| `script_Skill` | `SkillMod` | Two skill types: projectile launch and buff application |
| `script_World` | `WorldMod` | Applies game rules, gamemode, difficulty, fixed time at load |
| `script_ResourcePoint` | `ResourcePointConfigMod` | Periodic item spawning in configured areas |
| `script_LimitedRespawn` | `LimitedRespawnMod` | Finite respawn counts; owns the `Editor`/`Alive` component |
| `script_Gomoku` | `GomokuMod` | 五子棋 minigame: auto-builds the board (`/fill` from `config.BoardCenter`/`BoardSize`) on first join, spawns ores/tools in rings around the board, handles right-click piece placement (`ServerBlockUseEvent`, color from TeamMod lookup) and pickaxe-gated ore harvesting, one-use tools (consumed via item component), execution-sword kills (`PlayerAttackEntityEvent`). Piece flow: ore block → piece **item** (`netease_items_beh/` + `netease_items_res/`, the official beh/res split — wrong folder names silently fail item registration) → placed stone block (normal 3s / hardened 10s `destroy_time`, visually identical per color; breaking a stone frees the engine cell via `board.remove`). Ring spawners are **quantity-capped** (`SpawnMaxCountDict`): ores counted by a periodic frame-spread world scan (`RecountOres`); item "in-circulation" counts self-tracked in `itemExpireDict` — spawn registers a record expiring at spawn-time + `ItemDespawnSeconds`, consumption (via `ConsumeCarriedItem` → `OnItemConsumed`) frees the slot immediately, expiry handles vanilla despawn (`SpawnItemToLevel` returns only `True` on this SDK so no per-entityId tracking is possible; items hoarded unused in inventories past the TTL free their slot early). Game logic (occupancy / terminal state / five-in-a-row / draw) is **delegated to `modCommon/gomokuCore/board.py`** (`GomokuBoard`, zero MC dependencies); the server system only does MC-side glue. Gold stones use player value `3` in the engine — they occupy cells and block lines but never win (see `PlaceInEngine`). Design doc: `doc/gomoku-battle-design.md` |

`script_Gomoku/modCommon/gomokuCore/` is the only piece of logic in this repo that is testable from the shell: `gomoku_dev/test_board.py` runs its 32 unit tests under any Python (py2/3 compatible, no MC SDK imports). Other dev tooling at repo root: `gomoku_dev/gomoku_debug.py` (terminal REPL), `openspec/` (spec + change tracking; see `openspec/specs/gomoku-core/spec.md`).

**Mods must not import each other.** They interact only through two ModSDK mechanisms:

- **Direct system calls** — `serverApi.GetSystem(modName, systemName)`, then call public methods. Always guard for `None`: a mod may be absent from a given map. Every consumer does this (e.g. `StartLogic` calls `TeamServerSystem.ReQueueAllocation` / `ShowTeamUI`, and `EndLogicServerSystem.ReSetDynamicData` / `StartClock`).
- **Events** — `BroadcastEvent` / `ListenForEvent(namespace, systemName, eventName, ...)`. Cross-mod event names are duplicated as string constants in each side's config (e.g. `StartLogicEvent` is defined in StartLogic's config and listened for by `SkillMod` and `LimitedRespawnMod`). Changing an event name means grepping for the literal across all eight folders.

The `StartLogic → Team → EndLogic` chain is the backbone: StartLogic owns whether the round is running (`GetGameStartState()`, state `3`), and EndLogic queries `startLogicServerSystem.getPlayerEnsure()` to know which players count for victory judging. Both degrade gracefully when the other is missing. `EndLogicServerSystem.NotifyVictory` is **announcement-only** — actually ending a round early (as GomokuMod does on five-in-a-row) goes through `EndLogicServerSystem.ExternalSettleGame(victorName, victoryText=None)`, which cancels the pending timeout clock (`CancelClock`) and schedules the same `ReStartGame → StartLogic.ReStartGame` restart path the timeout settlement uses.

### Client/server split

Each mod registers a server system and (usually) a client system. Server holds authoritative state and `BroadcastToAllClient(...)` / `NotifyToClient(playerId, ...)`; client sends `NotifyToServer(...)`. Two structural conventions coexist:

- **Flat** (`script_StartLogic`, `script_EndLogic`, `script_World`, `script_ResourcePoint`, `script_LimitedRespawn`): `config.py`, `xxxServerSystem.py`, `xxxClientSystem.py`, `xxxUI.py` side by side, imported absolutely (`import config`) — the script folder is on `sys.path`.
- **Packaged** (`script_Skill`, `script_Team`): `modClient/` + `modServer/` + `modCommon/` subpackages with relative imports (`from ...modCommon import teamConfig`).

Follow whichever style the folder you are editing already uses.

### `editorConfig.py` is generated — do not hand-edit

Each mod has three config layers:

1. `editorConfigTemplate.py` — the schema/defaults shipped with the template component.
2. `editorConfig.py` — **written by MCStudio's component editor.** Holds `dataDict` (one entry per placed component instance, keyed by uuid) and sometimes `childDataDict`. Edits here are overwritten the next time the map is saved from the editor. Also defines `scriptFolderName`, which every mod uses to build class paths passed to `RegisterSystem`.
3. `config.py` / `teamConfig.py` / `worldConfig.py` / `skillModConfig.py` — the hand-written layer. It declares hardcoded defaults, then **overwrites them from `editorConfig`** via a module-scope loop:

```python
for _, data in editorConfig.dataDict.items():
    for key, value in data.items():
        locals()[key] = value
```

This `locals()` mutation only works at module scope in Python 2 — leave it alone. Derived values (`startPoint`/`endPoint` from `waitArea`, `teamPosDict` from `teamPosList`, `gameRuleDict` from `optionInfo`+`cheatInfo`) are computed *after* that loop, so new derived config must also go after it. To change a real gameplay value, prefer editing it in the MCStudio component editor; editing `config.py` defaults only takes effect for keys `editorConfig` does not supply.

### Coroutine managers

`coroutineMgrGas.py` (server) / `coroutineMgrGac.py` (client) are duplicated verbatim in most mods — a tiny generator scheduler. `CoroutineMgr.Tick()` must be pumped every frame, either from `Update()` or from an `OnScriptTickServer`/`OnScriptTickClient` handler; different mods pick different hooks.

Inside a coroutine: **`yield -N` waits N frames (30 frames = 1 second); `yield N` waits N seconds.** Hence the pervasive `* 30` conversions (`yield -self.clockEndTime * 30`).

Coroutines exist mostly to dodge init-order races — the client UI node often does not exist yet when the first server broadcast arrives, so handlers delay (`DelayUpdateUI`, `DelayUpdateScoreboard`, `DelayUpdatePlayerPrefix`).

### UI

Server never touches UI. Client systems register and create UI on the engine's `UiInitFinished` event:

```python
clientApi.RegisterUI(modName, uiName, editorConfig.scriptFolderName + '.' + pyClsPath, screenDef)
clientApi.CreateUI(modName, uiName, {"isHud": 1})
node = clientApi.GetUI(modName, uiName); node.Init()
```

The JSON layout lives in `resource_packs/resource_pack_P2R25RYV_0b0ae727/ui/` and **must be listed in `ui/_ui_defs.json`** to load. Control paths in the Python `ScreenNode` subclass (e.g. `"/waitNotifyPanal/waitNotifyLabel"`) mirror the JSON tree, so renaming a JSON control breaks the Python silently. Button handlers use the `@ViewBinder.binding(ViewBinder.BF_ButtonClickUp)` decorator and return `ViewRequest` flags.

Chinese text is embedded directly in Python source (files are `# -*- coding: utf-8 -*-`), with `§`-prefixed Minecraft color codes inline. Entity display names go in `resource_packs/.../texts/zh_CN.lang`.

## Hard-coded limits worth knowing

- **Max 5 teams.** `teamServerSystem` allocates fixed 5-element lists (`queuePlayerCount`, `queueScoreList`) and `teamConfig.queueColorDict` / the `['RED','GREEN','BLUE','YELLOW','PURPLE']` prefix colors have 5 entries. Adding a sixth team requires widening all of them.
- Team allocation strategy is a string key into `allocationMethodDict`: `RandomAllocation` or `MinmunAllocation` (note the misspelling — it is the actual key).
- `EndLogic` victory conditions are a `(endConditionType, endJudgeCondition)` tuple keying `victoryJudgeConditionList` in `script_EndLogic/config.py`. Supported pairs are enumerated there; anything else logs an error and no-ops.

## Assets and binary state

- `db/` is the LevelDB world save (blocks, entities) — binary, only MCStudio may write it. `db/presets.json` maps placed preset instances to world coordinates.
- `level.dat` / `level.dat_old` are NBT; `levelname.txt` is the display name.
- `world_behavior_packs.json` / `world_resource_packs.json` list the pack UUIDs the world loads. These **must match the `header.uuid` in each pack's `pack_manifest.json`**. Both files reference two packs; only one of each pair is present in this repo (the other is the editor-supplied `EditorAddon`, per `used_add_on_list.txt`).
- **Hand-edited pack content needs a version bump**: multiplayer clients cache packs by `header.uuid` + version and skip re-download if the version didn't change — files added by hand (`netease_items_beh/`, `netease_items_res/`, `item_texture.json`, `terrain_texture.json`, `blocks.json`) stay invisible to other clients until `pack_manifest.json` (header **and** modules) and the matching `world_*_packs.json` entry are all bumped together. MCStudio's editor bumps versions itself; shell/Claude edits don't.
- `behavior_packs/.../Presets/*.preset` are MCStudio editor prefabs (entity + attached parts); `entities/`, `netease_blocks/`, `netease_items_beh/` (items also need a matching `netease_items_res/` JSON in the resource pack — icon client-side, other components server-side) are standard Bedrock/NetEase JSON definitions. Custom content is namespaced `wihzo:` (with one stray `McChess:` block identifier — the gomoku board base `wihzo:McChess_ChessBase`).
- `.mcs/` is editor-local UI state — not gameplay.

Everything above, including the world `db/` and `level.dat`, is committed to git.
