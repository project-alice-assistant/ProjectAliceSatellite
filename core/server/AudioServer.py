import io
import threading
import time
import wave

import pyaudio
from webrtcvad import Vad

from core.ProjectAliceExceptions import PlayBytesStopped
from core.base.model.Manager import Manager
from core.commons import constants


class AudioManager(Manager):
	SAMPLERATE = 16000
	FRAMES_PER_BUFFER = 480


	# Inspired by https://github.com/koenvervloesem/hermes-audio-server

	def __init__(self):
		super().__init__()

		self._stopPlayingFlag = threading.Event()
		self._playing = False
		self._listening = False
		self._aliceListening = False

		if self.ConfigManager.getAliceConfigByName('disableSoundAndMic'):
			return

		with self.Commons.shutUpAlsaFFS():
			self._audio = pyaudio.PyAudio()

		self._vad = Vad(2)

		try:
			self._audioOutput = self._audio.get_default_output_device_info()
		except:
			self.logFatal('Audio output not found, cannot continue')
			return
		else:
			self.logInfo(f'Using **{self._audioOutput["name"]}** for audio output')

		try:
			self._audioInput = self._audio.get_default_input_device_info()
		except:
			self.logFatal('Audio input not found, cannot continue')
		else:
			self.logInfo(f'Using **{self._audioInput["name"]}** for audio input')


	def onStart(self):
		super().onStart()

		if not self.ConfigManager.getAliceConfigByName('disableSoundAndMic'):
			self.ThreadManager.newThread(name='audioPublisher', target=self.publishAudio)


	def onStop(self):
		super().onStop()

		if not self.ConfigManager.getAliceConfigByName('disableSoundAndMic'):
			self._audio.terminate()


	def onHotwordToggleOff(self):
		self._listening = False
		self.MqttManager.mqttLocalClient.loop_stop()


	def onHotwordToggleOn(self):
		self._listening = True
		self._aliceListening = False
		self.MqttManager.mqttLocalClient.loop_start()


	def onHotword(self, user: str = constants.UNKNOWN_USER):
		self.onHotwordToggleOff()


	def onWakeword(self, user: str = constants.UNKNOWN_USER):
		self.onHotwordToggleOff()


	def onStartListening(self):
		self._aliceListening = True


	def onStopListening(self):
		self._aliceListening = False


	def publishAudio(self):
		self.logInfo('Starting audio publisher')
		self._listening = True
		self._aliceListening = False

		audioStream = self._audio.open(
			format=pyaudio.paInt16,
			channels=1,
			rate=self.SAMPLERATE,
			frames_per_buffer=self.FRAMES_PER_BUFFER,
			input=True
		)

		speech = False
		silence = self.SAMPLERATE / self.FRAMES_PER_BUFFER
		speechFrames = 0
		minSpeechFrames = round(silence / 3)

		while True:
			if self.ProjectAlice.shuttingDown:
				break

			try:
				frames = audioStream.read(num_frames=self.FRAMES_PER_BUFFER, exception_on_overflow=False)

				if self._vad.is_speech(frames, self.SAMPLERATE):
					if not speech and speechFrames < minSpeechFrames:
						speechFrames += 1
					elif speechFrames >= minSpeechFrames:
						speech = True
						self.MqttManager.publish(
							topic=constants.TOPIC_VAD_UP.format(self.ConfigManager.getAliceConfigByName('uid')),
							payload={
								'siteId': self.ConfigManager.getAliceConfigByName('uid')
							})
						silence = self.SAMPLERATE / self.FRAMES_PER_BUFFER
						speechFrames = 0
				else:
					if speech:
						if silence > 0:
							silence -= 1
						else:
							speech = False
							self.MqttManager.publish(
								topic=constants.TOPIC_VAD_DOWN.format(self.ConfigManager.getAliceConfigByName('uid')),
								payload={
									'siteId': self.ConfigManager.getAliceConfigByName('uid')
								})
					else:
						speechFrames = 0

				self.publishAudioFrames(frames)
			except Exception as e:
				self.logDebug(f'Error publishing frame: {e}')


	def publishAudioFrames(self, frames: bytes):
		if not self._listening and not self._aliceListening:
			return

		with io.BytesIO() as buffer:
			with wave.open(buffer, 'wb') as wav:
				wav.setnchannels(1)
				wav.setsampwidth(2)
				wav.setframerate(self.SAMPLERATE)
				wav.writeframes(frames)

			audioFrames = buffer.getvalue()

			if self._listening:
				self.MqttManager.localPublish(topic=constants.TOPIC_AUDIO_FRAME.format(self.ConfigManager.getAliceConfigByName('uid')), payload=bytearray(audioFrames))
			elif self._aliceListening:
				self.MqttManager.publish(topic=constants.TOPIC_AUDIO_FRAME.format(self.ConfigManager.getAliceConfigByName('uid')), payload=bytearray(audioFrames))


	def onPlayBytes(self, requestId: str, payload: bytearray, sessionId: str = None):
		if self.ConfigManager.getAliceConfigByName('disableSoundAndMic'):
			return

		self._playing = True
		with io.BytesIO(payload) as buffer:
			try:
				with wave.open(buffer, 'rb') as wav:
					sampleWidth = wav.getsampwidth()
					nFormat = self._audio.get_format_from_width(sampleWidth)
					channels = wav.getnchannels()
					framerate = wav.getframerate()


					def streamCallback(_inData, frameCount, _timeInfo, _status) -> tuple:
						data = wav.readframes(frameCount)
						return data, pyaudio.paContinue


					audioStream = self._audio.open(
						format=nFormat,
						channels=channels,
						rate=framerate,
						output=True,
						stream_callback=streamCallback
					)

					self.logDebug(f'Playing wav stream using **{self._audioOutput["name"]}**')
					audioStream.start_stream()
					while audioStream.is_active():
						if self._stopPlayingFlag.is_set():
							raise PlayBytesStopped
						time.sleep(0.1)

					audioStream.stop_stream()
					audioStream.close()
			except PlayBytesStopped:
				self.logDebug('Playing bytes stopped')
			except Exception as e:
				self.logError(f'Playing wav failed with error: {e}')
			finally:
				self._stopPlayingFlag.clear()
				self._playing = False


	def stopPlaying(self):
		self._stopPlayingFlag.set()


	@property
	def isPlaying(self) -> bool:
		return self._playing
