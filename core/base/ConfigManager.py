import difflib
import importlib
import json
import logging
import typing
from pathlib import Path

import configTemplate
from core.ProjectAliceExceptions import ConfigurationUpdateFailed
from core.base.model.Manager import Manager
from core.base.model.TomlFile import TomlFile


class ConfigManager(Manager):

	CONFIG_FILE = Path('config.json')
	TEMPLATE_FILE = Path('configTemplate.json')
	SNIPS_CONF = Path('/etc/snips.toml')

	def __init__(self):
		super().__init__()

		self._aliceConfigurations: typing.Dict[str, typing.Any] = self._loadCheckAndUpdateAliceConfigFile()
		self._aliceTemplateConfigurations: typing.Dict[str, dict] = configTemplate.settings
		self._snipsConfigurations = self.loadSnipsConfigurations()


	def onStart(self):
		super().onStart()


	def _loadCheckAndUpdateAliceConfigFile(self) -> dict:
		self.logInfo('Checking Alice configuration file')

		try:
			aliceConfigs = self.loadJsonFromFile(self.CONFIG_FILE)
		except Exception:
			self.logInfo(f'No {str(self.CONFIG_FILE)} found.')
			aliceConfigs = self.migrateConfigToJson()

		if not aliceConfigs:
			self.logInfo('Creating config file from config template')
			aliceConfigs = {configName: configData['defaultValue'] if 'defaultValue' in configData else configData for configName, configData in self._aliceTemplateConfigurations.items()}
			self.CONFIG_FILE.write_text(json.dumps(aliceConfigs, indent=4))

		changes = False
		for setting, definition in configTemplate.settings.items():
			if setting not in aliceConfigs:
				self.logInfo(f'- New configuration found: {setting}')
				changes = True
				aliceConfigs[setting] = definition.get('defaultValue', '')
			else:
				if setting == 'supportedLanguages':
					continue

				if definition['dataType'] != 'list':
					if not isinstance(aliceConfigs[setting], type(definition['defaultValue'])):
						changes = True
						try:
							# First try to cast the seting we have to the new type
							aliceConfigs[setting] = type(definition['defaultValue'])(aliceConfigs[setting])
							self.logInfo(f'- Existing configuration type missmatch: {setting}, cast variable to template configuration type')
						except Exception:
							# If casting failed let's fall back to the new default value
							self.logInfo(f'- Existing configuration type missmatch: {setting}, replaced with template configuration')
							aliceConfigs[setting] = definition['defaultValue']
				else:
					values = definition['values'].values() if isinstance(definition['values'], dict) else definition['values']

					if aliceConfigs[setting] not in values:
						changes = True
						self.logInfo(f'- Selected value "{aliceConfigs[setting]}" for setting "{setting}" doesn\'t exist, reverted to default value "{definition["defaultValue"]}"')
						aliceConfigs[setting] = definition['defaultValue']

		# Setting logger level immediately
		if aliceConfigs['debug']:
			logging.getLogger('ProjectAlice').setLevel(logging.DEBUG)

		temp = aliceConfigs.copy()

		for k, v in temp.items():
			if k not in configTemplate.settings:
				self.logInfo(f'- Deprecated configuration: {k}')
				changes = True
				del aliceConfigs[k]

		if changes:
			self.writeToAliceConfigurationFile(aliceConfigs)

		return aliceConfigs


	def updateAliceConfiguration(self, key: str, value: typing.Any, doPreAndPostProcessing: bool = True):
		if key not in self._aliceConfigurations:
			self.logWarning(f'Was asked to update {key} but key doesn\'t exist')
			raise ConfigurationUpdateFailed()

		if doPreAndPostProcessing:
			pre = self.getAliceConfUpdatePreProcessing(confName=key)

			if pre and not self.ConfigManager.doConfigUpdatePreProcessing(pre, value):
				return

		self._aliceConfigurations[key] = value
		self.writeToAliceConfigurationFile(self.aliceConfigurations)

		if doPreAndPostProcessing:
			post = self.getAliceConfUpdatePostProcessing(confName=key)
			if post:
				self.doConfigUpdatePostProcessing(functions={post})


	def writeToAliceConfigurationFile(self, confs: dict = None):
		"""
		Saves the given configuration into config.json
		:param confs: the dict to save
		"""
		confs = confs if confs else self._aliceConfigurations

		sort = dict(sorted(confs.items()))
		self._aliceConfigurations = sort

		try:
			self.CONFIG_FILE.write_text(json.dumps(sort, indent=4))
		except Exception:
			raise ConfigurationUpdateFailed()


	def loadSnipsConfigurations(self) -> TomlFile:
		self.logInfo('Loading Snips configuration file')

		snipsConfigTemplatePath = Path(self.Commons.rootDir(), 'system/snips/snips.toml')

		if not self.SNIPS_CONF.exists():
			self.Commons.runRootSystemCommand(['cp', snipsConfigTemplatePath, '/etc/snips.toml'])
			SNIPS_CONF = snipsConfigTemplatePath

		snipsConfig = TomlFile.loadToml(self.SNIPS_CONF)

		return snipsConfig


	def updateSnipsConfiguration(self, parent: str, key: str, value, createIfNotExist: bool = True):
		"""
		Setting a config in snips.toml
		:param parent: Parent key in toml
		:param key: Key in that parent key
		:param value: The value to set
		:param createIfNotExist: If the parent key or the key doesn't exist do create it
		"""

		config = self.getSnipsConfiguration(parent=parent, key=key, createIfNotExist=createIfNotExist)
		if config is not None:
			self._snipsConfigurations[parent][key] = value
			self._snipsConfigurations.dump()


	def getSnipsConfiguration(self, parent: str, key: str, createIfNotExist: bool = True) -> typing.Optional[str]:
		"""
		Getting a specific configuration from snips.toml
		:param parent: parent key
		:param key: key within parent conf
		:param createIfNotExist: If that conf doesn't exist, create it
		:return: config value
		"""
		if createIfNotExist and key not in self._snipsConfigurations[parent]:
			conf = self._snipsConfigurations[parent][key]  # TomlFile does auto create missing keys
			self._snipsConfigurations.dump()
			return conf

		config = self._snipsConfigurations[parent].get(key, None)
		if config is None:
			self.logWarning(f'Tried to get "{parent}/{key}" in snips configuration but key was not found')

		return config.value


	def configAliceExists(self, configName: str) -> bool:
		return configName in self._aliceConfigurations


	def getAliceConfigByName(self, configName: str, voiceControl: bool = False) -> typing.Any:
		return self._aliceConfigurations.get(
			configName,
			difflib.get_close_matches(word=configName, possibilities=self._aliceConfigurations, n=3) if voiceControl else ''
		)


	def getAliceConfigType(self, confName: str) -> typing.Optional[str]:
		# noinspection PyTypeChecker
		return self._aliceConfigurations.get(confName['dataType'])


	def getAliceConfUpdatePreProcessing(self, confName: str) -> typing.Optional[str]:
		# Some config need some pre processing to run some checks before saving
		return self._aliceTemplateConfigurations.get(confName, dict()).get('beforeUpdate')


	def getAliceConfUpdatePostProcessing(self, confName: str) -> typing.Optional[str]:
		# Some config need some post processing if updated while Alice is running
		return self._aliceTemplateConfigurations.get(confName, dict()).get('onUpdate')


	def doConfigUpdatePreProcessing(self, function: str, value: typing.Any) -> bool:
		# Call alice config pre processing functions.
		try:
			func = getattr(self, function)
			return func(value)
		except:
			self.logWarning(f'Configuration pre processing method **{function}** does not exist')
			return False


	def doConfigUpdatePostProcessing(self, functions: set):
		# Call alice config post processing functions. This will call methods that are needed after a certain setting was
		# updated while Project Alice was running
		for function in functions:
			try:
				func = getattr(self, function)
				func()
			except AttributeError:
				self.logWarning(f'Configuration post processing method **{function}** does not exist')
				continue


	def updateMqttSettings(self):
		self.ConfigManager.updateSnipsConfiguration('snips-common', 'mqtt', f'{self.getAliceConfigByName("mqttHost")}:{self.getAliceConfigByName("mqttPort"):}', True)

		if self.getAliceConfigByName('mqttUser'):
			self.ConfigManager.updateSnipsConfiguration('snips-common', 'mqtt_username', self.getAliceConfigByName('mqttUser'), False)

		if self.getAliceConfigByName('mqtt_password'):
			self.ConfigManager.updateSnipsConfiguration('snips-common', 'mqtt_password', self.getAliceConfigByName('mqttPassword'), False)

		if self.getAliceConfigByName('mqtt_tls_cafile'):
			self.ConfigManager.updateSnipsConfiguration('snips-common', 'mqtt_tls_cafile', self.getAliceConfigByName('mqttTLSFile'), False)


	def updateDeviceName(self):
		self.ConfigManager.updateSnipsConfiguration('snips-audio-server', 'bind', f'{self.getAliceConfigByName("uid")}@mqtt', True)


	@property
	def snipsConfigurations(self) -> TomlFile:
		return self._snipsConfigurations


	@property
	def aliceConfigurations(self) -> dict:
		return self._aliceConfigurations


	@property
	def aliceTemplateConfigurations(self) -> dict:
		return self._aliceTemplateConfigurations


	#todo remove this method in a few month 01092020
	def migrateConfigToJson(self):
		try:
			# noinspection PyUnresolvedReferences,PyPackageRequirements
			import config

			self.CONFIG_FILE.write_text(json.dumps(config.settings, indent=4))
			self.logInfo('Migrated from old config.py')
			return config.settings.copy()
		except ModuleNotFoundError:
			self.logWarning(f'No old config.py found!')
			return None


	@staticmethod
	def loadJsonFromFile(jsonFile: Path) -> dict:
		try:
			return json.loads(jsonFile.read_text())
		except:
			# Prevents failing for caller
			raise
