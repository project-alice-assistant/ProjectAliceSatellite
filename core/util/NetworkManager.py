import socket
import time

from core.base.model.Manager import Manager
from core.base.model.States import State
from core.commons import constants


class NetworkManager(Manager):

	def __init__(self):
		super().__init__()
		self._tries = 0
		self._greetingTimer = None
		self._state = State.BOOTING
		self._heartbeatTimer = None
		self._coreLastHeartbeat = 0
		self._checkCoreHeartbeatTimer = None


	def onStop(self):
		self.MqttManager.publish(
			topic=constants.TOPIC_DISCONNECTING,
			payload={
				'siteId': self.ConfigManager.getAliceConfigByName('deviceName'),
				'uid': self.ConfigManager.getAliceConfigByName('uuid'),
			}
		)


	def setupSatellite(self):
		self.logInfo('This satellite is not yet registered for Project Alice. Searching for main unit')

		self._state = State.NEW

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

		if not data:
			self.logFatal('The main unit did not answer')
			return
		elif data.decode() != 'ok':
			self._state = State.ERROR
			self.logFatal('The main unit refused the addition')
			return

		# Save everything and let's continue!
		self.ConfigManager.updateAliceConfiguration(key='mqttHost', value=mainUnitIp)
		self.ConfigManager.updateAliceConfiguration(key='deviceName', value=attributedRoom.replace('_', ' '))
		self.ConfigManager.updateAliceConfiguration(key='uuid', value=attributedUid)
		self._state = State.ACCEPTED


	def tryConnectingToAlice(self):
		if self._greetingTimer and self._greetingTimer.is_alive():
			self._greetingTimer.cancel()

		if self._tries >= 5:
			self.logWarning('Alice did not answer to greetings for 5 times, scheduling retry in 5 minutes')
			self._tries = 0
			self._state = State.DORMANT
			self._greetingTimer = self.ThreadManager.newTimer(
				interval=300,
				func=self.tryConnectingToAlice
			)
			return

		self._state = State.WAITING_REPLY

		self._tries += 1
		self.logInfo(f'Sending greetings to Alice --({self._tries}/5)--')

		self.MqttManager.publish(
			topic=constants.TOPIC_ALICE_GREETING,
			payload={
				'siteId': self.ConfigManager.getAliceConfigByName('deviceName'),
				'uid': self.ConfigManager.getAliceConfigByName('uuid'),
			}
		)

		self._greetingTimer = self.ThreadManager.newTimer(
			interval=5,
			func=self.tryConnectingToAlice
		)


	def onAliceConnectionAccepted(self):
		if self._state != State.WAITING_REPLY:
			return

		if self._greetingTimer and self._greetingTimer.is_alive():
			self._greetingTimer.cancel()

		self.cancelHeartbeatsTimers(restart=True)
		self._coreLastHeartbeat = time.time()

		self._state = State.REGISTERED
		self._tries = 0
		self.logInfo('Alice answered and accepted the connection')


	def onAliceConnectionRefused(self):
		if self._state != State.WAITING_REPLY:
			return

		self.cancelHeartbeatsTimers()
		self._state = State.REFUSED
		self.logFatal('Alice answered and refused the connection')


	def onCoreDisconnection(self):
		if self._state == State.REGISTERED:
			self._state = State.DISCONNECTED
			self.logInfo('Alice main unit disconnected')
			self.cancelHeartbeatsTimers()


	def onCoreReconnection(self):
		if self._state == State.DISCONNECTED:
			self.cancelHeartbeatsTimers(restart=True)
			self._coreLastHeartbeat = time.time()
			self.logInfo('Alice main unit came online')
			self.tryConnectingToAlice()


	def cancelHeartbeatsTimers(self, restart: bool = False):
		if self._heartbeatTimer and self._heartbeatTimer.is_alive():
			self._heartbeatTimer.cancel()

		if self._checkCoreHeartbeatTimer and self._checkCoreHeartbeatTimer.is_alive():
			self._checkCoreHeartbeatTimer.cancel()

		if restart:
			self._heartbeatTimer = self.ThreadManager.newTimer(interval=0.5, func=self.sendHeartbeat)
			self._checkCoreHeartbeatTimer = self.ThreadManager.newTimer(interval=3, func=self.checkCoreHeartbeat)


	def sendHeartbeat(self):
		self.MqttManager.publish(
			topic=constants.TOPIC_DEVICE_HEARTBEAT,
			payload={
				'uid': self.ConfigManager.getAliceConfigByName('uuid'),
				'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
			}
		)
		self._heartbeatTimer = self.ThreadManager.newTimer(interval=2, func=self.sendHeartbeat)


	def checkCoreHeartbeat(self):
		now = time.time()
		if now - 5 > self._coreLastHeartbeat:
			self.logWarning(f'Main unit hasn\'t given any signs of life for over 5 seconds, disconnecting...')
			self.onCoreDisconnection()


	def coreHeartbeat(self):
		self._coreLastHeartbeat = time.time()


	@property
	def state(self) -> State:
		return self._state
