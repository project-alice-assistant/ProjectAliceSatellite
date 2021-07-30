from __future__ import annotations

import json
import re
from copy import copy
from typing import TYPE_CHECKING

from importlib_metadata import PackageNotFoundError, version as packageVersion

import core.base.SuperManager as SM
from core.base.model.Version import Version
from core.commons import constants
from core.util.model.Logger import Logger


if TYPE_CHECKING:
	from core.ProjectAlice import ProjectAlice
	from core.base.ConfigManager import ConfigManager
	from core.commons.CommonsManager import CommonsManager
	from core.server.AudioServer import AudioManager
	from core.server.MqttManager import MqttManager
	from core.util.DatabaseManager import DatabaseManager
	from core.util.InternetManager import InternetManager
	from core.util.ThreadManager import ThreadManager
	from core.util.TimeManager import TimeManager
	from core.util.SubprocessManager import SubprocessManager
	from core.voice.WakewordManager import WakewordManager


class ProjectAliceObject:
	DEPENDENCIES = {
		'system': [],
		'pip'   : []
	}

	def __init__(self, *args, **kwargs):
		self._logger = Logger(*args, **kwargs)


	def __repr__(self) -> str:
		ret = copy(self.__dict__)
		ret.pop('_logger')
		return json.dumps(ret)


	def __str__(self) -> str:
		return self.__repr__()


	def broadcast(self, method: str, exceptions: list = None, manager = None, propagateToSkills: bool = False, **kwargs):
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


	def checkDependencies(self) -> bool:
		self.logInfo('Checking dependencies')
		for dep in self.DEPENDENCIES['pip']:
			match = re.match(r'^([a-zA-Z-_]*)(?:([=><]{0,2})([\d.]*)$)', dep)
			if not match:
				continue

			packageName, operator, version = match.groups()
			if not packageName:
				self.logWarning('Wrongly declared PIP requirement')
				continue

			try:
				installedVersion = packageVersion(packageName)
			except PackageNotFoundError:
				self.logWarning(f'Found missing dependencies: {packageName}')
				return False

			if not installedVersion or not operator or not version:
				continue

			version = Version.fromString(version)
			installedVersion = Version.fromString(installedVersion)

			if (operator == '==' and version != installedVersion) or \
					(operator == '>=' and installedVersion < version) or \
					(operator == '>' and (installedVersion < version or installedVersion == version)) or \
					(operator == '<' and (installedVersion > version or installedVersion == version)):

				self.logWarning(f'Dependency "{packageName}" is not conform with version requirements')
				return False

		return True


	def installDependencies(self) -> bool:
		self.logInfo('Installing dependencies')

		try:
			for dep in self.DEPENDENCIES['system']:
				self.logInfo(f'Installing "{dep}"')
				self.Commons.runRootSystemCommand(['apt-get', 'install', '-y', dep])
				self.logInfo(f'Installed!')

			for dep in self.DEPENDENCIES['pip']:
				self.logInfo(f'Installing "{dep}"')
				self.Commons.runSystemCommand(['./venv/bin/pip', 'install', dep])
				self.logInfo(f'Installed!')

			return True
		except Exception as e:
			self.logError(f'Installing dependencies failed: {e}')
			return False


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
		pass # Super object function is overridden only if needed


	def onStop(self):
		pass # Super object function is overridden only if needed


	def onBooted(self):
		pass # Super object function is overridden only if needed


	def onFullMinute(self):
		pass # Super object function is overridden only if needed


	def onFiveMinute(self):
		pass # Super object function is overridden only if needed


	def onQuarterHour(self):
		pass # Super object function is overridden only if needed


	def onFullHour(self):
		pass # Super object function is overridden only if needed


	def onAudioFrame(self, **kwargs):
		pass # Super object function is overridden only if needed


	def onWakeword(self, user: str = constants.UNKNOWN_USER):
		pass # Super object function is overridden only if needed


	def onHotword(self, user: str = constants.UNKNOWN_USER):
		pass # Super object function is overridden only if needed


	def onHotwordToggleOn(self):
		pass # Super object function is overridden only if needed


	def onHotwordToggleOff(self):
		pass # Super object function is overridden only if needed


	def onPlayBytes(self, payload: bytearray, deviceUid: str, sessionId: str = None):
		pass # Super object function is overridden only if needed


	def onPlayBytesFinished(self, requestId: str, sessionId: str = None):
		pass # Super object function is overridden only if needed


	def onStartListening(self):
		pass # Super object function is overridden only if needed


	def onStopListening(self):
		pass # Super object function is overridden only if needed


	def onDndOn(self):
		pass # Super object function is overridden only if needed


	def onDndOff(self):
		pass # Super object function is overridden only if needed
	
	
	def onAliceConnectionAccepted(self):
		pass # Super object function is overridden only if needed


	def onAliceConnectionRefused(self):
		pass # Super object function is overridden only if needed


	@property
	def ProjectAlice(self) -> ProjectAlice: #NOSONAR
		return SM.SuperManager.getInstance().projectAlice


	@property
	def ConfigManager(self) -> ConfigManager: #NOSONAR
		return SM.SuperManager.getInstance().configManager


	@property
	def MqttManager(self) -> MqttManager: #NOSONAR
		return SM.SuperManager.getInstance().mqttManager


	@property
	def DatabaseManager(self) -> DatabaseManager: #NOSONAR
		return SM.SuperManager.getInstance().databaseManager


	@property
	def ThreadManager(self) -> ThreadManager: #NOSONAR
		return SM.SuperManager.getInstance().threadManager


	@property
	def TimeManager(self) -> TimeManager: #NOSONAR
		return SM.SuperManager.getInstance().timeManager


	@property
	def HotwordManager(self) -> HotwordManager: #NOSONAR
		return SM.SuperManager.getInstance().hotwordManager


	@property
	def Commons(self) -> CommonsManager: #NOSONAR
		return SM.SuperManager.getInstance().commonsManager


	@property
	def NetworkManager(self) -> NetworkManager: #NOSONAR
		return SM.SuperManager.getInstance().networkManager


	@property
	def SkillManager(self) -> SkillManager: #NOSONAR
		return SM.SuperManager.getInstance().skillManager


	@property
	def InternetManager(self) -> InternetManager: #NOSONAR
		return SM.SuperManager.getInstance().internetManager


	@property
	def WakewordManager(self) -> WakewordManager: #NOSONAR
		return SM.SuperManager.getInstance().wakewordManager

	@property
	def AudioServer(self) -> AudioManager: #NOSONAR
		return SM.SuperManager.getInstance().audioManager

	@property
	def SubprocessManager(self) -> SubprocessManager:  # NOSONAR
		return SM.SuperManager.getInstance().subprocessManager
