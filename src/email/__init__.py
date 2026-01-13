"""Email fetching and processing module."""

from src.email.client import EmailClient
from src.email.filters import EmailFilter
from src.email.models import Email, EmailAddress, MailFolder

__all__ = ["EmailClient", "EmailFilter", "Email", "EmailAddress", "MailFolder"]
