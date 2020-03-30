from enum import Enum, unique

@unique
class State(Enum):
	WAITING_REPLY = 0
	REGISTERED = 1
	REFUSED = 2
	NEW = 3
	BOOTING = 4
	DISCONNECTED = 5
	DORMANT = 6
	ERROR = 7
	ACCEPTED = 8
