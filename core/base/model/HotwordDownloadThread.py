import os
import re
import shutil
import socket
from pathlib import Path
from threading import Thread

from core.base.SuperManager import SuperManager
from core.util.model.Logger import Logger


class HotwordDownloadThread(Thread):

	def __init__(self, host: str, port: int, hotwordName: str):
		super().__init__()
		self._logger = Logger(prepend='[HotwordDownloadThread]')
		self._host = host
		self._port = int(port)
		self._hotwordName = hotwordName
		self.setDaemon(True)


	def run(self):
		sock = None
		try:
			self._logger.logInfo('Cleaning up')

			rootPath = Path(SuperManager.getInstance().commons.rootDir(), 'hotwords/snips_hotword')
			hotwordPath = rootPath / f'{self._hotwordName}'
			zipPath = hotwordPath.with_suffix('.zip')

			if zipPath.exists():
				zipPath.unlink()

			if hotwordPath.exists():
				shutil.rmtree(hotwordPath, ignore_errors=True)

			self._logger.logInfo(f'Connecting to **{self._host}_{self._port}**')
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.connect((self._host, self._port))

			self._logger.logInfo(f'Receiving hotword package: **{self._hotwordName}**')
			sock.settimeout(2)
			try:
				with zipPath.open('wb') as f:
					while True:
						data = sock.recv(1024)

						if not data:
							break

						f.write(data)
			except socket.timeout:
				sock.settimeout(None)

		except Exception as e:
			self._logger.logError(f'Error downloading hotword: {e}')
			if sock:
				sock.send(b'-1')
				sock.close()
			return

		try:
			self._logger.logInfo('New hotword received, unpacking...')
			shutil.unpack_archive(filename=zipPath, extract_dir=hotwordPath)

			conf = SuperManager.getInstance().configManager.getSnipsConfiguration(parent='snips-hotword', key='model', createIfNotExist=True)
			if not isinstance(conf, list):
				conf = list()

			wakewordRegex = re.compile(f'^{hotwordPath}=[0-9.]+$')
			for i, hotword in enumerate(conf.copy()):
				if wakewordRegex.match(hotword):
					conf.pop(i)

			conf.append(f'{hotwordPath}=0.52')
			SuperManager.getInstance().configManager.updateSnipsConfiguration(parent='snips-hotword', key='model', value=conf, createIfNotExist=True)

			sock.send(b'0')
			self._logger.logInfo(f'Sucessfully installed new hotword **{self._hotwordName}**')
		except Exception as e:
			self._logger.logError(f'Error while unpacking and installing hotword: {e}')
			sock.send(b'-2')
		finally:
			sock.close()
			os.remove(zipPath)
