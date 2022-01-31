from importlib import import_module, reload

from paho.mqtt.client import MQTTMessage

from core.base.model.Manager import Manager
from core.voice.model.WakewordEngine import WakewordEngine


class WakewordManager(Manager):

	def __init__(self):
		super().__init__()
		self._engine = None


	def onStart(self):
		super().onStart()
		self._startWakewordEngine()


	def onStop(self):
		super().onStop()
		if self._engine:
			self._engine.onStop()


	def onBooted(self):
		if self._engine:
			self._engine.onBooted()


	def onAudioFrame(self, message: MQTTMessage, siteId: str):
		if self._engine and self._engine.enabled:
			self._engine.onAudioFrame(message=message, siteId=siteId)


	def onHotwordToggleOn(self):
		if self._engine:
			self._engine.onHotwordToggleOn()


	def onHotwordToggleOff(self):
		if self._engine:
			self._engine.onHotwordToggleOff()


	def _startWakewordEngine(self):
		userWakeword = self.ConfigManager.getAliceConfigByName(configName='wakewordEngine').lower()

		self._engine = None

		package = f'core.voice.model.{userWakeword.title()}Wakeword'
		module = import_module(package)
		wakeword = getattr(module, package.rsplit('.', 1)[-1])
		self._engine = wakeword()

		if not self._engine.checkDependencies():
			if not self._engine.installDependencies():
				self._engine = None
			else:
				module = reload(module)
				wakeword = getattr(module, package.rsplit('.', 1)[-1])
				self._engine = wakeword()

		if self._engine is None:
			self.logFatal("Couldn't install wakeword engine, going down")
			return

		self._engine.onStart()


	@property
	def wakewordEngine(self) -> WakewordEngine:
		return self._engine


	def onDndOn(self):
		self.disableEngine()


	def onDndOff(self):
		self.enableEngine()


	def disableEngine(self):
		if self._engine:
			self._engine.onStop()
			self._engine.enabled = False


	def enableEngine(self):
		if self._engine:
			self._engine.onStart()
		else:
			self._startWakewordEngine()
			if self._engine:
				self._engine.onBooted()


	def restartEngine(self):
		if self._engine:
			self._engine.onStop()
		self.enableEngine()
