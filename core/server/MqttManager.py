import json
import re
import traceback
from typing import Union

import paho.mqtt.client as mqtt
from paho.mqtt import publish

from core.base.model.Manager import Manager
from core.base.model.States import State
from core.commons import constants


class MqttManager(Manager):

	def __init__(self):
		super().__init__()
		self._mqttClient = mqtt.Client()
		self._dnd = False
		self._audioFrameRegex = re.compile(constants.TOPIC_AUDIO_FRAME.replace('{}', '(.*)'))


	def onStart(self):
		super().onStart()

		self._mqttClient.on_message = self.onMqttMessage
		self._mqttClient.on_connect = self.onConnect
		self._mqttClient.on_log = self.onLog

		self._mqttClient.message_callback_add(constants.TOPIC_NEW_HOTWORD, self.onNewHotword)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_DISCONNECTION, self.onCoreDisconnection)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_RECONNECTION, self.onCoreReconnection)
		self._mqttClient.message_callback_add(constants.TOPIC_CORE_HEARTBEAT, self.onCoreHeartbeat)
		self._mqttClient.message_callback_add(constants.TOPIC_HOTWORD_TOGGLE_ON, self.hotwordToggleOn)
		self._mqttClient.message_callback_add(constants.TOPIC_HOTWORD_TOGGLE_OFF, self.hotwordToggleOff)
		self._mqttClient.message_callback_add(constants.TOPIC_HOTWORD_DETECTED, self.onHotwordDetected)
		self._mqttClient.message_callback_add(constants.TOPIC_PLAY_BYTES.format(constants.DEFAULT_SITE_ID), self.topicPlayBytes)

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
			(constants.TOPIC_DND, 0),
			(constants.TOPIC_STOP_DND, 0),
			(constants.TOPIC_TOGGLE_DND, 0),
			(constants.TOPIC_HOTWORD_DETECTED, 0),
			(constants.TOPIC_HOTWORD_TOGGLE_ON, 0),
			(constants.TOPIC_HOTWORD_TOGGLE_OFF, 0),
			(constants.TOPIC_PLAY_BYTES.format(constants.DEFAULT_SITE_ID), 0)
		]

		self._mqttClient.subscribe(subscribedEvents)
		self.NetworkManager.tryConnectingToAlice()


	def connect(self):
		if self.ConfigManager.getAliceConfigByName('mqttUser') and self.ConfigManager.getAliceConfigByName('mqttPassword'):
			self._mqttClient.username_pw_set(self.ConfigManager.getAliceConfigByName('mqttUser'), self.ConfigManager.getAliceConfigByName('mqttPassword'))

		if self.ConfigManager.getAliceConfigByName('mqttTLSFile'):
			self._mqttClient.tls_set(certfile=self.ConfigManager.getAliceConfigByName('mqttTLSFile'))
			self._mqttClient.tls_insecure_set(False)

		self._mqttClient.connect(self.ConfigManager.getAliceConfigByName('mqttHost'), int(self.ConfigManager.getAliceConfigByName('mqttPort')))

		self._mqttClient.loop_start()


	def disconnect(self):
		try:
			self._mqttClient.loop_stop()
			self._mqttClient.disconnect()
		except:
			# Do nothing, we are certainly not connected
			pass


	def reconnect(self):
		self.disconnect()
		self.connect()


	def onMqttMessage(self, _client, _userdata, message: mqtt.MQTTMessage):
		try:
			if self._audioFrameRegex.match(message.topic):
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
					self.logDebug(f'Based on uid **{uid}** the message --{message.topic}-- was filtered out')
					return
			else:
				if siteId and siteId != self.ConfigManager.getAliceConfigByName('deviceName'):
					self.logDebug(f'Based on siteId **{siteId}** the message --{message.topic}-- was filtered out')
					return

			if message.topic == constants.TOPIC_ALICE_CONNECTION_ACCEPTED:
				self.NetworkManager.onAliceConnectionAccepted()
				self.publish(
					topic='hermes/leds/clear',
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
					topic='hermes/leds/clear',
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)
				self._dnd = False
			elif message.topic == constants.TOPIC_DND:
				self.publish(
					topic='hermes/leds/doNotDisturb',
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
					}
				)
				self._dnd = True
			elif message.topic == constants.TOPIC_TOGGLE_DND:
				if self._dnd:
					topic = 'hermes/leds/clear'
				else:
					topic = 'hermes/leds/doNotDisturb'

				self._dnd = not self._dnd

				self.publish(
					topic=topic,
					payload={
						'siteId': self.ConfigManager.getAliceConfigByName('deviceName')
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

		siteId = self.Commons.parseSiteId(msg)
		self.broadcast(method=constants.EVENT_PLAY_BYTES, exceptions=self.name, propagateToSkills=True, requestId=requestId, payload=msg.payload, siteId=siteId, sessionId=sessionId)


	def hotwordToggleOn(self, _client, _data, msg: mqtt.MQTTMessage):
		siteId = self.Commons.parseSiteId(msg)
		if siteId != constants.DEFAULT_SITE_ID:
			return

		self.broadcast(method=constants.EVENT_HOTWORD_TOGGLE_ON, exceptions=[self.name], propagateToSkills=True, siteId=siteId)


	def hotwordToggleOff(self, _client, _data, msg: mqtt.MQTTMessage):
		siteId = self.Commons.parseSiteId(msg)
		if siteId != constants.DEFAULT_SITE_ID:
			return

		self.broadcast(method=constants.EVENT_HOTWORD_TOGGLE_OFF, exceptions=[self.name], propagateToSkills=True, siteId=siteId)


	def onHotwordDetected(self, _client, _data, msg):
		print('hotword')
		siteId = self.Commons.parseSiteId(msg)
		payload = self.Commons.payload(msg)

		user = constants.UNKNOWN_USER
		if payload['modelType'] == 'personal':
			user = payload['modelId']

		if user == constants.UNKNOWN_USER:
			self.broadcast(method=constants.EVENT_HOTWORD, exceptions=[self.name], propagateToSkills=True, siteId=siteId, user=user)
		else:
			self.broadcast(method=constants.EVENT_WAKEWORD, exceptions=[self.name], propagateToSkills=True, siteId=siteId, user=user)


	def onCoreHeartbeat(self, _client, _userdata, _message: mqtt.MQTTMessage):
		self.NetworkManager.coreHeartbeat()


	def publish(self, topic: str, payload: Union[dict, str] = None, qos: int = 0, retain: bool = False):
		if isinstance(payload, dict):
			payload = json.dumps(payload)

		self._mqttClient.publish(topic, payload, qos, retain)


	@staticmethod
	def localPublish(topic: str, payload: Union[dict, str] = None):
		if isinstance(payload, dict):
			payload = json.dumps(payload)

		publish.single(
			topic=topic,
			payload=payload,
			hostname='localhost'
		)


	@property
	def mqttClient(self) -> mqtt.Client:
		return self._mqttClient
