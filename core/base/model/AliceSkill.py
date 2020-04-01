from __future__ import annotations

import inspect
import json
import sqlite3
from copy import copy
from pathlib import Path
from typing import Any

from core.ProjectAliceExceptions import SkillStartingFailed
from core.base.model.ProjectAliceObject import ProjectAliceObject


class AliceSkill(ProjectAliceObject):


	def __init__(self, databaseSchema: dict = None):
		super().__init__()
		try:
			self._skillPath = Path(inspect.getfile(self.__class__)).parent
			self._installFile = Path(inspect.getfile(self.__class__)).with_suffix('.install')
			self._installer = json.loads(self._installFile.read_text())
		except FileNotFoundError:
			raise SkillStartingFailed(skillName=type(self).__name__, error=f'[{type(self).__name__}] Cannot find install file')
		except Exception as e:
			raise SkillStartingFailed(skillName=type(self).__name__, error=f'[{type(self).__name__}] Failed loading skill: {e}')

		self._name = self._installer['name']
		self._author = self._installer['author']
		self._version = self._installer['version']
		self._icon = self._installer['icon']
		self._description = self._installer['desc']
		self._category = self._installer['category'] if 'category' in self._installer else 'undefined'
		self._updateAvailable = False
		self._active = False
		self._databaseSchema = databaseSchema


	@property
	def active(self) -> bool:
		return self._active


	@active.setter
	def active(self, value: bool):
		self._active = value


	@property
	def name(self) -> str:
		return self._name


	@name.setter
	def name(self, value: str):
		self._name = value


	@property
	def author(self) -> str:
		return self._author


	@author.setter
	def author(self, value: str):
		self._author = value


	@property
	def description(self) -> str:
		return self._description


	@description.setter
	def description(self, value: str):
		self._description = value


	@property
	def version(self) -> float:
		return self._version


	@version.setter
	def version(self, value: float):
		self._version = value


	@property
	def updateAvailable(self) -> bool:
		return self._updateAvailable


	@updateAvailable.setter
	def updateAvailable(self, value: bool):
		self._updateAvailable = value


	@property
	def icon(self) -> str:
		return self._icon


	@property
	def installFile(self) -> Path:
		return self._installFile


	@property
	def skillPath(self) -> Path:
		return self._skillPath


	def getResource(self, resourcePathFile: str = '') -> Path:
		return self.skillPath / resourcePathFile


	def _initDB(self) -> bool:
		if self._databaseSchema:
			return self.DatabaseManager.initDB(schema=self._databaseSchema, callerName=self.name)
		return True


	def onStart(self):
		self.logInfo(f'Starting')
		self._active = True
		self._initDB()
		self.logInfo(f'![green](✔ Started!)')


	def onStop(self):
		self._active = False
		self.logInfo(f'![green](✔ Stopped)')


	def onBooted(self) -> bool:
		return True


	def onSkillInstalled(self, **_kwargs):
		self._updateAvailable = False


	def onSkillUpdated(self, **_kwargs):
		self._updateAvailable = False


	# HELPERS
	def getConfig(self, key: str) -> Any:
		return self.ConfigManager.getSkillConfigByName(skillName=self.name, configName=key)


	def getSkillConfigs(self) -> dict:
		ret = copy(self.ConfigManager.getSkillConfigs(self.name))
		ret.pop('active', None)
		return ret


	def getSkillConfigsTemplate(self) -> dict:
		return self.ConfigManager.getSkillConfigsTemplate(self.name)


	def updateConfig(self, key: str, value: Any):
		self.ConfigManager.updateSkillConfigurationFile(skillName=self.name, key=key, value=value)


	def getAliceConfig(self, key: str) -> Any:
		return self.ConfigManager.getAliceConfigByName(configName=key)


	def updateAliceConfig(self, key: str, value: Any):
		self.ConfigManager.updateAliceConfiguration(key=key, value=value)


	def databaseFetch(self, tableName: str, query: str, values: dict = None, method: str = 'one') -> sqlite3.Row:
		return self.DatabaseManager.fetch(tableName=tableName, query=query, values=values, callerName=self.name, method=method)


	def databaseInsert(self, tableName: str, query: str = None, values: dict = None) -> int:
		return self.DatabaseManager.insert(tableName=tableName, query=query, values=values, callerName=self.name)


	def getSkillInstance(self, skillName: str) -> AliceSkill:
		return self.SkillManager.getSkillInstance(skillName=skillName)


	def __repr__(self) -> str:
		return json.dumps(self.toJson())


	def __str__(self) -> str:
		return self.__repr__()


	def toJson(self) -> dict:
		return {
			'name'           : self._name,
			'author'         : self._author,
			'version'        : self._version,
			'updateAvailable': self._updateAvailable,
			'active'         : self._active,
			'databaseSchema' : self._databaseSchema
		}
