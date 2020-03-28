import json

from copy import copy

import core.base.SuperManager as SM
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
		except:
			exit()


	def logWarning(self, msg: str, printStack: bool = False):
		self._logger.doLog(function='warning', msg=self.decorateLogs(msg), printStack=printStack)


	def logCritical(self, msg: str):
		self._logger.doLog(function='critical', msg=self.decorateLogs(msg))


	def decorateLogs(self, text: str) -> str:
		return f'[{self.__class__.__name__}] {text}'


	def onStart(self):
		pass


	def onStop(self):
		pass


	def onBooted(self):
		pass


	def onFullMinute(self):
		pass


	def onFiveMinute(self):
		pass


	def onQuarterHour(self):
		pass


	def onFullHour(self):
		pass


	@property
	def ProjectAlice(self):
		return SM.SuperManager.getInstance().projectAlice


	@property
	def ConfigManager(self):
		return SM.SuperManager.getInstance().configManager


	@property
	def MqttManager(self):
		return SM.SuperManager.getInstance().mqttManager


	@property
	def DatabaseManager(self):
		return SM.SuperManager.getInstance().databaseManager


	@property
	def ThreadManager(self):
		return SM.SuperManager.getInstance().threadManager


	@property
	def TimeManager(self):
		return SM.SuperManager.getInstance().timeManager


	@property
	def WakewordManager(self):
		return SM.SuperManager.getInstance().wakewordManager


	@property
	def Commons(self):
		return SM.SuperManager.getInstance().commonsManager
