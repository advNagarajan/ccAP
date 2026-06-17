from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

class BaseNotificationChannel(ABC):

    @abstractmethod
    def send_message(
        self,
        subject: str,
        message: str,
        db: Session,
        details: dict = None
    ) -> None:
        """
        Abstract method to dispatch a notification message through the channel.
        """
        pass
