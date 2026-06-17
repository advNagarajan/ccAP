from app.services.notification.slack import SlackNotificationChannel
from app.services.notification.smtp import SmtpNotificationChannel

# Pluggable channels list
NOTIFICATION_CHANNELS = [
    SlackNotificationChannel(),
    SmtpNotificationChannel()
]
