import getpass
import importlib
import json
import socket
import subprocess
import time
from pathlib import Path

import requests

from core.base.model.Version import Version

PIP = './venv/bin/pip'
YAML = '/boot/ProjectAliceSatellite.yaml'
ASOUND = '/etc/asound.conf'
VENV = '~/ProjectAlice/venv/'

try:
	import yaml
except:
	subprocess.run([PIP, 'install', 'pyyaml'])
	import yaml

import configTemplate
from core.base.model.ProjectAliceObject import ProjectAliceObject


class InitDict(dict):

	def __init__(self, default: dict):
		super().__init__(default)


	def __getitem__(self, item):
		try:
			return super().__getitem__(item) or ''
		except:
			print(f'Missing key "{item}" in provided yaml file.')
			return ''


class Initializer(ProjectAliceObject):
	NAME = 'ProjectAlice'

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
		self.logInfo('Starting Project Alice Satellite initialization')

		self._rootDir = Path(__file__).resolve().parent.parent

		self._confsFile = Path(self._rootDir, 'config.py')
		self._confsSample = Path(self._rootDir, 'configTemplate.py')
		self._initFile = Path(YAML)
		self._latest = 1.01


	def initProjectAlice(self) -> bool:
		if not self._initFile.exists() and not self._confsFile.exists():
			self.logFatal('Init file not found and there\'s no configuration file, aborting Project Alice start')
		elif not self._initFile.exists():
			self.logInfo('No initialization needed')
			return False

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

		if not Path(VENV).exists:
			subprocess.run(['python3', '-m', 'venv', VENV])
			initConfs['doGroundInstall'] = True
		else:
			subprocess.run([PIP, 'uninstall', '-y', '-r', str(Path(self._rootDir, 'pipuninstalls.txt'))])

		if 'forceRewrite' not in initConfs:
			initConfs['forceRewrite'] = True

		if not self._confsFile.exists() and not self._confsSample.exists():
			self.logFatal('No config and no config template found, can\'t continue')

		elif not self._confsFile.exists() and self._confsSample.exists():
			self.logWarning('No config file found, creating it from sample file')
			confs = self.newConfs()
			self._confsFile.write_text(f"settings = {json.dumps(confs, indent=4).replace('false', 'False').replace('true', 'True')}")

		elif self._confsFile.exists() and not initConfs['forceRewrite']:
			self.logWarning('Config file already existing and user not wanting to rewrite, aborting')
			return False

		elif self._confsFile.exists() and initConfs['forceRewrite']:
			self.logWarning('Config file found and force rewrite specified, let\'s restart all this!')
			self._confsFile.unlink()
			confs = self.newConfs()
			self._confsFile.write_text(f"settings = {json.dumps(confs, indent=4).replace('false', 'False').replace('true', 'True')}")


		subprocess.run(['sudo', 'apt-get', 'update'])
		subprocess.run(['sudo', 'apt-get', 'dist-upgrade', '-y'])
		reqs = [line.rstrip('\n') for line in open(Path(self._rootDir, 'sysrequirements.txt'))]
		subprocess.run(['sudo', 'apt-get', 'install', '-y', '--allow-unauthenticated'] + reqs)

		config = importlib.import_module('config')
		confs = config.settings.copy()

		# Do some installation if wanted by the user
		if 'doGroundInstall' not in initConfs or initConfs['doGroundInstall']:
			subprocess.run([PIP, 'install', '-r', str(Path(self._rootDir, 'requirements.txt'))])

			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-platform-common_0.64.0_armhf.deb', '-y'])
			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-satellite_0.64.0_armhf.deb', '-y'])
			subprocess.run(['sudo', 'apt', 'install', './system/snips/snips-hotword-model-heysnipsv4_0.64.0_armhf.deb', '-y'])

			subprocess.run(['sudo', 'systemctl', 'stop', 'snips-satellite'])
			subprocess.run(['sudo', 'systemctl', 'disable', 'snips-satellite'])

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
			confString = json.dumps(sort, indent=4).replace('false', 'False').replace('true', 'True')
			self._confsFile.write_text(f'settings = {confString}')
		except Exception as e:
			self.logFatal(f'An error occured while writting final configuration file: {e}')
		else:
			importlib.reload(config)

		if initConfs['keepYAMLBackup']:
			subprocess.run(['sudo', 'mv', Path(YAML), Path('/boot/ProjectAlice.yaml.bak')])
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

		req = requests.get('https://api.github.com/repos/project-alice-assistant/ProjectAlice/branches')
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


	@staticmethod
	def newConfs():
		return {configName: configData['values'] if 'dataType' in configData and configData['dataType'] == 'list' else configData['defaultValue'] if 'defaultValue' in configData else configData for configName, configData in configTemplate.settings.items()}
