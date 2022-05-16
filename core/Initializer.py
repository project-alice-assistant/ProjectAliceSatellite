import getpass
import json
import socket
import subprocess
import logging
import time
import sys
from pathlib import Path

import requests

from core.base.model.Version import Version


PIP = './venv/bin/pip'
YAML = '/boot/ProjectAliceSatellite.yaml'
ASOUND = '/etc/asound.conf'
VENV = 'venv/'
TEMP = Path('/tmp/service')
VERSION = 1.01
PYTHON = 'python3.7'


class SimpleLogger(object):

	def __init__(self, prepend: str = None):
		self._prepend = f'[{prepend}]'
		self._logger = logging.getLogger('ProjectAlice')


	def logInfo(self, text: str):
		self._logger.info(f'{self.spacer(text)}')


	def logWarning(self, text: str):
		self._logger.warning(f'{self.spacer(text)}')


	def logError(self, text: str):
		self._logger.error(f'{self.spacer(text)}')


	def logFatal(self, text: str):
		self._logger.fatal(f'{self.spacer(text)}')
		exit(1)


	def spacer(self, msg: str) -> str:
		space = ''.join([' ' for _ in range(35 - len(self._prepend) + 1)])
		msg = f'{self._prepend}{space}{msg}'
		return msg

class InitDict(dict):

	def __init__(self, default: dict):
		super().__init__(default)


	def __getitem__(self, item):
		try:
			return super().__getitem__(item) or ''
		except:
			print(f'Missing key "{item}" in provided yaml file.')
			return ''

