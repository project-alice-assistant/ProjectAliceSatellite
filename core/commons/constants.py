#  Copyright (c) 2021
#
#  This file, constants.py, is part of Project Alice.
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
#  Last modified: 2021.04.13 at 12:56:46 CEST

VERSION                         = '1.0.0-rc1'
DEVICETYPE                      = 'ProjectAliceSatellite'

PYTHON                          = 'python3.7'

DEFAULT_SITE_ID                 = 'default'
DEFAULT                         = 'default'
DUMMY                           = 'dummy'
UNKNOWN                         = 'unknown'
UNKNOWN_MANAGER                 = 'unknownManager'
UNKNOWN_USER                    = 'unknownUser'

DATABASE_FILE                   = 'system/database/data.db'
GITHUB_URL                      = 'https://github.com/project-alice-assistant'
GITHUB_RAW_URL                  = 'https://raw.githubusercontent.com/project-alice-assistant'
GITHUB_API_URL                  = 'https://api.github.com/repos/project-alice-assistant'
GITHUB_REPOSITORY_ID            = 250856660

TOPIC_ASR_START_LISTENING       = 'hermes/asr/startListening'
TOPIC_ASR_STOP_LISTENING        = 'hermes/asr/stopListening'
TOPIC_AUDIO_FRAME               = 'hermes/audioServer/{}/audioFrame'
TOPIC_CLEAR_LEDS                = 'hermes/leds/clear'
TOPIC_DND_LEDS                  = 'hermes/leds/doNotDisturb'
TOPIC_HOTWORD_DETECTED          = 'hermes/hotword/default/detected'
TOPIC_HOTWORD_TOGGLE_OFF        = 'hermes/hotword/toggleOff'
TOPIC_HOTWORD_TOGGLE_ON         = 'hermes/hotword/toggleOn'
TOPIC_PLAY_BYTES                = 'hermes/audioServer/{}/playBytes/#'
TOPIC_PLAY_BYTES_FINISHED       = 'hermes/audioServer/{}/playFinished'
TOPIC_TTS_FINISHED              = 'hermes/tts/sayFinished'
TOPIC_VAD_DOWN                  = 'hermes/voiceActivity/{}/vadDown'
TOPIC_VAD_UP                    = 'hermes/voiceActivity/{}/vadUp'

TOPIC_ALICE_CONNECTION_ACCEPTED = 'projectalice/devices/connectionAccepted'
TOPIC_ALICE_CONNECTION_REFUSED  = 'projectalice/devices/connectionRefused'
TOPIC_ALICE_GREETING            = 'projectalice/devices/greeting'
TOPIC_CORE_DISCONNECTION        = 'projectalice/devices/coreDisconnection'
TOPIC_CORE_HEARTBEAT            = 'projectalice/devices/coreHeartbeat'
TOPIC_CORE_RECONNECTION         = 'projectalice/devices/coreReconnection'
TOPIC_DEVICE_HEARTBEAT          = 'projectalice/devices/heartbeat'
TOPIC_DEVICE_STATUS             = 'projectalice/devices/status'
TOPIC_DISCONNECTING             = 'projectalice/devices/disconnection'
TOPIC_DND                       = 'projectalice/devices/stopListen'
TOPIC_NEW_HOTWORD               = 'projectalice/devices/alice/newHotword'
TOPIC_STOP_DND                  = 'projectalice/devices/startListen'
TOPIC_TOGGLE_DND                = 'projectalice/devices/toggleListen'

EVENT_ALICE_CONNECTION_ACCEPTED = 'aliceConnectionAccepted'
EVENT_ALICE_CONNECTION_REFUSED  = 'aliceConnectionRefused'
EVENT_AUDIO_FRAME               = 'audioFrame'
EVENT_BOOTED                    = 'booted'
EVENT_DND_OFF                   = 'dndOff'
EVENT_DND_ON                    = 'dndOn'
EVENT_FIVE_MINUTE               = 'fiveMinute'
EVENT_FULL_HOUR                 = 'fullHour'
EVENT_FULL_MINUTE               = 'fullMinute'
EVENT_HOTWORD                   = 'hotword'
EVENT_HOTWORD_TOGGLE_OFF        = 'hotwordToggleOff'
EVENT_HOTWORD_TOGGLE_ON         = 'hotwordToggleOn'
EVENT_PLAY_BYTES                = 'playBytes'
EVENT_PLAY_BYTES_FINISHED       = 'playBytesFinished'
EVENT_QUARTER_HOUR              = 'quarterHour'
EVENT_SKILL_UPDATED             = 'skillUpdated'
EVENT_START_LISTENING           = 'startListening'
EVENT_STOP_LISTENING            = 'stopListening'
EVENT_WAKEWORD                  = 'wakeword'
