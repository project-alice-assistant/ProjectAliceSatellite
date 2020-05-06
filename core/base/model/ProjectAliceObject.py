import json
from copy import copy

import core.base.SuperManager as SM
from core.commons import constants
from core.util.model.Logger import Logger


class ProjectAliceObject:

	def __init__(self, *args, **kwargs):
		self._logger = Logger(*args, **kwargs)


	def __repr__(self) -> str:
		ret = copy(self.__dict__)
		ret.pop('_logger')
		return json.dumps(ret)


	def __str__(self) -> str:
		return self.__repr__()


	def broadcast(self, method: str, exceptions: list = None, manager = None, **kwargs):
		if not exceptions:
			exceptions = list()

		if isinstance(exceptions, str):
			exceptions = [exceptions]

		if not exceptions and not manager:
			# Prevent infinite loop of broadcaster being broadcasted to re broadcasting
			self.logWarning('Cannot broadcast to itself, the calling method has to be put in exceptions')
			return

		if 'ProjectAlice' not in exceptions:
			exceptions.append('ProjectAlice')

		if not method.startswith('on'):
			method = f'on{method[0].capitalize() + method[1:]}'

		deadManagers = list()
		for name, man in SM.SuperManager.getInstance().managers.items():
			if not man:
				deadManagers.append(name)
				continue

			if (manager and man.name != manager.name) or man.name in exceptions:
				continue

			try:
				func = getattr(man, method, None)
				if func:
					func(**kwargs)

			except TypeError as e:
				self.logWarning(f'- Failed to broadcast event {method} to {man.name}: {e}')

		for name in deadManagers:
			del SM.SuperManager.getInstance().managers[name]


	def logInfo(self, msg: str):
		self._logger.doLog(function='info', msg=self.decorateLogs(msg), printStack=False)


	def logError(self, msg: str):
		self._logger.doLog(function='error', msg=self.decorateLogs(msg))


	def logDebug(self, msg: str):
		self._logger.doLog(function='debug', msg=self.decorateLogs(msg), printStack=False)


	def logFatal(self, msg: str):
		self._logger.doLog(function='fatal', msg=self.decorateLogs(msg))
		try:
			self.ProjectAlice.onStop()
			exit()
		except:
			exit()


	def logWarning(self, msg: str, printStack: bool = False):
		self._logger.doLog(function='warning', msg=self.decorateLogs(msg), printStack=printStack)


	def logCritical(self, msg: str):
		self._logger.doLog(function='critical', msg=self.decorateLogs(msg))


	def decorateLogs(self, text: str) -> str:
		return f'[{self.__class__.__name__}] {text}'


	def onStart(self):
		pass # Super object function is overriden only if needed


	def onStop(self):
		pass # Super object function is overriden only if needed


	def onBooted(self):
		pass # Super object function is overriden only if needed


	def onFullMinute(self):
		pass # Super object function is overriden only if needed


	def onFiveMinute(self):
		pass # Super object function is overriden only if needed


	def onQuarterHour(self):
		pass # Super object function is overriden only if needed


	def onFullHour(self):
		pass # Super object function is overriden only if needed


	def onAudioFrame(self, **kwargs):
		pass # Super object function is overriden only if needed


	def onWakeword(self, siteId: str, user: str = constants.UNKNOWN_USER):
		pass # Super object function is overriden only if needed


	def onHotword(self, siteId: str, user: str = constants.UNKNOWN_USER):
		pass # Super object function is overriden only if needed


	def onHotwordToggleOn(self, siteId: str, session):
		pass # Super object function is overriden only if needed


	def onHotwordToggleOff(self, siteId: str, session):
		pass # Super object function is overriden only if needed


	def onPlayBytes(self, requestId: str, payload: bytearray, siteId: str, sessionId: str = None):
		pass # Super object function is overriden only if needed


	def onPlayBytesFinished(self, requestId: str, siteId: str, sessionId: str = None):
		pass # Super object function is overriden only if needed


	@property
	def ProjectAlice(self): #NOSONAR
		return SM.SuperManager.getInstance().projectAlice


	@property
	def ConfigManager(self): #NOSONAR
		return SM.SuperManager.getInstance().configManager


	@property
	def MqttManager(self): #NOSONAR
		return SM.SuperManager.getInstance().mqttManager


	@property
	def DatabaseManager(self): #NOSONAR
		return SM.SuperManager.getInstance().databaseManager


	@property
	def ThreadManager(self): #NOSONAR
		return SM.SuperManager.getInstance().threadManager


	@property
	def TimeManager(self): #NOSONAR
		return SM.SuperManager.getInstance().timeManager


	@property
	def HotwordManager(self): #NOSONAR
		return SM.SuperManager.getInstance().hotwordManager


	@property
	def Commons(self): #NOSONAR
		return SM.SuperManager.getInstance().commonsManager


	@property
	def NetworkManager(self): #NOSONAR
		return SM.SuperManager.getInstance().networkManager


	@property
	def SkillManager(self): #NOSONAR
		return SM.SuperManager.getInstance().skillManager


	@property
	def InternetManager(self): #NOSONAR
		return SM.SuperManager.getInstance().internetManager


	@property
	def SnipsServicesManager(self): #NOSONAR
		return SM.SuperManager.getInstance().snipsServicesManager

	@property
	def AudioServer(self): #NOSONAR
		return SM.SuperManager.getInstance().audioManager