class PreInit(object):
	"""
	Pre init checks and makes sure vital stuff is installed and running. Not much, but internet, venv and so on
	Pre init is meant to run on the system python and not on the venv
	"""

	PIP = './venv/bin/pip'


	def __init__(self):
		self._logger = SimpleLogger(prepend='PreInitializer')

		self.rootDir = Path(__file__).resolve().parent.parent
		self.confsFile = Path(self.rootDir, 'config.json')
		self.initFile = Path(YAML)
		self.initConfs = dict()

		self.oldConfFile = Path(self.rootDir, 'config.py')


	def start(self):
		if not self.initFile.exists() and not self.confsFile.exists() and not self.oldConfFile.exists():
			self._logger.logFatal('Init file not found and there\'s no configuration file, aborting Project Alice start')
			return False

		if not self.confsFile.exists() and self.oldConfFile.exists():
			self._logger.logFatal('Found old conf file, trying to migrate...')
			try:
				# noinspection PyPackageRequirements,PyUnresolvedReferences
				import config.py

				self.confsFile.write_text(json.dumps(config.settings, indent='\t', ensure_ascii=False, sort_keys=True))
			except:
				self._logger.logFatal('Something went wrong migrating the old configs, aborting')
			return False

		elif not self.initFile.exists():
			self._logger.logInfo('No initialization needed')
			return False

		self.initConfs = self.loadConfig()
		self.checkWPASupplicant()
		self.checkInternet()
		self.installSystemDependencies()
		#self.doUpdates()
		#self.installSystemDependencies()
		if not self.checkVenv():
			self.setServiceFileTo('venv')
			subprocess.run(['sudo', 'systemctl', 'enable', 'ProjectAlice'])
			subprocess.run(['sudo', 'systemctl', 'restart', 'ProjectAlice'])
			exit(0)

		return True


	def informUser(self):
		self._logger.logInfo('I am now restarting and will use my service file. To continue checking what I do, please type "tail -f /var/log/syslog"')


	def installSystemDependencies(self):
		reqs = [line.rstrip('\n') for line in open(Path(self.rootDir, 'sysrequirements.txt'))]
		subprocess.run(['sudo', 'apt-get', 'install', '-y', '--allow-unauthenticated'] + reqs)


	def loadConfig(self) -> dict:

		try:
			import yaml
		except:
			#subprocess.run(['sudo', 'apt-get', 'update'])
			subprocess.run(['sudo', 'apt-get', 'update'])
			#subprocess.run(['sudo', 'apt-get', 'install', 'python3-pip', 'python3-wheel', '-y'])
			subprocess.run(['sudo', 'apt-get', 'install', 'python3-pip', 'python3-wheel', '-y'])
			subprocess.run(['pip3', 'install', 'PyYAML==5.3.1'])

			self.setServiceFileTo('system')
			subprocess.run(['sudo', 'systemctl', 'enable', 'ProjectAlice'])
			subprocess.run(['sudo', 'systemctl', 'restart', 'ProjectAlice'])
			self.informUser()
			exit(0)

		with Path(YAML).open(mode='r') as f:
			try:
				# noinspection PyUnboundLocalVariable
				load = yaml.safe_load(f)
				initConfs = InitDict(load)
				# Check that we are running using the latest yaml
				if float(initConfs['version']) < VERSION:
					self._logger.logFatal('The yaml file you are using is deprecated. Please update it before trying again')

			except yaml.YAMLError as e:
				self._logger.logFatal(f'Failed loading init configurations: {e}')

			return initConfs


	@staticmethod
	def isVenv() -> bool:
		return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)


	def checkWPASupplicant(self):
		wpaSupplicant = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
		if not wpaSupplicant.exists() and self.initConfs['useWifi']:
			self._logger.logInfo('Setting up wifi')

			if not self.initConfs['wifiCountryCode'] or not self.initConfs['wifiNetworkName'] or not self.initConfs['wifiWPAPass']:
				self._logger.logFatal('You must specify the wifi parameters')

			bootWpaSupplicant = Path('/boot/wpa_supplicant.conf')

			wpaFile = Path('wpa_supplicant.conf').read_text() \
				.replace('%wifiCountryCode%', str(self.initConfs['wifiCountryCode'])) \
				.replace('%wifiNetworkName%', str(self.initConfs['wifiNetworkName'])) \
				.replace('%wifiWPAPass%', str(self.initConfs['wifiWPAPass']))

			file = Path(self.rootDir, 'wifi.conf')
			file.write_text(wpaFile)

			subprocess.run(['sudo', 'mv', str(file), bootWpaSupplicant])
			self._logger.logInfo('Successfully initialized wpa_supplicant.conf')
			self.reboot()


	def doUpdates(self):
		subprocess.run(['git', 'config', '--global', 'user.name', '"An Other"'])
		subprocess.run(['git', 'config', '--global', 'user.email', '"anotheruser@projectalice.io"'])

		updateChannel = self.initConfs['aliceUpdateChannel'] if 'aliceUpdateChannel' in self.initConfs else 'master'
		updateSource = self.getUpdateSource(updateChannel)
		# Update our system and sources
		subprocess.run(['sudo', 'apt-get', 'update'])
		#subprocess.run(['sudo', 'apt-get', 'dist-upgrade', '-y'])
		subprocess.run(['sudo', 'apt', 'autoremove', '-y'])
		subprocess.run(['git', 'clean', '-df'])
		subprocess.run(['git', 'stash'])

		result = subprocess.run(['git', 'checkout', updateSource], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if 'switched' in result.stderr.decode().lower():
			print('Switched branch, restarting...')
			self.restart()

		result = subprocess.run(['git', 'pull'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if 'core/initializer.py' in result.stdout.decode().lower():
			print('Updated critical sources, restarting...')
			self.restart()

		subprocess.run(['git', 'stash', 'clear'])

		#subprocess.run(['git', 'submodule', 'init'])
		#subprocess.run(['git', 'submodule', 'update'])
		#subprocess.run(['git', 'submodule', 'foreach', 'git', 'checkout', f'builds_{str(updateSource)}'])
		#subprocess.run(['git', 'submodule', 'foreach', 'git', 'pull'])


	@staticmethod
	def reboot():
		time.sleep(1)
		subprocess.run(['sudo', 'shutdown', '-r', 'now'])
		exit(0)


	def restart(self):
		sys.stdout.flush()
		try:
			# Close everything related to ProjectAlice, allows restart without component failing
			try:
				# noinspection PyUnresolvedReferences
				import psutil
			except:
				self.setServiceFileTo('system')
				subprocess.run(['sudo', 'systemctl', 'restart', 'ProjectAlice'])
				self.informUser()
				exit(0)

			# noinspection PyUnboundLocalVariable
			process = psutil.Process(os.getpid())
			for handler in process.open_files() + process.connections():
				os.close(handler.fd)
		except Exception as e:
			print(f'Failed restarting Project Alice: {e}')

		python = sys.executable
		os.execl(python, python, *sys.argv)


	def checkInternet(self):
		try:
			socket.create_connection(('www.google.com', 80))
			connected = True
		except:
			connected = False

		if not connected:
			self._logger.logFatal('Your device needs internet access to continue')


	def getUpdateSource(self, definedSource: str) -> str:
		updateSource = 'master'
		if definedSource in {'master', 'release'}:
			return updateSource

		try:
			import requests
		except:
			self.setServiceFileTo('system')
			subprocess.run(['sudo', 'systemctl', 'restart', 'ProjectAlice'])
			self.informUser()
			exit(0)

		# noinspection PyUnboundLocalVariable
		req = requests.get('https://api.github.com/repos/project-alice-assistant/ProjectAliceSatellite/branches')
		result = req.json()

		versions = list()
		from core.base.model.Version import Version

		for branch in result:
			repoVersion = Version.fromString(branch['name'])

			releaseType = repoVersion.releaseType
			if not repoVersion.isVersionNumber \
					or definedSource == 'rc' and releaseType in {'b', 'a'} \
					or definedSource == 'beta' and releaseType == 'a':
				continue

			versions.append(repoVersion)

		if versions:
			versions.sort(reverse=True)
			updateSource = versions[0]

		return str(updateSource)


	def checkVenv(self) -> bool:
		if not Path('venv').exists():
			self._logger.logInfo('Not running with venv, I need to create it')
			subprocess.run(['sudo', 'apt-get', 'install', 'python3-dev', 'python3-pip', 'python3-venv', 'python3-wheel', '-y'])
			subprocess.run([PYTHON, '-m', 'venv', 'venv'])
			self.updateVenv()
			self._logger.logInfo('Installed virtual environment, restarting...')
			return False
		elif not self.isVenv():
			self.updateVenv()
			self._logger.logWarning('Restarting to run using virtual environment: "./venv/bin/python main.py"')
			return False

		return True


	def updateVenv(self):
		subprocess.run([self.PIP, 'uninstall', '-y', '-r', str(Path(self.rootDir, 'pipuninstalls.txt'))])
		subprocess.run([self.PIP, 'install', 'wheel'])
		subprocess.run([self.PIP, 'install', '-r', str(Path(self.rootDir, 'requirements.txt')), '--upgrade', '--no-cache-dir'])


	@staticmethod
	def setServiceFileTo(pointer: str):
		serviceFilePath = Path('/etc/systemd/system/ProjectAlice.service')
		if serviceFilePath.exists():
			subprocess.run(['sudo', 'rm', serviceFilePath])

		serviceFile = Path('ProjectAlice.service').read_text()

		if pointer == 'venv':
			serviceFile = serviceFile.replace('#EXECSTART', f'ExecStart=/home/{getpass.getuser()}/ProjectAlice/venv/bin/python main.py')
		else:
			serviceFile = serviceFile.replace('#EXECSTART', f'ExecStart=python3 main.py')

		serviceFile = serviceFile.replace('#WORKINGDIR', f'WorkingDirectory=/home/{getpass.getuser()}/ProjectAlice')
		serviceFile = serviceFile.replace('#USER', f'User={getpass.getuser()}')
		TEMP.write_text(serviceFile)
		subprocess.run(['sudo', 'mv', TEMP, serviceFilePath])
		subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
		time.sleep(1)


class Initializer(object):

	_WPA_FILE = '''country=%wifiCountryCode%
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="%wifiNetworkName%"
    scan_ssid=1
    psk="%wifiWPAPass%"
    key_mgmt=WPA-PSK
}
	'''


	def __init__(self):
		super().__init__()
		self._logger = SimpleLogger('Initializer')
		self._logger.logInfo('Starting Project Alice Satellite initialization')
		self._preInit = PreInit()

		self._rootDir = Path(__file__).resolve().parent.parent

		self._confsFile = Path(self._rootDir, 'config.json')
		self._confsSample = Path(self._rootDir, 'configTemplate.json')
		self._initFile = Path(YAML)
		self._latest = 1.01


	def logInfo(self, msg):
		self._logger.logInfo(msg)


	def logFatal(self, msg):
		self._logger.logFatal(msg)


	def logWarning(self, msg):
		self._logger.logWarning(msg)


	def initProjectAlice(self) -> bool:

		if not self._preInit.start():
			return False

		if not self._initFile.exists() and not self._confsFile.exists():
			self.logFatal('Init file not found and there\'s no configuration file, aborting Project Alice start')
		elif not self._initFile.exists():
			self.logInfo('No initialization needed')
			return False

		if not Path(VENV).exists():
			self.logInfo('VENV missing - creating new')
			#subprocess.run(['sudo', 'apt-get', 'update'])
			subprocess.run(['sudo', 'apt-get', 'install', 'python3-pip', 'python3-wheel', 'python3-venv', '-y'])
			subprocess.run(['python3', '-m', 'install', VENV])
			doGroundInstall = True
		else:
			self.logInfo('VENV exists. Continue.')
			subprocess.run([PIP, 'uninstall', '-y', '-r', str(Path(self._rootDir, 'pipuninstalls.txt'))])

		try:
			import yaml
		except:
			subprocess.run([PIP, 'install', 'pyyaml'])
			import yaml

		with self._initFile.open(mode='r') as f:
			try:
				load = yaml.safe_load(f)
				if not load:
					raise yaml.YAMLError

				initConfs = InitDict(load)
			except yaml.YAMLError as e:
				self.logFatal(f'Failed loading init configurations: {e}')

		# Check that we are running using the latest yaml
		if float(initConfs['version']) < self._latest:
			self.logFatal('The yaml file you are using is deprecated. Please update it before trying again')

		wpaSupplicant = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
		if not wpaSupplicant.exists() and initConfs['useWifi']:
			self.logInfo('Setting up wifi')

			if not initConfs['wifiCountryCode'] or not initConfs['wifiNetworkName'] or not initConfs['wifiWPAPass']:
				self.logFatal('You must specify the wifi parameters')

			bootWpaSupplicant = Path('/boot/wpa_supplicant.conf')

			wpaFile = self._WPA_FILE \
				.replace('%wifiCountryCode%', str(initConfs['wifiCountryCode'])) \
				.replace('%wifiNetworkName%', str(initConfs['wifiNetworkName'])) \
				.replace('%wifiWPAPass%', str(initConfs['wifiWPAPass']))

			file = Path(self._rootDir, 'wifi.conf')
			file.write_text(wpaFile)

			subprocess.run(['sudo', 'mv', str(file), bootWpaSupplicant])
			self.logInfo('Successfully initialized wpa_supplicant.conf')
			time.sleep(1)
			subprocess.run(['sudo', 'shutdown', '-r', 'now'])
			exit(0)

		try:
			socket.create_connection(('www.google.com', 80))
			connected = True
		except:
			connected = False

		if not connected:
			self.logFatal('Your device needs internet access to continue')

		updateChannel = initConfs['aliceUpdateChannel'] if 'aliceUpdateChannel' in initConfs else 'master'
		updateSource = self.getUpdateSource(updateChannel)
		# Update our system and sources
		subprocess.run(['git', 'clean', '-df'])
		subprocess.run(['git', 'stash'])
		subprocess.run(['git', 'checkout', updateSource])
		subprocess.run(['git', 'pull'])
		subprocess.run(['git', 'stash', 'clear'])

		time.sleep(1)

		if 'forceRewrite' not in initConfs:
			initConfs['forceRewrite'] = True

		if not self._confsFile.exists() and not self._confsSample.exists():
			self.logFatal('No config and no config template found, can\'t continue')

		elif not self._confsFile.exists() and self._confsSample.exists():
			self.logWarning('No config file found, creating it from sample file')
			self.newConfs()

		elif self._confsFile.exists() and not initConfs['forceRewrite']:
			self.logWarning('Config file already existing and user not wanting to rewrite, aborting')
			return False

		elif self._confsFile.exists() and initConfs['forceRewrite']:
			self.logWarning('Config file found and force rewrite specified, let\'s restart all this!')
			self._confsFile.unlink()
			self.newConfs()


		subprocess.run(['sudo', 'apt-get', 'update'])
		#subprocess.run(['sudo', 'apt-get', 'dist-upgrade', '-y'])
		reqs = [line.rstrip('\n') for line in open(Path(self._rootDir, 'sysrequirements.txt'))]
		subprocess.run(['sudo', 'apt-get', 'install', '-y', '--allow-unauthenticated'] + reqs)

		subprocess.run(['sudo', 'systemctl', 'stop', 'mosquitto'])
		subprocess.run('sudo sed -i -e \'s/persistence true/persistence false/\' /etc/mosquitto/mosquitto.conf'.split())
		subprocess.run(['sudo', 'rm', '/var/lib/mosquitto/mosquitto.db '])
		subprocess.run(['sudo', 'systemctl', 'start', 'mosquitto'])

		confs = json.loads(self._confsFile.read_text())

		# Do some installation if wanted by the user
		if 'doGroundInstall' not in initConfs or initConfs['doGroundInstall'] or doGroundInstall:
			subprocess.run([PIP, 'install', '-r', str(Path(self._rootDir, 'requirements.txt'))])

			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-platform-common_0.64.0_armhf.deb', '-y'])
			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-hotword_0.64.0_armhf.deb', '-y'])
			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-hotword-model-heysnipsv4_0.64.0_armhf.deb', '-y'])

			subprocess.run(['sudo', 'systemctl', 'stop', 'snips-hotword'])
			subprocess.run(['sudo', 'systemctl', 'disable', 'snips-hotword'])

		confs['ssid'] = initConfs['wifiNetworkName']
		confs['wifipassword'] = str(initConfs['wifiWPAPass'])
		confs['useHLC'] = bool(initConfs['useHLC'])

		aliceUpdateChannel = initConfs['aliceUpdateChannel']
		if aliceUpdateChannel not in {'master', 'rc', 'beta', 'alpha'}:
			self.logWarning(f'{aliceUpdateChannel} is not a supported updateChannel, only master, rc, beta and alpha are supported. Reseting to master')
			confs['aliceUpdateChannel'] = 'master'
		else:
			confs['aliceUpdateChannel'] = aliceUpdateChannel

		serviceFilePath = Path('/etc/systemd/system/ProjectAlice.service')
		if not serviceFilePath.exists():
			subprocess.run(['sudo', 'cp', 'ProjectAlice.service', serviceFilePath])

		subprocess.run(['sudo', 'sed', '-i', '-e', f's/\#WORKINGDIR/WorkingDirectory=\/home\/{getpass.getuser()}\/ProjectAlice/', str(serviceFilePath)])
		subprocess.run(['sudo', 'sed', '-i', '-e', f's/\#EXECSTART/ExecStart=\/home\/{getpass.getuser()}\/ProjectAlice\/venv\/bin\/python3 main.py/', str(serviceFilePath)])
		subprocess.run(['sudo', 'sed', '-i', '-e', f's/\#USER/User={getpass.getuser()}/', str(serviceFilePath)])

		self.logInfo('Installing audio hardware')
		audioHardware = ''
		for hardware in initConfs['audioHardware']:
			if initConfs['audioHardware'][hardware]:
				audioHardware = hardware
				break

		hlcServiceFilePath = Path('/etc/systemd/system/hermesledcontrol.service')
		if initConfs['useHLC']:

			if not Path('/home', getpass.getuser(), 'hermesLedControl').exists():
				subprocess.run(['git', 'clone', 'https://github.com/project-alice-assistant/hermesLedControl.git', str(Path('/home', getpass.getuser(), 'hermesLedControl'))])
			else:
				subprocess.run(['git', '-C', str(Path('/home', getpass.getuser(), 'hermesLedControl')), 'stash'])
				subprocess.run(['git', '-C', str(Path('/home', getpass.getuser(), 'hermesLedControl')), 'pull'])
				subprocess.run(['git', '-C', str(Path('/home', getpass.getuser(), 'hermesLedControl')), 'stash', 'clear'])

			if not hlcServiceFilePath.exists():
				subprocess.run(['sudo', 'cp', f'/home/{getpass.getuser()}/hermesLedControl/hermesledcontrol.service', str(hlcServiceFilePath)])

			subprocess.run(['sudo', 'sed', '-i', '-e', f's/%WORKING_DIR%/\/home\/{getpass.getuser()}\/hermesLedControl/', str(hlcServiceFilePath)])
			subprocess.run(['sudo', 'sed', '-i', '-e', f's/%EXECSTART%/\/home\/{getpass.getuser()}\/hermesLedControl\/venv\/bin\/python3 main.py --hardware=%HARDWARE% --pattern=projectalice/', str(hlcServiceFilePath)])
			subprocess.run(['sudo', 'sed', '-i', '-e', f's/%USER%/{getpass.getuser()}/', str(hlcServiceFilePath)])

		if audioHardware in {'respeaker2', 'respeaker4', 'respeaker6MicArray'}:
			subprocess.run(['sudo', Path(self._rootDir, 'system/scripts/audioHardware/respeakers.sh')])
			if initConfs['useHLC']:
				subprocess.run(['sudo', 'sed', '-i', '-e', f's/%HARDWARE%/{audioHardware}/', str(hlcServiceFilePath)])

			if audioHardware == 'respeaker6MicArray':
				subprocess.run(['sudo', 'cp', Path(self._rootDir, 'system', 'asounds', 'respeaker6micarray.conf'), Path(ASOUND)])

		elif audioHardware == 'respeaker7':
			subprocess.run(['sudo', Path(self._rootDir, 'system/scripts/audioHardware/respeaker7.sh')])
			if initConfs['useHLC']:
				subprocess.run(['sudo', 'sed', '-i', '-e', 's/%HARDWARE%/respeaker7MicArray/', str(hlcServiceFilePath)])

		elif audioHardware == 'respeakerCoreV2':
			subprocess.run(['sudo', Path(self._rootDir, 'system/scripts/audioHardware/respeakerCoreV2.sh')])
			if initConfs['useHLC']:
				subprocess.run(['sudo', 'sed', '-i', '-e', f's/%HARDWARE%/{audioHardware}/', str(hlcServiceFilePath)])

		elif audioHardware in {'matrixCreator', 'matrixVoice'}:
			subprocess.run(['sudo', Path(self._rootDir, 'system/scripts/audioHardware/matrix.sh')])
			subprocess.run(['sudo', 'cp', Path(self._rootDir, 'system', 'asounds', 'matrix.conf'), Path(ASOUND)])

			if initConfs['useHLC']:
				subprocess.run(['sudo', 'sed', '-i', '-e', f's/%HARDWARE%/{audioHardware.lower()}/', str(hlcServiceFilePath)])

		elif audioHardware == 'googleAIY':
			subprocess.run(['sudo', Path(self._rootDir, 'system/scripts/audioHardware/aiy.sh')])
			if initConfs['useHLC']:
				subprocess.run(['sudo', 'sed', '-i', '-e', 's/%HARDWARE%/googleAIY/', str(hlcServiceFilePath)])

		elif audioHardware == 'usbMic':
			subprocess.run(['sudo', 'cp', Path(self._rootDir, 'system', 'asounds', 'usbmic.conf'), Path(ASOUND)])

		elif audioHardware == 'ps3eye':
			subprocess.run(['sudo', 'cp', Path(self._rootDir, 'system', 'asounds', 'ps3eye.conf'), Path(ASOUND)])
			asoundrc = f'/home/{getpass.getuser()}/.asoundrc'
			subprocess.run(['echo', 'pcm.dsp0 {', '>', asoundrc])
			subprocess.run(['echo', '    type plug', '>>', asoundrc])
			subprocess.run(['echo', '    slave.pcm "dmix"', '>>', asoundrc])
			subprocess.run(['echo', '}', '>>', asoundrc])

		subprocess.run(['sudo', 'systemctl', 'daemon-reload'])

		sort = dict(sorted(confs.items()))

		try:
			self._confsFile.write_text(json.dumps(sort, ensure_ascii=False, indent='\t'))
		except Exception as e:
			self.logFatal(f'An error occurred while writing final configuration file: {e}')

		if initConfs['keepYAMLBackup']:
			subprocess.run(['sudo', 'mv', Path(YAML), Path('/boot/ProjectAliceSatellite.yaml.bak')])
		else:
			subprocess.run(['sudo', 'rm', Path(YAML)])

		self.logWarning('Initializer done with configuring')
		time.sleep(2)
		subprocess.run(['sudo', 'systemctl', 'enable', 'ProjectAlice'])
		subprocess.run(['sudo', 'shutdown', '-r', 'now'])


	@staticmethod
	def getUpdateSource(definedSource: str) -> str:
		updateSource = 'master'
		if definedSource == 'master':
			return updateSource

		req = requests.get('https://api.github.com/repos/project-alice-assistant/ProjectAliceSatellite/branches')
		result = req.json()

		versions = list()
		for branch in result:
			repoVersion = Version.fromString(branch['name'])

			releaseType = repoVersion.releaseType
			if not repoVersion.isVersionNumber \
					or definedSource == 'rc' and releaseType in {'b', 'a'} \
					or definedSource == 'beta' and releaseType == 'a':
				continue

			versions.append(repoVersion)

		if versions:
			versions.sort(reverse=True)
			updateSource = versions[0]

		return str(updateSource)


	def newConfs(self):
		self._confsFile.write_text(json.dumps({configName: configData['defaultValue'] for configName, configData in json.loads(self._confsSample.read_text()).items()}, indent='\t', ensure_ascii=False))
