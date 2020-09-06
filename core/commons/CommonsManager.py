import inspect
import json
import socket
import string
import subprocess
from contextlib import contextmanager
from ctypes import *
from pathlib import Path
from typing import Any

import hashlib
import random
import requests
from paho.mqtt.client import MQTTMessage

from core.base.model.Manager import Manager
from core.commons import constants


class CommonsManager(Manager):
	ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


	def __init__(self):
		super().__init__(name='Commons')


	@staticmethod
	@contextmanager
	def shutUpAlsaFFS():
		asound = cdll.LoadLibrary('libasound.so')
		asound.snd_lib_error_set_handler(c_error_handler)
		yield
		asound.snd_lib_error_set_handler(None)


	@staticmethod
	def getFunctionCaller(depth: int = 3) -> str:
		return inspect.getmodulename(inspect.stack()[depth][1])


	@staticmethod
	def dictMaxValue(d: dict) -> Any:
		return max(d, key=d.get)


	@staticmethod
	def rootDir() -> str:
		return str(Path(__file__).resolve().parent.parent.parent)


	@staticmethod
	def payload(message: MQTTMessage) -> dict:
		try:
			payload = json.loads(message.payload)
		except (ValueError, TypeError):
			payload = dict()

		if payload is True:
			payload = {'true': True}
		elif payload is False:
			payload = {'false': False}

		return payload


	@classmethod
	def parseSiteId(cls, message: MQTTMessage) -> str:
		data = cls.payload(message)
		if 'siteId' in data:
			return data['siteId'].replace('_', ' ')
		else:
			from core.base.SuperManager import SuperManager
			return data.get('IPAddress', SuperManager.getInstance().configManager.getAliceConfigByName('uuid'))


	@staticmethod
	def clamp(x: float, minimum: float, maximum: float) -> float:
		return max(minimum, min(x, maximum))


	@staticmethod
	def angleToCardinal(angle: float) -> str:
		cardinals = ['north', 'north east', 'east', 'south east', 'south', 'south west', 'west', 'north west']
		return cardinals[int(((angle + 45 / 2) % 360) / 45)]


	@classmethod
	def toCamelCase(cls, theString: str, replaceSepCharacters: bool = False, sepCharacters: tuple = None) -> str:
		join = cls.toPascalCase(theString, replaceSepCharacters, sepCharacters)
		return join[0].lower() + join[1:]


	@staticmethod
	def toPascalCase(theString: str, replaceSepCharacters: bool = False, sepCharacters: tuple = None) -> str:
		if replaceSepCharacters:
			for char in sepCharacters or ('-', '_'):
				theString = theString.replace(char, ' ')

		return ''.join(x.capitalize() for x in theString.split(' '))


	@staticmethod
	def getLocalIp() -> str:
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			sock.connect(('10.255.255.255', 1))
			ip = sock.getsockname()[0]
		except:
			ip = '127.0.0.1'
		finally:
			sock.close()
		return ip


	@staticmethod
	def indexOf(sub: str, theString: str) -> int:
		try:
			return theString.index(sub)
		except ValueError:
			return -1


	def runRootSystemCommand(self, commands: list, shell: bool = False, stdout = subprocess.PIPE, stderr = subprocess.PIPE):
		if commands[0] != 'sudo':
			commands.insert(0, 'sudo')
		return self.runSystemCommand(commands, shell=shell, stdout=stdout, stderr=stderr)


	@staticmethod
	def runSystemCommand(commands: list, shell: bool = False, stdout = subprocess.PIPE, stderr = subprocess.PIPE):
		return subprocess.run(commands, shell=shell, stdout=stdout, stderr=stderr)


	def downloadFile(self, url: str, dest: str) -> bool:
		if not self.Commons.rootDir() in dest:
			dest = self.Commons.rootDir() + dest

		try:
			with requests.get(url, stream=True) as r:
				r.raise_for_status()
				with Path(dest).open('wb') as fp:
					for chunk in r.iter_content(chunk_size=8192):
						if chunk:
							fp.write(chunk)
			return True
		except Exception as e:
			self.logWarning(f'Failed downloading file: {e}')
			return False


	@staticmethod
	def fileChecksum(file: Path) -> str:
		return hashlib.blake2b(file.read_bytes()).hexdigest()


	@staticmethod
	def randomString(length: int) -> str:
		chars = string.ascii_letters + string.digits
		return ''.join(random.choice(chars) for _ in range(length))


	def randomNumber(self, length: int) -> int:
		digits = string.digits
		number = ''.join(random.choice(digits) for _ in range(length))
		return int(number) if not number.startswith('0') else self.randomNumber(length)


# noinspection PyUnusedLocal
def py_error_handler(filename, line, function, err, fmt):
	pass


c_error_handler = CommonsManager.ERROR_HANDLER_FUNC(py_error_handler)
