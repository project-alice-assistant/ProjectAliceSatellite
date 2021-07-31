#  Copyright (c) 2021
#
#  This file, SnipsWakeword.py, is part of Project Alice.
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
#  Last modified: 2021.05.19 at 12:56:48 CEST

import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from core.voice.model.WakewordEngine import WakewordEngine


class SnipsWakeword(WakewordEngine):

	NAME = 'Snips hotword'
	DEPENDENCIES = {
		'system': [
			'snips-hotword',
			'snips-hotword-model-heysnipsv4'
		],
		'pip'   : []
	}


	def installDependencies(self) -> bool:
		installed = self.Commons.runRootSystemCommand(['apt-get', 'install', '-y', f'{self.Commons.rootDir()}/system/snips/snips-hotword_0.64.0_armhf.deb'])
		installed2 = self.Commons.runRootSystemCommand(['apt-get', 'install', '-y', f'{self.Commons.rootDir()}/system/snips/snips-hotword-model-heysnipsv4_0.64.0_armhf.deb'])
		if installed.returncode or installed2.returncode:
			self.logError(f"Couldn't install Snips wakeword: {installed.stderr}")
			return False
		return True


	def onStop(self):
		super().onStop()
		self.SubprocessManager.terminateSubprocess(name='SnipsHotword')


	def onStart(self):
		super().onStart()

		cmd = f'snips-hotword'
		cmd += f' --audio {self.ConfigManager.getAliceConfigByName("uuid")}@mqtt'

		if self.ConfigManager.getMainUnitConfigByName('monoWakewordEngine'):
			cmd += f' --mqtt {self.ConfigManager.getAliceConfigByName("mqttHost")}:{self.ConfigManager.getAliceConfigByName("mqttPort")}'

		if self.ConfigManager.getAliceConfigByName('mqttUser'):
			cmd += f' --mqtt-username {self.ConfigManager.getAliceConfigByName("mqttUser")} --mqtt-password {self.ConfigManager.getAliceConfigByName("mqttPassword")}'

		if self.ConfigManager.getAliceConfigByName('mqttTLSFile'):
			cmd += f' --mqtt-tls-cafile {self.ConfigManager.getAliceConfigByName("mqttTLSFile")}'

		for entry in Path(f'{self.Commons.rootDir()}/trained/hotwords/snips_hotword').glob('*'):
			if not entry.is_dir() or entry.name == '.' or entry.name == '..':
				continue

			cmd += f' --model {entry}=0.5'

		self.SubprocessManager.runSubprocess(name='SnipsHotword', cmd=cmd, autoRestart=True)
