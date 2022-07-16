import subprocess

import requests

from core.base.SuperManager import SuperManager
from core.base.model.Version import Version
from core.commons import constants
from core.commons.model.Singleton import Singleton
from core.util.Stopwatch import Stopwatch
from core.util.model.Logger import Logger


class ProjectAlice(Singleton):
	NAME = 'ProjectAlice'


	def __init__(self, restartHandler: callable):
		Singleton.__init__(self, self.NAME)
		self._logger = Logger(prepend='[Project Alice]')
		self._logger.logInfo('Starting Alice satellite unit')
		self._booted = False
		self._isUpdating = False
		self._shuttingDown = False
		with Stopwatch() as stopWatch:
			self._restart = False
			self._restartHandler = restartHandler

			self._superManager = SuperManager(self)

			self._superManager.initManagers()

			if self._superManager.ConfigManager.getAliceConfigByName('useHLC') and self._superManager.ConfigManager.getAliceConfigByName('uuid'):
				self._superManager.Commons.runRootSystemCommand(['systemctl', 'stop', 'hermesledcontrol'])
				self._superManager.Commons.runRootSystemCommand(['systemctl', 'start', 'hermesledcontrol'])

			self._superManager.onStart()

			self._superManager.onBooted()

		self._logger.logInfo(f'Started in {stopWatch} seconds')
		self._booted = True


	@property
	def name(self) -> str:
		return self.NAME


	@property
	def isBooted(self) -> bool:
		return self._booted


	@property
	def restart(self) -> bool:
		return self._restart


	@restart.setter
	def restart(self, value: bool):
		self._restart = value


	def doRestart(self):
		self._restart = True
		self.onStop()


	def onStop(self, withReboot: bool = False):
		self._logger.logInfo('Shutting down')
		self._shuttingDown = True
		self._superManager.onStop()
		if self._superManager.ConfigManager.getAliceConfigByName('useHLC'):
			self._superManager.Commons.runRootSystemCommand(['systemctl', 'stop', 'hermesledcontrol'])

		self._booted = False
		self.INSTANCE = None

		if withReboot:
			subprocess.run(['sudo', 'shutdown', '-r', 'now'])
		else:
			self._restartHandler()


	def onFullHour(self):
		if not self._superManager.ConfigManager.getAliceConfigByName('aliceAutoUpdate'):
			return
		self.updateProjectAlice()


	def updateProjectAlice(self):
		self._logger.logInfo('Checking for satellite updates')
		self._isUpdating = True
		req = requests.get(url=f'{constants.GITHUB_API_URL}/ProjectAliceSatellite/branches', auth=SuperManager.getInstance().ConfigManager.getGithubAuth())
		if req.status_code != 200:
			self._logger.logWarning('Failed checking for updates')
			return

		userUpdatePref = SuperManager.getInstance().ConfigManager.getAliceConfigByName('aliceUpdateChannel')

		if userUpdatePref == 'master':
			candidate = 'master'
		else:
			candidate = Version.fromString(constants.VERSION)
			for branch in req.json():
				repoVersion = Version.fromString(branch['name'])
				if not repoVersion.isVersionNumber:
					continue

				releaseType = repoVersion.releaseType
				if userUpdatePref == 'rc' and releaseType in {'b', 'a'} or userUpdatePref == 'beta' and releaseType == 'a':
					continue

				if repoVersion > candidate:
					candidate = repoVersion

		self._logger.logInfo(f'Checking on "{str(candidate)}" update channel')
		commons = SuperManager.getInstance().Commons

		currentHash = subprocess.check_output(['git', 'rev-parse', '--short HEAD'])

		commons.runSystemCommand(['git', '-C', commons.rootDir(), 'stash'])
		commons.runSystemCommand(['git', '-C', commons.rootDir(), 'clean', '-df'])
		commons.runSystemCommand(['git', '-C', commons.rootDir(), 'checkout', str(candidate)])
		commons.runSystemCommand(['git', '-C', commons.rootDir(), 'pull'])

		newHash = subprocess.check_output(['git', 'rev-parse', '--short HEAD'])

		if currentHash != newHash:
			self._logger.logWarning('New satellite version installed, need to restart...')
			self.doRestart()

		self._isUpdating = False


	@property
	def updating(self) -> bool:
		return self._isUpdating


	@property
	def shuttingDown(self) -> bool:
		return self._shuttingDown
