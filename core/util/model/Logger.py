#  Copyright (c) 2021
#
#  This file, Logger.py, is part of Project Alice.
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
#  Last modified: 2021.04.13 at 12:56:48 CEST

import logging
import re
import traceback
from typing import Match, Union


class Logger(object):

	def __init__(self, prepend: str = None, **_kwargs):
		self._prepend = prepend
		self._logger = logging.getLogger('ProjectAlice')


	def logInfo(self, msg: str, plural: Union[list, str] = None):
		self.doLog(function='info', msg=msg, printStack=False, plural=plural)


	def logError(self, msg: str, plural: Union[list, str] = None):
		self.doLog(function='error', msg=msg, plural=plural)


	def logDebug(self, msg: str, plural: Union[list, str] = None):
		self.doLog(function='debug', msg=msg, printStack=False, plural=plural)


	def logFatal(self, msg: str, plural: Union[list, str] = None):
		self.doLog(function='fatal', msg=msg, plural=plural)
		try:
			from core.base.SuperManager import SuperManager

			SuperManager.getInstance().projectAlice.onStop()
		except:
			exit()


	def logWarning(self, msg: str, printStack: bool = False, plural: Union[list, str] = None):
		from core.base.SuperManager import SuperManager

		if SuperManager.getInstance().ConfigManager.getAliceConfigByName('debug'):
			self.doLog(function='warning', msg=msg, printStack=True, plural=plural)
		else:
			self.doLog(function='warning', msg=msg, printStack=printStack, plural=plural)


	def logCritical(self, msg: str, plural: Union[list, str] = None):
		self.doLog(function='critical', msg=msg, plural=plural)


	def doLog(self, function: str, msg: str, printStack=True, plural: Union[list, str] = None):
		if not msg:
			return

		if plural:
			msg = self.doPlural(string=msg, word=plural)

		if self._prepend:
			msg = f'{self._prepend} {msg}'
		elif not msg.startswith('['):
			msg = f'[Project Alice Logger] {msg}'

		match = re.match(r'^(\[[\w ]+])(.*)$', msg)
		if match:
			tag, log = match.groups()
			space = ''.join([' ' for _ in range(35 - len(tag))])
			msg = f'{tag}{space}{log}'

		func = getattr(self._logger, function)
		func(msg)
		if printStack:
			for line in traceback.format_exc().split('\n'):
				if not line.strip():
					continue
				self.doLog(function=function, msg=f'[Traceback] {line}', printStack=False)


	@staticmethod
	def doPlural(string: str, word: Union[list, str]) -> str:
		def plural(match: Match) -> str:
			matched = match.group()
			if int(match.group(1)) > 1:
				return matched + 's'
			return matched


		words = word
		if isinstance(word, str):
			words = [word]

		for word in words:
			string = re.sub(r'([\d]+)[* ]+?({})'.format(word), plural, string)

		return string
