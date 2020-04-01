from __future__ import annotations

import functools
import warnings
from typing import Any, Callable

from core.base.SuperManager import SuperManager
from core.util.model.Logger import Logger


def deprecated(func):
	"""
	https://stackoverflow.com/questions/2536307/decorators-in-the-python-standard-lib-deprecated-specifically
	This is a decorator which can be used to mark functions
	as deprecated. It will result in a warning being emitted
	when the function is used.
	"""

	@functools.wraps(func)
	def new_func(*args, **kwargs):
		warnings.simplefilter('always', DeprecationWarning)  # turn off filter
		warnings.warn(f'Call to deprecated function {func.__name__}.',
			category=DeprecationWarning,
			stacklevel=2)
		warnings.simplefilter('default', DeprecationWarning)  # reset filter
		return func(*args, **kwargs)

	return new_func


def Online(func: Callable = None, text: str = 'offline', offlineHandler: Callable = None, returnText: bool = False, catchOnly: bool = False):
	"""
	(return a) decorator to mark a function that requires ethernet.

	This decorator can be used (with or or without parameters) to define
	a function that requires ethernet. In the Default mode without arguments shown
	in the example it will either execute whats in the function or when alice is
	offline ends the dialog with a random offline answer.
	Using the parameters:
		@online(text=<myText>)
	a own text can be used when being offline aswell and using the parameters:
		@online(offlineHandler=<myFunc>)
	a own offline handler can be called, which is helpful when not only endDialog has to be called,
	but some other cleanup is required aswell

	When there is no named argument 'session' of type DialogSession in the arguments of the decorated function,
	the decorator will return the text instead. This behaviour can be enforced aswell using:
		@online(returnText=True)

	:param catchOnly: If catch only, do not raise anything
	:param func:
	:param text:
	:param offlineHandler:
	:param returnText:
	:return: return value of function or random offline string in the current language
	Examples:
		An intent that requires ethernet can be defined the following way:

		@online
		def exampleIntent(self, session: DialogSession, **_kwargs):
			request = requests.get('http://api.open-notify.org')
			self.endDialog(sessionId=session.sessionId, text=request.text)
	"""
	def argumentWrapper(func):
		@functools.wraps(func)
		def offlineDecorator(*args, **kwargs):
			internetManager = SuperManager.getInstance().internetManager
			if internetManager.online:
				try:
					return func(*args, **kwargs)
				except:
					if internetManager.checkOnlineState():
						raise

			if catchOnly:
				return

			return offlineHandler(*args, **kwargs)

		return offlineDecorator

	return argumentWrapper(func) if func else argumentWrapper


def IfSetting(func: Callable = None, settingName: str = None, settingValue: Any = None, inverted: bool = False, skillName: str = None):
	"""
	Checks wheter a setting is equal to the given value before executing the wrapped method
	If the setting is not equal to the given value, the wrapped method is not called
	By providing a skill name the wrapper searches for a skill setting, otherwise for a system setting
	By setting inverted to True one can check for "not equal to", in other words, if the settingName is not equal to the settingValue
	:param func:
	:param settingName:
	:param settingValue:
	:param inverted:
	:param skillName:
	:return:
	"""


	def argumentWrapper(func: Callable):
		@functools.wraps(func)
		def settingDecorator(*args, **kwargs):
			if not settingName:
				Logger(prepend='[Decorator]').logWarning(msg='Cannot use IfSetting decorator without settingName')
				return None

			configManager = SuperManager.getInstance().configManager
			value = configManager.getSkillConfigByName(skillName, settingName) if skillName else configManager.getAliceConfigByName(settingName)

			if value is None:
				return None

			if not inverted and value == settingValue:
				return func(*args, **kwargs)
			elif inverted and value != settingValue:
				return func(*args, **kwargs)


		return settingDecorator


	return argumentWrapper(func) if func else argumentWrapper
