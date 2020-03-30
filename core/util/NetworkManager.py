import socket

from core.base.model.Manager import Manager


class NetworkManager(Manager):

	def __init__(self):
		super().__init__()
		self._tries = 0


	def setupSatellite(self):
		self.logInfo('This satellite is not yet registered for Project Alice. Searching for main unit')

		listenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		listenSocket.settimeout(3)
		listenSocket.bind(('', self.ConfigManager.getAliceConfigByName('mainUnitBroadcastPort')))

		i = 0
		data = ''
		# Try to get some data
		while i <= 5:
			try:
				data = listenSocket.recv(1024)
				break
			except socket.timeout:
				i += 1
				if i >= 5:
					self.logFatal('No main unit found, did you ask Alice to add this new device?')
					return
				pass

		self.logInfo('Main unit found!')
		try:
			data = data.decode()
			mainUnitIp = str(data.split(':')[0])
			mainUnitListenPort = int(data.split(':')[1])
			attributedRoom = str(data.split(':')[2])
			attributedUid = str(data.split(':')[3])
		except:
			self.logFatal('Bad formatting in the main unit return data')
			return

		# Send back the module type and ip
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.connect((mainUnitIp, mainUnitListenPort))
		sock.send(bytes(f'{self.Commons.getLocalIp()}:AliceSatellite', encoding='utf8'))
		sock.close()

		# Check if we've been accepted
		i = 0
		data = ''
		while i <= 5:
			try:
				data = listenSocket.recv(1024)
				break
			except socket.timeout:
				i += 1
				pass

		if not data:
			self.logFatal('The main unit did not answer')
			return
		elif data.decode() != 'ok':
			self.logFatal('The main unit refused the addition')
			return

		# Save everything and let's continue!
		self.ConfigManager.updateAliceConfiguration(key='mqttHost', value=mainUnitIp)
		self.ConfigManager.updateAliceConfiguration(key='deviceName', value=attributedRoom)
		self.ConfigManager.updateAliceConfiguration(key='uuid', value=attributedUid)
		self.Commons.runRootSystemCommand(['restart', 'snips-satellite'])


	def tryConnectingToAlice(self):
		if self._tries >= 5:
			self.logWarning('Alice did not answer to greetings for 5 times, scheduling retry in 5 minutes')
			self._tries = 0
			return

		self._tries += 1
		self.logInfo(f'Sending greetings ({self._tries}/5) to Alice')
