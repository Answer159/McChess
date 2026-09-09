# -*- coding: utf-8 -*-
import editorConfig
ModName = "WorldMod"
ModVersion = "0.0.1"

WorldServerSystem = "WorldServerSystem"
WorldServerSystemClsPath = "worldServerSystem.WorldServerSystem"
WorldClientSystem = "WorldClientSystem"
WorldClientSystemClsPath = "worldClientSystem.WorldClientSystem"

# editor config begin
gameMode = 0
spawn = [0, 0, 0]
optionInfo = {
	"natural_regeneration": True,
	"experimental_gameplay": False,
	"show_coordinates": True,
	"fire_spreads": True,
	"pvp": True,
	"mob_loot": True,
	"tnt_explodes": True,
	"tile_drops": True,
}
title = "World"
difficulty = 1
cheatInfo = {
	"daylight_cycle": False,
	"keep_inventory": False,
	"mob_griefing": True,
	"stable_time": 6000,
	"command_blocks_enabled": True,
	"weather_cycle": False,
	"entities_drop_loot": True,
	"mob_spawn": False,
	"random_tick_speed": 1,
}
storyline = ""
cheat = True
compPath = ''
# editor config end
for _, data in editorConfig.dataDict.items():
	for key, value in data.items():
		locals()[key] = value
# to set
cheatInfo['enable'] = cheat
fixTime = cheatInfo["stable_time"]
del cheatInfo["stable_time"]
gameDifficulty = difficulty
gameType = gameMode
gameRuleDict = {'option_info': optionInfo}
if cheat:
	gameRuleDict['cheat_info'] = cheatInfo

