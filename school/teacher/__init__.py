# Teacher Agent - AI Agent that teaches student agents

from .agent import TeacherAgent
from .lessons import LessonManager
from .communicator import FileCommunicator

__all__ = ['TeacherAgent', 'LessonManager', 'FileCommunicator']
