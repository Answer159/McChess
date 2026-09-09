# -*- coding: utf-8 -*-
isUnique = False
LastVersion = [
	0,
	1,
	3
]
compId = 'Skill'
version = [
	0,
	1,
	3
]
dataDict = {
	'0b2c20a8-2711-4401-969e-58be750f56e3': {
		'addBuffParams': {
			'buff': {
				'buffDuration': 5,
				'buffPower': 3,
				'buffType': 'regeneration'
			},
			'effectiveTarget': 1
		},
		'owner': '_all',
		'projectileParams': {
			'blockParams': {
				'destroyBlock': True,
				'replaceBlock': [
					'air',
					'空气'
				]
			},
			'effectiveTarget': 2,
			'gravity': 0.05,
			'nonBlockParams': {
				'buff': {
					'buffDuration': 0,
					'buffPower': 0,
					'buffType': 'none'
				},
				'damage': 0
			},
			'sfx': 'none',
			'velocity': 2
		},
		'skillCD': 20,
		'skillIcon': 'textures/icons/apple',
		'skillName': '治疗',
		'skillType': 1,
		'uuid': '0b2c20a8-2711-4401-969e-58be750f56e3'
	},
	'613beeb2-fe44-472c-bf90-d120ba98c37c': {
		'addBuffParams': {
			'buff': {
				'buffDuration': 0,
				'buffPower': 0,
				'buffType': 'none'
			},
			'effectiveTarget': 0
		},
		'owner': '火焰使者',
		'projectileParams': {
			'blockParams': {
				'destroyBlock': True,
				'replaceBlock': [
					'air',
					'空气'
				]
			},
			'effectiveTarget': 3,
			'gravity': 0.05,
			'nonBlockParams': {
				'buff': {
					'buffDuration': 0,
					'buffPower': 0,
					'buffType': 'none'
				},
				'damage': 3
			},
			'sfx': 'effects/fire',
			'velocity': 2
		},
		'skillCD': 5,
		'skillIcon': 'textures/icons/blaze_powder',
		'skillName': '火焰投掷',
		'skillType': 0,
		'uuid': '613beeb2-fe44-472c-bf90-d120ba98c37c'
	},
	'f1b5d609-51a0-4cf9-a653-eb1f76507d45': {
		'addBuffParams': {
			'buff': {
				'buffDuration': 0,
				'buffPower': 0,
				'buffType': 'none'
			},
			'effectiveTarget': 0
		},
		'owner': '森林之子',
		'projectileParams': {
			'blockParams': {
				'destroyBlock': True,
				'replaceBlock': [
					'air',
					'空气'
				]
			},
			'effectiveTarget': 3,
			'gravity': 0.05,
			'nonBlockParams': {
				'buff': {
					'buffDuration': 0,
					'buffPower': 0,
					'buffType': 'none'
				},
				'damage': 3
			},
			'sfx': 'effects/tree',
			'velocity': 2
		},
		'skillCD': 5,
		'skillIcon': 'textures/icons/bamboo',
		'skillName': '树枝投掷',
		'skillType': 0,
		'uuid': 'f1b5d609-51a0-4cf9-a653-eb1f76507d45'
	}
}
scriptFolderName = 'script_Skill'
