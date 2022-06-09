import requests
from ProjectAlice.core.base.model import Manager

from requests.exceptions import RequestException


class InternetManager(Manager):

	def __init__(self):
		super().__init__()
		self._online = False


	def onStart(self):
		super().onStart()
		if not self.ConfigManager.getAliceConfigByName('stayCompletlyOffline'):
			self.checkOnlineState(silent=True)
		else:
			self.logInfo('Configurations set to stay completly offline')


	@property
	def online(self) -> bool:
		return self._online


	def onBooted(self):
		self.checkOnlineState()


	def onFullMinute(self):
		if not self.ConfigManager.getAliceConfigByName('stayCompletlyOffline'):
			self.checkOnlineState()


	def checkOnlineState(self, addr: str = 'https://clients3.google.com/generate_204', silent: bool = False) -> bool:
		try:
			online = requests.get(addr).status_code == 204
		except RequestException:
			online = False

		if silent:
			self._online = online
			return online

		if self._online and not online:
			self._online = False
		elif not self._online and online:
			self._online = True

		return online
