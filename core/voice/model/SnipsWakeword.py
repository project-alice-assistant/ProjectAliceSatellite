from core.voice.model.WakewordEngine import WakewordEngine


class SnipsWakeword(WakewordEngine):

	NAME = 'Snips hotword'
	DEPENDENCIES = {
		'system': [
			'snips-hotword'
		],
		'pip': []
	}


	def onBooted(self):
		super().onBooted()
		result = self.Commons.runRootSystemCommand(['systemctl', 'start', 'snips-hotword'])
		if result.returncode:
			self.logWarning(f'Error: {result.stderr}')


	def onStop(self):
		super().onStop()
		self.Commons.runRootSystemCommand(['systemctl', 'stop', 'snips-hotword'])
