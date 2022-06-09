import importlib
import json
import os
import shutil
import threading
import traceback
from pathlib import Path
from typing import Dict, Optional

from ProjectAlice.core.base.modeel.Version import Version
from ProjectAlice.core.base.model import Manager
from core.base.model.Manager

from core.ProjectAliceExceptions import GithubNotFound, GithubRateLimit, GithubTokenFailed, SkillStartingFailed
from core.base.model.AliceSkill import AliceSkill
from core.base.model.FailedAliceSkill import FailedAliceSkill
from core.commons import constants
from core.util.Decorators import IfSetting, Online


class SkillManager(Manager):

	DATABASE = {
		'skills' : [
			'skillName TEXT NOT NULL UNIQUE',
			'active INTEGER NOT NULL DEFAULT 1'
		]
	}

	def __init__(self):
		super().__init__(databaseSchema=self.DATABASE)

		self._busyInstalling = None

		self._skillInstallThread: Optional[threading.Thread] = None

		# This is only a dict of the skills, with name: dict(status, install file)
		self._skillList = dict()

		# These are dict of the skills, with name: skill instance
		self._activeSkills: Dict[str, AliceSkill] = dict()
		self._deactivatedSkills: Dict[str, AliceSkill] = dict()
		self._failedSkills: Dict[str, FailedAliceSkill] = dict()


	def onStart(self):
		super().onStart()

		self._busyInstalling = self.ThreadManager.newEvent('skillInstallation')

		self._skillList = self._loadSkills()

		if self.checkForSkillUpdates():
			self._checkForSkillInstall()

		self._skillInstallThread = self.ThreadManager.newThread(name='SkillInstallThread', target=self._checkForSkillInstall, autostart=False)
		self._initSkills()

		#self.ConfigManager.loadCheckAndUpdateSkillConfigurations()

		self.startAllSkills()


	# noinspection SqlResolve
	def _loadSkills(self) -> dict:
		skills = self.loadSkillsFromDB()
		skills = [skill['skillName'] for skill in skills]

		# First, make sure the skills installed are in database
		# if not, inject them
		physicalSkills = [skill.stem for skill in Path(self.Commons.rootDir(), 'skills').glob('**/*.install')]
		for file in physicalSkills:
			if file not in skills:
				if self.ConfigManager.getAliceConfigByName('devMode'):
					self.logWarning(f'Skill "{file}" is not declared in database, fixing this')
					self.addSkillToDB(file)
				else:
					self.logWarning(f'Skill "{file}" is not declared in database, ignoring it')

		# Next, check that database declared skills are still existing, using the first database load
		# If not, cleanup both skills and widgets tables
		for skill in skills:
			if skill not in physicalSkills:
				self.logWarning(f'Skill "{skill}" declared in database but is not existing, cleaning this')
				self.DatabaseManager.delete(
					tableName='skills',
					callerName=self.name,
					query='DELETE FROM :__table__ WHERE skillName = :skill',
					values={'skill': skill}
				)

		# Now that we are clean, reload the skills from database
		# Those represent the skills we have
		skills = self.loadSkillsFromDB()

		data = dict()
		for skill in skills:
			installer = json.loads(Path(self.Commons.rootDir(), f'skills/{skill["skillName"]}/{skill["skillName"]}.install').read_text())
			data[skill['skillName']] = {
				'active'   : skill['active'],
				'installer': installer
			}

		return dict(sorted(data.items()))


	def loadSkillsFromDB(self) -> list:
		return self.databaseFetch(
			tableName='skills',
			method='all'
		)


	def changeSkillStateInDB(self, skillName: str, newState: bool):
		# Changes the state of a skill in db and also deactivates widgets if state is False
		self.DatabaseManager.update(
			tableName='skills',
			callerName=self.name,
			values={
				'active': 1 if newState else 0
			},
			row=('skillName', skillName)
		)


	def addSkillToDB(self, skillName: str, active: int = 1):
		self.DatabaseManager.replace(
			tableName='skills',
			values={'skillName': skillName, 'active': active}
		)


	# noinspection SqlResolve
	def removeSkillFromDB(self, skillName: str):
		self.DatabaseManager.delete(
			tableName='skills',
			callerName=self.name,
			query='DELETE FROM :__table__ WHERE skillName = :skill',
			values={'skill': skillName}
		)


	@property
	def activeSkills(self) -> Dict[str, AliceSkill]:
		return self._activeSkills


	@property
	def deactivatedSkills(self) -> Dict[str, AliceSkill]:
		return self._deactivatedSkills


	@property
	def failedSkills(self) -> dict:
		return self._failedSkills


	@property
	def allSkills(self) -> dict:
		return {**self._activeSkills, **self._deactivatedSkills, **self._failedSkills}


	@property
	def allWorkingSkills(self) -> dict:
		return {**self._activeSkills, **self._deactivatedSkills}


	def onBooted(self):
		self.skillBroadcast(constants.EVENT_BOOTED)

		if self._skillInstallThread:
			self._skillInstallThread.start()


	def _initSkills(self, loadOnly: str = '', reload: bool = False):
		for skillName, data in self._skillList.items():
			if loadOnly and skillName != loadOnly:
				continue

			self._activeSkills.pop(skillName, None)
			self._failedSkills.pop(skillName, None)
			self._deactivatedSkills.pop(skillName, None)

			try:
				if not data['active']:
					self.logInfo(f'Skill {skillName} is disabled')

				skillInstance = self.instanciateSkill(skillName=skillName, reload=reload)
				if skillInstance:
					if data['active']:
						self._activeSkills[skillInstance.name] = skillInstance
					else:
						self._deactivatedSkills[skillName] = skillInstance
				else:
					self._failedSkills[skillName] = FailedAliceSkill(data['installer'])

			except SkillStartingFailed as e:
				self.logWarning(f'Failed loading skill: {e}')
				self._failedSkills[skillName] = FailedAliceSkill(data['installer'])
				continue
			except Exception as e:
				self.logWarning(f'Something went wrong loading skill {skillName}: {e}')
				self._failedSkills[skillName] = FailedAliceSkill(data['installer'])
				continue


	# noinspection PyTypeChecker
	def instanciateSkill(self, skillName: str, skillResource: str = '', reload: bool = False) -> AliceSkill:
		instance: AliceSkill = None
		skillResource = skillResource or skillName

		try:
			skillImport = importlib.import_module(f'skills.{skillName}.{skillResource}')

			if reload:
				skillImport = importlib.reload(skillImport)

			klass = getattr(skillImport, skillName)
			instance: AliceSkill = klass()
		except ImportError as e:
			self.logError(f"Couldn't import skill {skillName}.{skillResource}: {e}")
		except AttributeError as e:
			self.logError(f"Couldn't find main class for skill {skillName}.{skillResource}: {e}")
		except Exception as e:
			self.logError(f"Couldn't instanciate skill {skillName}.{skillResource}: {e} {traceback.print_exc()}")

		return instance


	def onStop(self):
		super().onStop()

		for skillItem in self._activeSkills.values():
			skillItem.onStop()


	def onQuarterHour(self):
		self.checkForSkillUpdates()


	def startAllSkills(self):
		supportedIntents = list()

		tmp = self._activeSkills.copy()
		for skillName in tmp:
			try:
				supportedIntents += self._startSkill(skillName)
			except SkillStartingFailed:
				continue

		self.logInfo(f'Skills started')


	def _startSkill(self, skillName: str):
		if skillName in self._activeSkills:
			skillInstance = self._activeSkills[skillName]
		elif skillName in self._deactivatedSkills:
			self._deactivatedSkills.pop(skillName, None)
			skillInstance = self.instanciateSkill(skillName=skillName)
			if skillInstance:
				self.activeSkills[skillName] = skillInstance
			else:
				return
		elif skillName in self._failedSkills:
			skillInstance = self.instanciateSkill(skillName=skillName)
			if skillInstance:
				self.activeSkills[skillName] = skillInstance
			else:
				return
		else:
			self.logWarning(f'Skill "{skillName}" is unknown')
			return

		try:
			skillInstance.onStart()
		except SkillStartingFailed:
			self._failedSkills[skillName] = FailedAliceSkill(self._skillList[skillName]['installer'])
		except Exception as e:
			self.logError(f'- Couldn\'t start skill "{skillName}". Error: {e}')

			try:
				self.deactivateSkill(skillName=skillName)
			except:
				self._activeSkills.pop(skillName, None)
				self._deactivatedSkills.pop(skillName, None)

			self._failedSkills[skillName] = FailedAliceSkill(self._skillList[skillName]['installer'])


	def isSkillActive(self, skillName: str) -> bool:
		if skillName in self._activeSkills:
			return self._activeSkills[skillName].active
		return False


	def getSkillInstance(self, skillName: str, silent: bool = False) -> Optional[AliceSkill]:
		if skillName in self._activeSkills:
			return self._activeSkills[skillName]
		else:
			if not silent:
				self.logWarning(f'Skill "{skillName}" is disabled, failed or does not exist in skills manager')

			return None


	def skillBroadcast(self, method: str, filterOut: list = None, **kwargs):
		"""
		Broadcasts a call to the given method on every skill
		:param filterOut: array, skills not to broadcast to
		:param method: str, the method name to call on every skill
		:return:
		"""

		if not method.startswith('on'):
			method = f'on{method[0].capitalize() + method[1:]}'

		for skillName, skillInstance in self._activeSkills.items():

			if filterOut and skillName in filterOut:
				continue

			try:
				func = getattr(skillInstance, method, None)
				if func:
					func(**kwargs)

				func = getattr(skillInstance, 'onEvent', None)
				if func:
					func(event=method, **kwargs)

			except TypeError as e:
				self.logWarning(f'- Failed to broadcast event {method} to {skillName}: {e}')


	def deactivateSkill(self, skillName: str, persistent: bool = False):
		if skillName in self._activeSkills:
			skillInstance = self._activeSkills.pop(skillName)
			self._deactivatedSkills[skillName] = skillInstance
			skillInstance.onStop()

			if persistent:
				self.changeSkillStateInDB(skillName=skillName, newState=False)
				self.logInfo(f'Deactivated skill "{skillName}" with persistence')
			else:
				self.logInfo(f'Deactivated skill "{skillName}" without persistence')

		else:
			self.logWarning(f'Skill "{skillName} is not active')


	def activateSkill(self, skillName: str, persistent: bool = False):
		if skillName not in self._deactivatedSkills and skillName not in self._failedSkills:
			self.logWarning(f'Skill "{skillName} is not deactivated or failed')
			return

		try:
			self._startSkill(skillName)

			if persistent:
				self.changeSkillStateInDB(skillName=skillName, newState=True)
				self.logInfo(f'Activated skill "{skillName}" with persistence')
			else:
				self.logInfo(f'Activated skill "{skillName}" without persistence')
		except:
			self.logError(f'Failed activating skill "{skillName}"')
			return


	def toggleSkillState(self, skillName: str, persistent: bool = False):
		if self.isSkillActive(skillName):
			self.deactivateSkill(skillName=skillName, persistent=persistent)
		else:
			self.activateSkill(skillName=skillName, persistent=persistent)


	# TODO
	@Online(catchOnly=True)
	@IfSetting(settingName='stayCompletlyOffline', settingValue=False)
	def checkForSkillUpdates(self, skillToCheck: str = None) -> bool:
		return
		self.logInfo('Checking for skill updates')
		updateCount = 0

		for skillName, data in self._skillList.items():
			if not data['active']:
				continue

			try:
				if skillToCheck and skillName != skillToCheck:
					continue

				remoteVersion = self.SkillStoreManager.getSkillUpdateVersion(skillName)
				localVersion = Version.fromString(self._skillList[skillName]['installer']['version'])
				if localVersion < remoteVersion:
					updateCount += 1
					self.logInfo(f'❌ {skillName} - Version {self._skillList[skillName]["installer"]["version"]} < {str(remoteVersion)} in {self.ConfigManager.getAliceConfigByName("skillsUpdateChannel")}')

					if not self.ConfigManager.getAliceConfigByName('skillAutoUpdate'):
						if skillName in self._activeSkills:
							self._activeSkills[skillName].updateAvailable = True
					else:
						if not self.downloadInstallTicket(skillName):
							raise Exception
				else:
					self.logInfo(f'✔ {skillName} - Version {self._skillList[skillName]["installer"]["version"]} in {self.ConfigManager.getAliceConfigByName("skillsUpdateChannel")}')

			except GithubNotFound:
				self.logInfo(f'❓ Skill "{skillName}" is not available on Github. Deprecated or is it a dev skill?')

			except Exception as e:
				self.logError(f'❗ Error checking updates for skill "{skillName}": {e}')

		self.logInfo(f'Found {updateCount} skill update(s)')
		return updateCount > 0


	# TODO
	@Online(catchOnly=True)
	def _checkForSkillInstall(self):
		return
		# Don't start the install timer from the main thread in case it's the first start
		if self._skillInstallThread:
			self.ThreadManager.newTimer(interval=10, func=self._checkForSkillInstall, autoStart=True)

		root = Path(self.Commons.rootDir(), constants.SKILL_INSTALL_TICKET_PATH)
		files = [f for f in root.iterdir() if f.suffix == '.install']

		if self._busyInstalling.isSet() or not files or self.ProjectAlice.restart:
			return

		self.logInfo(f'Found {len(files)} install ticket(s)')
		self._busyInstalling.set()

		skillsToBoot = dict()
		try:
			skillsToBoot = self._installSkills(files)
		except Exception as e:
			self._logger.logError(f'Error installing skill: {e}')
		finally:
			self.MqttManager.mqttBroadcast(topic='hermes/leds/clear')

			if skillsToBoot:
				for skillName, info in skillsToBoot.items():
					self._initSkills(loadOnly=skillName, reload=info['update'])
					self.ConfigManager.loadCheckAndUpdateSkillConfigurations(skillToLoad=skillName)
					self._startSkill(skillName)

					if info['update']:
						self.allSkills[skillName].onSkillUpdated()
					else:
						self.allSkills[skillName].onSkillInstalled()

				self.SnipsAssistantManager.train()
				self.DialogTemplateManager.afterSkillChange()
				self.NluManager.afterSkillChange()

			self._busyInstalling.clear()


	# TODO
	def _installSkills(self, skills: list) -> dict:
		return
		root = Path(self.Commons.rootDir(), constants.SKILL_INSTALL_TICKET_PATH)
		skillsToBoot = dict()
		self.MqttManager.mqttBroadcast(topic='hermes/leds/systemUpdate', payload={'sticky': True})
		for file in skills:
			skillName = Path(file).stem

			self.logInfo(f'Now taking care of skill {skillName}')
			res = root / file

			try:
				installFile = json.loads(res.read_text())

				skillName = installFile['name']
				path = Path(installFile['author'], skillName)

				if not skillName:
					self.logError('Skill name to install not found, aborting to avoid casualties!')
					continue

				directory = Path(self.Commons.rootDir()) / 'skills' / skillName

				if skillName in self._skillList:
					installedVersion = Version.fromString(self._skillList[skillName]['installer']['version'])
					remoteVersion = Version.fromString(installFile['version'])

					if installedVersion >= remoteVersion:
						self.logWarning(f'Skill "{skillName}" is already installed, skipping')
						self.Commons.runRootSystemCommand(['rm', res])
						continue
					else:
						self.logWarning(f'Skill "{skillName}" needs updating')
						updating = True
				else:
					updating = False

				self.checkSkillConditions(installFile)

				if skillName in self._activeSkills:
					try:
						self._activeSkills[skillName].onStop()
					except Exception as e:
						self.logError(f'Error stopping "{skillName}" for update: {e}')
						raise

				gitCloner = GithubCloner(baseUrl=f'{constants.GITHUB_URL}/skill_{skillName}.git', path=path, dest=directory)

				try:
					gitCloner.clone(skillName=skillName)
					self.logInfo('Skill successfully downloaded')
					self._installSkill(res)
					skillsToBoot[skillName] = {
						'update': updating
					}
				except (GithubTokenFailed, GithubRateLimit):
					self.logError('Failed cloning skill')
					raise
				except GithubNotFound:
					if self.ConfigManager.getAliceConfigByName('devMode'):
						if not Path(f'{self.Commons.rootDir}/skills/{skillName}').exists() or not \
								Path(f'{self.Commons.rootDir}/skills/{skillName}/{skillName.py}').exists() or not \
								Path(f'{self.Commons.rootDir}/skills/{skillName}/dialogTemplate').exists() or not \
								Path(f'{self.Commons.rootDir}/skills/{skillName}/talks').exists():
							self.logWarning(f'Skill "{skillName}" cannot be installed in dev mode due to missing base files')
						else:
							self._installSkill(res)
							skillsToBoot[skillName] = {
								'update': updating
							}
						continue
					else:
						self.logWarning(f'Skill "{skillName}" is not available on Github, cannot install')
						raise

			except Exception:
				self.logError(f'Failed installing skill "{skillName}"')
				if res.exists():
					res.unlink()

				self.broadcast(
					method=constants.EVENT_SKILL_INSTALL_FAILED,
					exceptions=self.name,
					skill=skillName
				)
				raise

		return skillsToBoot


	def _installSkill(self, res: Path):
		try:
			installFile = json.loads(res.read_text())
			pipReqs = installFile.get('pipRequirements', list())
			sysReqs = installFile.get('systemRequirements', list())
			scriptReq = installFile.get('script')
			directory = Path(self.Commons.rootDir()) / 'skills' / installFile['name']

			for requirement in pipReqs:
				self.Commons.runSystemCommand(['./venv/bin/pip3', 'install', requirement])

			for requirement in sysReqs:
				self.Commons.runRootSystemCommand(['apt-get', 'install', '-y', requirement])

			if scriptReq:
				self.Commons.runRootSystemCommand(['chmod', '+x', str(directory / scriptReq)])
				self.Commons.runRootSystemCommand([str(directory / scriptReq)])

			self.addSkillToDB(installFile['name'])
			self._skillList[installFile['name']] = {
				'active'   : 1,
				'installer': installFile
			}

			os.unlink(str(res))
		except Exception:
			raise


	def removeSkill(self, skillName: str):
		if skillName not in self.allSkills:
			return

		if skillName in self._activeSkills:
			self._activeSkills[skillName].onStop()

		self._skillList.pop(skillName, None)
		self._activeSkills.pop(skillName, None)
		self._deactivatedSkills.pop(skillName, None)
		self._failedSkills.pop(skillName, None)

		self.removeSkillFromDB(skillName=skillName)
		shutil.rmtree(Path(self.Commons.rootDir(), 'skills', skillName))


	def reloadSkill(self, skillName: str):
		self.logInfo(f'Reloading skill "{skillName}"')

		if skillName in self._activeSkills:
			self._activeSkills[skillName].onStop()

		self._initSkills(loadOnly=skillName, reload=True)
		self._startSkill(skillName=skillName)


	def wipeSkills(self):
		shutil.rmtree(Path(self.Commons.rootDir(), 'skills'))
		Path(self.Commons.rootDir(), 'skills').mkdir()

		self._activeSkills = dict()
		self._deactivatedSkills = dict()
		self._failedSkills = dict()
		self._loadSkills()


	# TODO
	def downloadInstallTicket(self, skillName: str) -> bool:
		return
		try:
			tmpFile = Path(self.Commons.rootDir(), f'system/skillInstallTickets/{skillName}.install')
			if not self.Commons.downloadFile(
					url=f'{constants.GITHUB_RAW_URL}/skill_{skillName}/{self.SkillStoreManager.getSkillUpdateTag(skillName)}/{skillName}.install',
					dest=str(tmpFile.with_suffix('.tmp'))
			):
				raise

			shutil.move(tmpFile.with_suffix('.tmp'), tmpFile)
			return True
		except Exception as e:
			self.logError(f'Error downloading install ticket for skill "{skillName}": {e}')
			return False
