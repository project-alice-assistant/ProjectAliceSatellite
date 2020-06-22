import json
import traceback
from typing import Union

import paho.mqtt.client as mqtt

from core.base.model.Manager import Manager
from core.base.model.States import State
from core.commons import constants


class MqttManager(Manager):

	def __init__(self):
		super().__init__()
		self._mqttClient = mqtt.Client()
		self._mqttLocalClient = mqtt.Client()
		self._dnd = False
		self._audioFrameTopic = constants.TOPIC_AUDIO_FRAME.replace('{}', self.ConfigManager.getAliceConfigByName('deviceName'))


	def onStart(self):
		super().onStart()

		self._mqttClient.on_message = self.onMqttMessage
		self._mqttLocalClient.on_message = self.onMqttMessage
		self._mqttClient.on_connect = self.onConnect
		self._mqttClient.on_log = self.onLog
		self._mqttLocalClient.on_log = self.onLog

		self._mqttClient.message_callback_add(constants.TOPIC_NEW_HOTWORD, self.onNewHotword)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_DISCONNECTION, self.onCoreDisconnection)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_RECONNECTION, self.onCoreReconnection)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_HEARTBEAT, self.onCoreHeartbeat)
		self._mqttClient.message_callback_add(constants.TOPIC_HOTWORD_TOGGLE_ON, self.hotwordToggleOn)
		self._mqttClient.message_callback_add(constants.TOPIC_HOTWORD_TOGGLE_OFF, self.hotwordToggleOff)
		self._mqttLocalClient.message_callback_add(constants.TOPIC_HOTWORD_DETECTED, self.onHotwordDetected)
		self._mqttLocalClient.message_callback_add(self._audioFrameTopic, self.onAudioFrameTopic)
		self._mqttClient.message_callback_add(constants.TOPIC_PLAY_BYTES.format(self.ConfigManager.getAliceConfigByName('deviceName')), self.topicPlayBytes)

		if self.ConfigManager.getAliceConfigByName('uuid'):
			self.connect()


	def onBooted(self):
		if not self.ConfigManager.getAliceConfigByName('uuid'):
			try:
				self.NetworkManager.setupSatellite()
				self.connect()
			except Exception as e:
				self.logCritical(f'Couldn\'t access Alice\'s network: {e}')
				traceback.print_exc()


	def onStop(self):
		super().onStop()
		self.disconnect()


	# noinspection PyUnusedLocal
	def onLog(self, client, userdata, level, buf):
		if level != 16:
			self.logError(buf)


	# noinspection PyUnusedLocal
	def onConnect(self, client, userdata, flags, rc):
		subscribedEvents = [
			(constants.TOPIC_NEW_HOTWORD, 0),
			(constants.TOPIC_ALICE_CONNECTION_ACCEPTED, 0),
			(constants.TOPIC_ALICE_CONNECTION_REFUSED, 0),
			(constants.TOPIC_CORE_RECONNECTION, 0),
			(constants.TOPIC_CORE_DISCONNECTION, 0),
			(constants.TOPIC_CORE_HEARTBEAT, 0),
			(constants.TOPIC_DND, 0),
			(constants.TOPIC_STOP_DND, 0),
			(constants.TOPIC_TOGGLE_DND, 0),
			(constants.TOPIC_HOTWORD_TOGGLE_ON, 0),
			(constants.TOPIC_HOTWORD_TOGGLE_OFF, 0),
			(constants.TOPIC_ASR_START_LISTENING, 0),
			(constants.TOPIC_ASR_STOP_LISTENING, 0),
			(constants.TOPIC_CORE_HEARTBEAT, 0),
			(constants.TOPIC_PLAY_BYTES.format(self.ConfigManager.getAliceConfigByName('deviceName')), 0)
		]

		self._mqttClient.subscribe(subscribedEvents)
		self._mqttLocalClient.subscribe(constants.TOPIC_HOTWORD_DETECTED)
		self._mqttLocalClient.subscribe(self._audioFrameTopic)

		self.NetworkManager.tryConnectingToAlice()


	def connect(self):
		if self.ConfigManager.getAliceConfigByName('mqttUser') and self.ConfigManager.getAliceConfigByName('mqttPassword'):
			self._mqttClient.username_pw_set(self.ConfigManager.getAliceConfigByName('mqttUser'), self.ConfigManager.getAliceConfigByName('mqttPassword'))

		if self.ConfigManager.getAliceConfigByName('mqttTLSFile'):
			self._mqttClient.tls_set(certfile=self.ConfigManager.getAliceConfigByName('mqttTLSFile'))
			self._mqttClient.tls_insecure_set(False)

		self._mqttClient.connect(self.ConfigManager.getAliceConfigByName('mqttHost'), int(self.ConfigManager.getAliceConfigByName('mqttPort')))
		self._mqttClient.loop_start()

		self._mqttLocalClient.connect(host='127.0.0.1')
		self._mqttLocalClient.loop_start()


	def disconnect(self):
		try:
			self._mqttClient.loop_stop()
			self._mqttClient.disconnect()

			self._mqttLocalClient.loop_stop()
			self._mqttLocalClient.disconnect()
		except:
			# Do nothing, we are certainly not connected
			pass


	def reconnect(self):
		self.disconnect()
		self.connect()


	def onMqttMessage(self, _client, _userdata, message: mqtt.MQTTMessage):
		try:
			statusName = ''
			statusValue = ''
			if message.topic == self._audioFrameTopic:
				self.broadcast(
					method=constants.EVENT_AUDIO_FRAME,
					exceptions=[self.name],
					propagateToSkills=True,
					message=message,
					siteId=message.topic.replace('hermes/audioServer/', '').replace('/audioFrame', '')
				)
				return

			siteId = self.Commons.parseSiteId(message)
			payload = self.Commons.payload(message)
			uid = payload.get('uid', None)

			if uid:
				if uid != self.ConfigManager.getAliceConfigByName('uuid'):
					self.logDebug(f'Based on received uid **{uid}** the message --{message.topic}-- was filtered out')
					return
			else:
				if siteId and siteId != self.ConfigManager.getAliceConfigByName('deviceName'):
					self.logDebug(f'Based on received siteId **{siteId}** the message --{message.topic}-- was filtered out')
					return

			if message.topic == constants.TOPIC_ALICE_CONNECTION_ACCEPTED:
				self.NetworkManager.onAliceConnectionAccepted()
				self.publish(
					topic=constants.TOPIC_CLEAR_LEDS,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)
			elif message.topic == constants.TOPIC_ALICE_CONNECTION_REFUSED:
				self.NetworkManager.onAliceConnectionRefused()
				self.publish(
					topic='hermes/leds/connectionError',
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)

			if self.NetworkManager.state != State.REGISTERED:
				return

			if message.topic == constants.TOPIC_STOP_DND:
				self.publish(
					topic=constants.TOPIC_CLEAR_LEDS,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)
				self._dnd = False
				statusName = 'dnd'
				statusValue = False
			elif message.topic == constants.TOPIC_DND:
				self.publish(
					topic=constants.TOPIC_DND_LEDS,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)
				self._dnd = True
				statusName = 'dnd'
				statusValue = True
			elif message.topic == constants.TOPIC_TOGGLE_DND:
				if self._dnd:
					topic = constants.TOPIC_CLEAR_LEDS
				else:
					topic = constants.TOPIC_DND_LEDS

				self._dnd = not self._dnd

				statusName = 'dnd'
				statusValue = self._dnd

				self.publish(
					topic=topic,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)

			elif message.topic == constants.TOPIC_ASR_START_LISTENING:
				self.broadcast(method=constants.EVENT_START_LISTENING, exceptions=[self.name], propagateToSkills=True)

			elif message.topic == constants.TOPIC_ASR_STOP_LISTENING:
				self.broadcast(method=constants.EVENT_STOP_LISTENING, exceptions=[self.name], propagateToSkills=True)

			if statusName:
				self.publish(
					topic=constants.TOPIC_DEVICE_STATUS,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName'),
						'uid': self.ConfigManager.getAliceConfigByName('uuid'),
						statusName: statusValue
					}
				)

			if self._dnd:
				return

		except Exception as e:
			self.logError(f'Error in onMessage: {e}')


	def onNewHotword(self, _client, _userdata, message: mqtt.MQTTMessage):
		payload = self.Commons.payload(message)
		if 'uid' not in payload or payload['uid'] != self.ConfigManager.getAliceConfigByName('uuid'):
			return

		self.HotwordManager.newHotword(payload)


	def onCoreReconnection(self, _client, _userdata, _message: mqtt.MQTTMessage):
		self.NetworkManager.onCoreReconnection()


	def onCoreDisconnection(self, _client, _userdata, _message: mqtt.MQTTMessage):
		self.NetworkManager.onCoreDisconnection()
		self.publish(
			topic='hermes/leds/connectionError',
			payload={
				'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
			}
		)


	def onAudioFrameTopic(self, _client, _data, msg: mqtt.MQTTMessage):
		self.broadcast(
			method=constants.EVENT_AUDIO_FRAME,
			exceptions=[self.name],
			propagateToSkills=True,
			message=msg,
			siteId=msg.topic.replace('hermes/audioServer/', '').replace('/audioFrame', '')
		)


	def topicPlayBytes(self, _client, _data, msg: mqtt.MQTTMessage):
		"""
		SessionId is completly custom and does not belong in the Hermes Protocol
		:param _client:
		:param _data:
		:param msg:
		:return:
		"""
		count = msg.topic.count('/')
		if count > 4:
			requestId = msg.topic.rsplit('/')[-1]
			sessionId = msg.topic.rsplit('/')[-2]
		else:
			requestId = msg.topic.rsplit('/')[-1]
			sessionId = None

		self.broadcast(method=constants.EVENT_PLAY_BYTES, exceptions=self.name, propagateToSkills=True, requestId=requestId, payload=msg.payload, sessionId=sessionId)


	def hotwordToggleOn(self, _client, _data, msg: mqtt.MQTTMessage):
		if not self.isForMe(msg):
			return

		self._mqttLocalClient.loop_start()
		self.broadcast(method=constants.EVENT_HOTWORD_TOGGLE_ON, exceptions=[self.name], propagateToSkills=True)


	def hotwordToggleOff(self, _client, _data, msg: mqtt.MQTTMessage):
		if not self.isForMe(msg):
			return

		self.broadcast(method=constants.EVENT_HOTWORD_TOGGLE_OFF, exceptions=[self.name], propagateToSkills=True)


	def onHotwordDetected(self, _client, _data, msg):
		"""
		Only triggers on local mqtt broker and sends it to Alice broker.
		:param _client:
		:param _data:
		:param msg:
		:return:
		"""
		self._mqttLocalClient.loop_stop()
		payload = self.Commons.payload(msg)

		user = constants.UNKNOWN_USER
		if payload['modelType'] == 'personal':
			user = payload['modelId']

		self.publish(
			topic=constants.TOPIC_HOTWORD_DETECTED,
			payload={
				'siteId': self.ConfigManager.getAliceConfigByName('deviceName'),
				'modelId': payload['modelId'],
				'modelVersion': payload['modelVersion'],
				'modelType': payload['modelType'],
				'currentSensitivity': payload['currentSensitivity']
			}
		)

		if user == constants.UNKNOWN_USER:
			self.broadcast(method=constants.EVENT_HOTWORD, exceptions=[self.name], propagateToSkills=True, user=user)
		else:
			self.broadcast(method=constants.EVENT_WAKEWORD, exceptions=[self.name], propagateToSkills=True, user=user)


	def onCoreHeartbeat(self, _client, _userdata, _message: mqtt.MQTTMessage):
		self.NetworkManager.coreHeartbeat()


	def publish(self, topic: str, payload: Union[dict, str] = None, qos: int = 0, retain: bool = False):
		if isinstance(payload, dict):
			payload = json.dumps(payload)

		self._mqttClient.publish(topic, payload, qos, retain)


	def localPublish(self, topic: str, payload: Union[dict, str] = None):
		if isinstance(payload, dict):
			payload = json.dumps(payload)

		self._mqttLocalClient.publish(
			topic=topic,
			payload=payload
		)


	@property
	def mqttClient(self) -> mqtt.Client:
		return self._mqttClient


	@property
	def mqttLocalClient(self) -> mqtt.Client:
		return self._mqttLocalClient


	def isForMe(self, message: mqtt.MQTTMessage) -> bool:
		siteId = self.Commons.parseSiteId(message)
		return siteId == self.ConfigManager.getAliceConfigByName('deviceName')
