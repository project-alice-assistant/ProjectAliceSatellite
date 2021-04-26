import difflib
import json
import logging
import typing
from pathlib import Path

from core.ProjectAliceExceptions import ConfigurationUpdateFailed
from core.base.model.Manager import Manager


class ConfigManager(Manager):

	CONFIG_FILE = Path('config.json')
	TEMPLATE_FILE = Path('configTemplate.json')

	def __init__(self):
		super().__init__()

		self._aliceTemplateConfigurations: typing.Dict[str, dict] = json.loads(self.TEMPLATE_FILE.read_text())
		self._aliceConfigurations: typing.Dict[str, typing.Any] = self._loadCheckAndUpdateAliceConfigFile()


	def onStart(self):
		super().onStart()


	def _loadCheckAndUpdateAliceConfigFile(self) -> dict:
		self.logInfo('Checking Alice configuration file')
		aliceConfigs = self.loadJsonFromFile(self.CONFIG_FILE)

		if not aliceConfigs:
			self.logInfo('Creating config file from config template')
			aliceConfigs = {configName: configData['defaultValue'] if 'defaultValue' in configData else configData for configName, configData in self._aliceTemplateConfigurations.items()}
			self.CONFIG_FILE.write_text(json.dumps(aliceConfigs, indent=4))

		changes = False
		for setting, definition in self._aliceTemplateConfigurations.items():
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
							# First try to cast the setting we have to the new type
							aliceConfigs[setting] = type(definition['defaultValue'])(aliceConfigs[setting])
							self.logInfo(f'- Existing configuration type mismatch: {setting}, cast variable to template configuration type')
						except Exception:
							# If casting failed let's fall back to the new default value
							self.logInfo(f'- Existing configuration type mismatch: {setting}, replaced with template configuration')
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
			if k not in self._aliceTemplateConfigurations:
				self.logInfo(f'- Deprecated configuration: {k}')
				changes = True
				del aliceConfigs[k]

		if changes:
			self.writeToAliceConfigurationFile(aliceConfigs)

		return aliceConfigs


	def updateAliceConfiguration(self, key: str, value: typing.Any, doPreAndPostProcessing: bool = True):
		if key not in self._aliceConfigurations:
			self.logWarning(f"'Was asked to update {key} but key doesn't exist'")
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
			self.CONFIG_FILE.write_text(json.dumps(sort, indent='\t'))
		except Exception:
			raise ConfigurationUpdateFailed()


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


	@property
	def aliceConfigurations(self) -> dict:
		return self._aliceConfigurations


	@property
	def aliceTemplateConfigurations(self) -> dict:
		return self._aliceTemplateConfigurations


	@staticmethod
	def loadJsonFromFile(jsonFile: Path) -> dict:
		try:
			return json.loads(jsonFile.read_text())
		except:
			# Prevents failing for caller
			raise
