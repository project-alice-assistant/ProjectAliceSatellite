settings = {
	'disableSoundAndMic'      : {
		'defaultValue': False,
		'dataType'    : 'boolean',
		'isSensitive' : False,
		'description' : 'If this device is a server without sound and mic, turn this to True',
		'onUpdate'    : 'enableDisableSoundInSnips',
		'category'    : 'device'
	},
	'uid': {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : False,
		'hidden'      : True,
		'description' : 'Attributed device uid',
		'category'    : 'device'
	},
	'mainUnitBroadcastPort': {
		'defaultValue': 12354,
		'dataType'    : 'integer',
		'isSensitive' : False,
		'description' : 'Port where new hardware addition is broadcasting'
	},
	'temperatureOffset'    : {
		'defaultValue': 0,
		'dataType'    : 'integer',
		'isSensitive' : False,
		'description' : 'Offset to use for temperature correction'
	},
	'ssid'                 : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : False,
		'description' : 'Your Wifi name'
	},
	'debug'                : {
		'defaultValue': False,
		'dataType'    : 'boolean',
		'isSensitive' : False,
		'description' : 'If true debug logs will show'
	},
	'wifipassword'         : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : True,
		'description' : 'Your Wifi password'
	},
	'mqttHost'             : {
		'defaultValue': 'localhost',
		'dataType'    : 'string',
		'isSensitive' : False,
		'description' : 'Mqtt server ip adress',
		'onUpdate'    : 'updateMqttSettings'
	},
	'mqttPort'             : {
		'defaultValue': 1883,
		'dataType'    : 'integer',
		'isSensitive' : False,
		'description' : 'Mqtt server port',
		'onUpdate'    : 'updateMqttSettings'
	},
	'mqttUser'             : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : False,
		'description' : 'Mqtt user. Leave blank if not password protected',
		'onUpdate'    : 'updateMqttSettings'
	},
	'mqttPassword'         : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : True,
		'description' : 'Mqtt password. Leave blank if not password protected',
		'onUpdate'    : 'updateMqttSettings'
	},
	'mqttTLSFile'          : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : False,
		'description' : 'Mqtt TLS file path for SSL',
		'onUpdate'    : 'updateMqttSettings'
	},
	'useHLC'               : {
		'defaultValue': False,
		'dataType'    : 'boolean',
		'isSensitive' : False,
		'description' : 'Enables Hermes Led Control for visual feedback from your assistant'
	},
	'aliceAutoUpdate'      : {
		'defaultValue': False,
		'dataType'    : 'boolean',
		'isSensitive' : False,
		'description' : 'Whether Alice should auto update, checked every hour'
	},
	'aliceUpdateChannel'   : {
		'defaultValue': 'master',
		'dataType'    : 'list',
		'isSensitive' : False,
		'values'      : {'Stable': 'master', 'Release candidate': 'rc', 'Beta': 'beta', 'Alpha': 'alpha'},
		'description' : 'Choose your update frequency. Release is the only supposedly safe option! But if you like to live on the edge, alpha will allow you to preview what\'s coming next!'
	},
	'onReboot'             : {
		'defaultValue': '',
		'dataType'    : 'string',
		'isSensitive' : False,
		'display'     : 'hidden'
	},
	'wakewordEngine'     : {
		'defaultValue': 'snips',
		'dataType'    : 'list',
		'isSensitive' : False,
		'values'      : ['porcupine', 'snips', 'precise'],
		'description' : 'Wakeword engine to use',
		'category'    : 'wakeword'
	},
	'wakewordSensitivity': {
		'defaultValue': 0.5,
		'dataType'    : 'range',
		'min'         : 0,
		'max'         : 1,
		'step'        : 0.01,
		'isSensitive' : False,
		'description' : 'Default wakeword sensitivity',
		'category'    : 'wakeword'
	},
}
