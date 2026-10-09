import re
import logging

logger = logging.getLogger(__name__)

DISPOSABLE_DOMAINS = {
    'mailinator.com', 'tempmail.com', '10minutemail.com', 'guerrillamail.com',
    'throwawaymail.com', 'getairmail.com', 'dispostable.com', 'temp-mail.org',
    'yopmail.com', 'burnermail.io', 'trashmail.com', 'sharklasers.com',
    'fakeinbox.com', 'crazymailing.com', 'nada.ltd', 'mohmal.com', 'tempail.com',
    'mytemp.email', 'dropmail.me', 'inboxkitten.com', 'maildrop.cc', 'tempmailo.com',
    'emailondeck.com', 'generator.email', '10mail.org', 'disposablemail.com'
}


def validate_email_address(email: str):
    """
    Validates email address using clean local format and disposable check,
    without external Abstract API network fetching.
    """
    email = (email or '').strip()
    if not email:
        return False, "Email address is required.", {}

    # Basic RFC syntax check
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        return False, "Please enter a valid email format (e.g. name@domain.com).", {}

    user_part, domain = email.split('@', 1)
    domain = domain.lower()

    # Reject known disposable domains
    if domain in DISPOSABLE_DOMAINS:
        return False, "Disposable and temporary email addresses are not permitted. Please use a real email.", {}

    return True, "Email validated successfully.", {'valid_format': True}

