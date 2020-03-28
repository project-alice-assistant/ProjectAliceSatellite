import json

import paho.mqtt.client as mqtt

from core.base.model.Manager import Manager
from core.commons import constants


class MqttManager(Manager):

	def __init__(self):
		super().__init__()

		self._mqttClient = mqtt.Client()


	def onStart(self):
		super().onStart()

		self._mqttClient.on_message = self.onMqttMessage
		self._mqttClient.on_connect = self.onConnect
		self._mqttClient.on_log = self.onLog
		self.connect()


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
			(constants.TOPIC_SESSION_ENDED, 0)
		]

		self._mqttClient.subscribe(subscribedEvents)


	def connect(self):
		if self.ConfigManager.getAliceConfigByName('mqttUser') and self.ConfigManager.getAliceConfigByName('mqttPassword'):
			self._mqttClient.username_pw_set(self.ConfigManager.getAliceConfigByName('mqttUser'), self.ConfigManager.getAliceConfigByName('mqttPassword'))

		if self.ConfigManager.getAliceConfigByName('mqttTLSFile'):
			self._mqttClient.tls_set(certfile=self.ConfigManager.getAliceConfigByName('mqttTLSFile'))
			self._mqttClient.tls_insecure_set(False)

		self._mqttClient.connect(self.ConfigManager.getAliceConfigByName('mqttHost'), int(self.ConfigManager.getAliceConfigByName('mqttPort')))

		self._mqttClient.loop_start()


	def disconnect(self):
		self._mqttClient.loop_stop()
		self._mqttClient.disconnect()


	def reconnect(self):
		self.disconnect()
		self.connect()


	# noinspection PyUnusedLocal
	def onMqttMessage(self, client, userdata, message: mqtt.MQTTMessage):
		try:
			siteId = self.Commons.parseSiteId(message)
			payload = self.Commons.payload(message)

		except Exception as e:
			self.logError(f'Error in onMessage: {e}')


	def publish(self, topic: str, payload: (dict, str) = None, qos: int = 0, retain: bool = False):
		if isinstance(payload, dict):
			payload = json.dumps(payload)
		self._mqttClient.publish(topic, payload, qos, retain)


	def mqttBroadcast(self, topic: str, payload: dict = None, qos: int = 0, retain: bool = False):
		if not payload:
			payload = dict()

		payload['siteId'] = constants.DEFAULT_SITE_ID
		self.publish(topic=topic, payload=json.dumps(payload), qos=qos, retain=retain)


	@property
	def mqttClient(self) -> mqtt.Client:
		return self._mqttClient
