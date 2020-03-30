import typing

from core.util.model.Logger import Logger


class _ProjectAliceException(Exception):

	def __init__(self, message: str = None, status: int = None, context: list = None):
		self._logger = Logger()
		self._message = message
		self._status = status
		self._context = context
		super().__init__(message)


	@property
	def message(self) -> str:
		return self._message


	@property
	def status(self) -> typing.Optional[int]:
		return self._status


	@property
	def context(self) -> typing.Optional[list]:
		return self._context


class FunctionNotImplemented(_ProjectAliceException):

	def __init__(self, clazz: str, funcName: str):
		self._logger.logError(f'{funcName} must be implemented in {clazz}!')


class HttpError(_ProjectAliceException):

	def __init__(self, status: int, message: str, context: list):
		super().__init__(message, status, context)


class OfflineError(_ProjectAliceException): pass


class DbConnectionError(_ProjectAliceException): pass


class InvalidQuery(_ProjectAliceException): pass


class ConfigurationUpdateFailed(_ProjectAliceException): pass
