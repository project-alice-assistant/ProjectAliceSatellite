from __future__ import annotations

from core.util.model.Logger import Logger


class SuperManager:
	NAME = 'SuperManager'
	_INSTANCE = None


	def __new__(cls, *args, **kwargs):
		if not isinstance(SuperManager._INSTANCE, SuperManager):
			SuperManager._INSTANCE = object.__new__(cls)

		return SuperManager._INSTANCE


	def __init__(self, mainClass):
		SuperManager._INSTANCE = self
		self._managers = dict()

		self.projectAlice = mainClass
		self.Commons = None
		self.CommonsManager = None
		self.ConfigManager = None
		self.DatabaseManager = None
		self.ThreadManager = None
		self.MqttManager = None
		self.TimeManager = None
		self.NetworkManager = None
		self.HotwordManager = None
		self.SkillManager = None
		self.InternetManager = None
		self.AudioManager = None
		self.WakewordManager = None
		self.SubprocessManager = None


	def onStart(self):
		try:
			commons = self._managers.pop('CommonsManager')
			commons.onStart()

			configManager = self._managers.pop('ConfigManager')
			configManager.onStart()

			subprocessManager = self._managers.pop('SubprocessManager')
			subprocessManager.onStart()

			internetManager = self._managers.pop('InternetManager')
			internetManager.onStart()

			databaseManager = self._managers.pop('DatabaseManager')
			databaseManager.onStart()

			networkManager = self._managers.pop('NetworkManager')
			networkManager.onStart()

			mqttManager = self._managers.pop('MqttManager')
			mqttManager.onStart()

			for manager in self._managers.values():
				if manager:
					manager.onStart()

			self._managers[commons.name] = commons
			self._managers[configManager.name] = configManager
			self._managers[subprocessManager.name] = subprocessManager
			self._managers[databaseManager.name] = databaseManager
			self._managers[mqttManager.name] = mqttManager
			self._managers[networkManager.name] = networkManager
			self._managers[internetManager.name] = internetManager
		except Exception as e:
			import traceback

			traceback.print_exc()
			Logger().logFatal(f'Error while starting managers: {e}')

	def onBooted(self):
		manager = None
		try:
			for manager in self._managers.values():
				if manager:
					manager.onBooted()
		except Exception as e:
			Logger().logError(f'Error while sending onBooted to manager **{manager.name}**: {e}')


	@staticmethod
	def getInstance() -> SuperManager:
		return SuperManager._INSTANCE


	def initManagers(self):
		from core.commons.CommonsManager import CommonsManager
		from core.base.ConfigManager import ConfigManager
		from core.server.MqttManager import MqttManager
		from core.util.DatabaseManager import DatabaseManager
		from core.util.ThreadManager import ThreadManager
		from core.util.TimeManager import TimeManager
		from core.util.NetworkManager import NetworkManager
		from core.util.HotwordManager import HotwordManager
		from core.base.SkillManager import SkillManager
		from core.util.InternetManager import InternetManager
		from core.util.SubprocessManager import SubprocessManager
		from core.server.AudioServer import AudioManager
		from core.voice.WakewordManager import WakewordManager

		self.CommonsManager = CommonsManager()
		self.Commons = self.CommonsManager
		self.ConfigManager = ConfigManager()
		self.DatabaseManager = DatabaseManager()
		self.ThreadManager = ThreadManager()
		self.MqttManager = MqttManager()
		self.TimeManager = TimeManager()
		self.NetworkManager = NetworkManager()
		self.HotwordManager = HotwordManager()
		self.SkillManager = SkillManager()
		self.InternetManager = InternetManager()
		self.AudioManager = AudioManager()
		self.WakewordManager = WakewordManager()
		self.SubprocessManager = SubprocessManager()

		self._managers = {name: manager for name, manager in self.__dict__.items() if name.endswith('Manager')}


	def onStop(self):
		mqttManager = self._managers.pop('MqttManager', None) # Mqtt goes down last with bug reporter
		bugReportManager = self._managers.pop('BugReportManager', None) # bug reporter goes down as last

		skillManager = self._managers.pop('SkillManager', None) # Skill manager goes down first, to tell the skills
		if skillManager:
			try:
				skillManager.onStop()
			except Exception as e:
				Logger().logError(f'Error stopping SkillManager: {e}')

		for managerName, manager in self._managers.items():
			try:
				if manager.isActive:
					manager.onStop()
			except Exception as e:
				Logger().logError(f'Error while shutting down manager **{managerName}**: {e}')

		if mqttManager:
			try:
				mqttManager.onStop()
			except Exception as e:
				Logger().logError(f'Error stopping MqttManager: {e}')

		if bugReportManager:
			try:
				bugReportManager.onStop()
			except Exception as e:
				Logger().logError(f'Error stopping BugReportManager: {e}')


	def getManager(self, managerName: str):
		return self._managers.get(managerName, None)


	def restartManager(self, manager: str):
		managerInstance = self._managers.get(manager, None)
		if not managerInstance:
			Logger().logWarning(f'Was asking to restart manager **{manager}** but it doesn\'t exist')
			return

		managerInstance.onStop()
		managerInstance.onStart()
		managerInstance.onBooted()


	@property
	def managers(self) -> dict:
		return self._managers
