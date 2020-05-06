from typing import Union

from core.base.model.Manager import Manager


class SnipsServicesManager(Manager):


	def __init__(self):
		super().__init__()

		self._snipsServices = [
			'snips-hotword'
		]


	def snipsServices(self) -> list:
		return self._snipsServices


	def onStart(self):
		super().onStart()
		self.runCmd(cmd='start', services=self.snipsServices())


	def onStop(self):
		super().onStop()
		self.runCmd(cmd='stop', services=self.snipsServices())


	def runCmd(self, cmd: str, services: Union[str, list] = None):
		if not services:
			services = self._snipsServices

		if isinstance(services, str):
			services = [services]

		for service in services:
			result = self.Commons.runRootSystemCommand(['systemctl', cmd, service])
			if result.returncode == 0:
				self.logInfo(f"Service {service} {cmd}'ed")
			elif result.returncode == 5:
				pass # Do nothing
			else:
				self.logInfo(f"Tried to {cmd} the {service} service but it returned with return code {result.returncode}")
