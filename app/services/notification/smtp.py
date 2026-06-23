import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.notification.base import BaseNotificationChannel
from app.models.db.notification_recipient import NotificationRecipient
from app.core.settings import settings

logger = logging.getLogger("smtp_notifier")

class SmtpNotificationChannel(BaseNotificationChannel):

    def send_message(
        self,
        subject: str,
        message: str,
        db: Session,
        details: dict = None
    ) -> None:
        # 1. Fetch active recipients dynamically from the metadata database, filtered by topic
        topic = (details or {}).get("topic")
        is_sqlite = db.bind is not None and db.bind.dialect.name == "sqlite"

        if is_sqlite:
            # Standalone/test databases (like SQLite) don't support Postgres ARRAY operations
            query_res = db.execute(
                select(NotificationRecipient.email, NotificationRecipient.subscribed_topics)
                .where(NotificationRecipient.is_active == True)
            ).all()
            if topic:
                recipients = [row[0] for row in query_res if topic in row[1]]
            else:
                recipients = [row[0] for row in query_res]
        else:
            if topic:
                recipients = db.execute(
                    select(NotificationRecipient.email)
                    .where(
                        NotificationRecipient.is_active == True,
                        NotificationRecipient.subscribed_topics.any(topic)
                    )
                ).scalars().all()
            else:
                recipients = db.execute(
                    select(NotificationRecipient.email)
                    .where(NotificationRecipient.is_active == True)
                ).scalars().all()

        if not recipients:
            logger.warning(
                f"No active email recipients found in metadata DB. "
                f"SMTP notification for '{subject}' skipped."
            )
            return

        sender = settings.NOTIFICATION_EMAIL_SENDER or "no-reply@example.com"
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT
        user = settings.SMTP_USER
        password = settings.SMTP_PASSWORD

        if not host:
            logger.warning(
                f"[STUB] SMTP Email Notification: '{subject}' to recipients={recipients} -> {message}. "
                "SMTP_HOST is not configured."
            )
            return

        try:
            # 2. Build email headers and body MIME structure
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)

            html = f"""
            <html>
              <body>
                <h2>{subject}</h2>
                <p>{message}</p>
                {f'<pre>{details}</pre>' if details else ''}
              </body>
            </html>
            """
            msg.attach(MIMEText(message, "plain"))
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if port == 587:
                    server.starttls()
                    server.ehlo()
                if user and password:
                    server.login(user, password)
                server.sendmail(sender, recipients, msg.as_string())
                
            logger.info(f"Successfully sent email notification '{subject}' to {recipients}")
        except Exception as e:
            logger.error(f"Failed to send email notification '{subject}' via SMTP: {e}")
            raise
