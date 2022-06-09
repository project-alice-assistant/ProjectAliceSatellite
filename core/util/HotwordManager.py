from ProjectAlice.core.base.model import Manager

from core.base.model.HotwordDownloadThread import HotwordDownloadThread


class HotwordManager(Manager):


	def __init__(self):
		super().__init__()
		self._downloadThreads = list()


	def onStop(self):
		super().onStop()

		for thread in self._downloadThreads:
			if thread.is_alive():
				thread.join(timeout=1)


	def newHotword(self, data: dict):
		thread = HotwordDownloadThread(host=data['ip'], port=data['port'], hotwordName=data['name'])
		self._downloadThreads.append(thread)
		thread.start()
