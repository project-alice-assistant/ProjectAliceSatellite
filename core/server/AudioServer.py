#  Copyright (c) 2021
#
#  This file, AudioServer.py, is part of Project Alice.
#
#  Project Alice is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>
#
#  Last modified: 2021.04.13 at 12:56:47 CEST

import io
import time
import uuid
import wave

import sounddevice as sd
from typing import Dict, Optional, Union
# noinspection PyUnresolvedReferences
from webrtcvad import Vad

from core.ProjectAliceExceptions import PlayBytesStopped
from core.base.model.Manager import Manager
from core.commons import constants
from core.util.model.AliceEvent import AliceEvent


class AudioManager(Manager):

	SAMPLERATE = 16000
	FRAMES_PER_BUFFER = 320

	LAST_USER_SPEECH = 'var/cache/lastUserpeech_{}_{}.wav'
	SECOND_LAST_USER_SPEECH = 'var/cache/secondLastUserSpeech_{}_{}.wav'

	def __init__(self):
		super().__init__()

		self._stopPlayingFlag: Optional[AliceEvent] = None
		self._playing = False
		self._waves: Dict[str, wave.Wave_write] = dict()
		self._audioInputStream = None

		self._vad = Vad(2)

		self._audioInput = None
		self._audioOutput = None

		self._broadcastLocal = True

	def onStart(self):
		super().onStart()

		if not self.ConfigManager.getAliceConfigByName('inputDevice'):
			self.logWarning('Input device not set in config, trying to find default device')
			try:
				self._audioInput = sd.query_devices(kind='input')['name']
			except:
				self.logFatal('Audio input not found, cannot continue')
				return
			self.ConfigManager.updateAliceConfiguration(key='inputDevice', value=self._audioInput)
		else:
			self._audioInput = self.ConfigManager.getAliceConfigByName('inputDevice')

		if not self.ConfigManager.getAliceConfigByName('outputDevice'):
			self.logWarning('Output device not set in config, trying to find default device')
			try:
				self._audioOutput = sd.query_devices(kind='output')['name']
			except:
				self.logError('Audio output not found, cannot continue')
				self._audioOutput = 'default'
			self.ConfigManager.updateAliceConfiguration(key='outputDevice', value=self._audioOutput)
		else:
			self._audioOutput = self.ConfigManager.getAliceConfigByName('outputDevice')

		self.setDefaults()

		self._stopPlayingFlag = self.ThreadManager.newEvent('stopPlaying')
		self.MqttManager.mqttClient.subscribe(constants.TOPIC_AUDIO_FRAME.format(self.ConfigManager.getAliceConfigByName('uuid')))


	def onBooted(self):
		if not self.ConfigManager.getAliceConfigByName('disableCapture'):
			self.ThreadManager.newThread(name='audioPublisher', target=self.publishAudio)


	def setDefaults(self):
		self.logInfo(f'Using **{self._audioInput}** for audio input')
		self.logInfo(f'Using **{self._audioOutput}** for audio output')

		sd.default.device = self._audioInput, self._audioOutput


	def onStop(self):
		super().onStop()
		if self._audioInputStream:
			self._audioInputStream.stop(ignore_errors=True)
			self._audioInputStream.close(ignore_errors=True)


	def onHotwordToggleOff(self):
		self._broadcastLocal = False


	def onHotwordToggleOn(self):
		self._broadcastLocal = True


	def recordFrame(self, deviceUid: str, frame: bytes):
		if deviceUid not in self._waves:
			return

		self._waves[deviceUid].writeframes(frame)


	def publishToListener(self, topic: str, payload: Union[dict, str, bytearray] = None, qos: int = 0, retain: bool = False):
		if self._broadcastLocal:
			self.MqttManager.localPublish(topic=topic, payload=payload)
		else:
			self.MqttManager.publish(topic=topic, payload=payload, qos=qos, retain=retain)


	def publishAudio(self):
		"""
		captures the audio and broadcasts it via publishAudioFrames to the topic 'hermes/audioServer/{}/audioFrame'
		furthermore it will publish VAD_UP and VAD_DOWN when detected
		:return:
		"""
		self.logInfo('Starting audio publisher')
		self._audioInputStream = sd.RawInputStream(
			dtype='int16',
			channels=1,
			samplerate=self.SAMPLERATE,
			blocksize=self.FRAMES_PER_BUFFER,
		)
		self._audioInputStream.start()

		speech = False
		silence = self.SAMPLERATE / self.FRAMES_PER_BUFFER
		speechFrames = 0
		minSpeechFrames = round(silence / 3)

		while True:
			if self.ProjectAlice.shuttingDown:
				break

			try:
				frames = self._audioInputStream.read(frames=self.FRAMES_PER_BUFFER)[0]

				if self._vad.is_speech(frames, self.SAMPLERATE):
					if not speech and speechFrames < minSpeechFrames:
						speechFrames += 1
					elif speechFrames >= minSpeechFrames:
						self.publishToListener(
								topic=constants.TOPIC_VAD_UP.format(self.ConfigManager.getAliceConfigByName('uuid')),
								payload={
									'siteId': self.ConfigManager.getAliceConfigByName('uuid')
								})
						speech = True
						silence = self.SAMPLERATE / self.FRAMES_PER_BUFFER
						speechFrames = 0
				else:
					if speech:
						if silence > 0:
							silence -= 1
						else:
							speech = False
							self.publishToListener(
									topic=constants.TOPIC_VAD_DOWN.format(self.ConfigManager.getAliceConfigByName('uuid')),
									payload={
										'siteId': self.ConfigManager.getAliceConfigByName('uuid')
									})
					else:
						speechFrames = 0

				self.publishAudioFrames(frames)
			except Exception as e:
				self.logDebug(f'Error publishing frame: {e}')


	def publishAudioFrames(self, frames: bytes):
		"""
		receives some audio frames, adds them to the buffer and publishes them to MQTT
		:param frames:
		:return:
		"""
		with io.BytesIO() as buffer:
			with wave.open(buffer, 'wb') as wav:
				wav.setnchannels(1)
				wav.setsampwidth(2)
				wav.setframerate(self.SAMPLERATE)
				wav.writeframes(frames)

			audioFrames = buffer.getvalue()

			self.publishToListener(topic=constants.TOPIC_AUDIO_FRAME.format(self.ConfigManager.getAliceConfigByName('uuid')), payload=bytearray(audioFrames))


	def onPlayBytes(self, payload: bytearray, deviceUid: str, sessionId: str = None, requestId: str = None):
		if deviceUid != self.ConfigManager.getAliceConfigByName('uuid'):
			return

		requestId = requestId or sessionId or str(uuid.uuid4())

		self._playing = True
		with io.BytesIO(payload) as buffer:
			try:
				with wave.open(buffer, 'rb') as wav:
					channels = wav.getnchannels()
					framerate = wav.getframerate()

					def streamCallback(outdata, frameCount, _timeInfo, _status):
						data = wav.readframes(frameCount)
						if len(data) < len(outdata):
							outdata[:len(data)] = data
							outdata[len(data):] = b'\x00' * (len(outdata) - len(data))
							raise sd.CallbackStop
						else:
							outdata[:] = data

					stream = sd.RawOutputStream(
						dtype='int16',
						channels=channels,
						samplerate=framerate,
						callback=streamCallback
					)

					self.logDebug(f'Playing wav stream using **{self._audioOutput}** audio output (channels: {channels}, rate: {framerate})')
					stream.start()
					while stream.active:
						if self._stopPlayingFlag.is_set():
							stream.stop()
							stream.close()

							if not sessionId:
								raise PlayBytesStopped

						time.sleep(0.1)

					stream.stop()
					stream.close()
			except PlayBytesStopped:
				self.logDebug('Playing bytes stopped')
			except Exception as e:
				self.logError(f'Playing wav failed with error: {e}')
			finally:
				self.logDebug('Playing bytes finished')
				self._stopPlayingFlag.clear()
				self._playing = False

		# Session id support is not Hermes protocol official
		self.MqttManager.publish(
			topic=constants.TOPIC_PLAY_BYTES_FINISHED.format(deviceUid),
			payload={
				'id'       : requestId,
				'sessionId': sessionId
			}
		)

		self.MqttManager.publish(
			topic=constants.TOPIC_TTS_FINISHED,
			payload={
				'id'       : requestId,
				'sessionId': sessionId,
				'siteId'   : deviceUid
			}
		)


	def stopPlaying(self):
		self._stopPlayingFlag.set()


	def updateAudioDevices(self):
		self._audioInput = self.ConfigManager.getAliceConfigByName('inputDevice')
		self._audioOutput = self.ConfigManager.getAliceConfigByName('outputDevice')
		self.setDefaults()


	@property
	def isPlaying(self) -> bool:
		return self._playing
