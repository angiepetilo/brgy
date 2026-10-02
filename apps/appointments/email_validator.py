import urllib.request
import urllib.parse
import json
import re
import socket
import logging

logger = logging.getLogger(__name__)

ABSTRACT_API_KEY = "a1a378425838442abcee4f5af6805e83"
ABSTRACT_API_URL = "https://emailvalidation.abstractapi.com/v1/"

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
    Validates email address using Abstract API Email Validation with API key:
    a1a378425838442abcee4f5af6805e83.
    Verifies that the email is a real, active personal/business email account,
    rejecting disposable emails, randomized bot addresses, and nonexistent domains.
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

    # Reject known disposable domains immediately
    if domain in DISPOSABLE_DOMAINS:
        return False, "Disposable and temporary email addresses are not permitted. Please use a real email.", {}

    # Check for randomized bot patterns (e.g. long random alphanumeric string or lack of vowels)
    if re.match(r'^[a-f0-9]{16,}$', user_part, re.IGNORECASE) or (len(user_part) >= 12 and not any(c in 'aeiouy' for c in user_part.lower())):
        return False, "Automated or randomized bot email detected. Please provide your real personal email.", {}

    # 1. Attempt validation via Abstract API Email Validation service
    try:
        query_params = urllib.parse.urlencode({
            'api_key': ABSTRACT_API_KEY,
            'email': email
        })
        request_url = f"{ABSTRACT_API_URL}?{query_params}"
        req = urllib.request.Request(request_url, headers={'User-Agent': 'BarangayPortal/1.0'})

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))

                # Check deliverability
                deliverability = data.get('deliverability')
                if deliverability == 'UNDELIVERABLE':
                    return False, "This email address was determined to be undeliverable. Please check for typos.", data

                # Check disposable flag
                is_disposable = data.get('is_disposable_email')
                if isinstance(is_disposable, dict) and is_disposable.get('value') is True:
                    return False, "Disposable/temporary email accounts are not accepted.", data
                elif is_disposable is True:
                    return False, "Disposable/temporary email accounts are not accepted.", data

                # Check format validity
                is_valid_format = data.get('is_valid_format')
                if isinstance(is_valid_format, dict) and is_valid_format.get('value') is False:
                    return False, "The email address format is invalid.", data

                # Check quality score if present
                quality_score = data.get('quality_score')
                if quality_score is not None:
                    try:
                        if float(quality_score) < 0.20:
                            return False, "This email was flagged as suspicious or low quality.", data
                    except (ValueError, TypeError):
                        pass

                return True, "Email verified successfully via Abstract API.", data
    except urllib.error.HTTPError as e:
        logger.warning(f"Abstract API returned HTTP {e.code}: {e.reason}")
    except Exception as e:
        logger.warning(f"Abstract API connection error: {e}")

    # 2. Resilient Fallback: Domain existence check via socket
    try:
        socket.getaddrinfo(domain, 80)
    except socket.gaierror:
        return False, f"The email domain '@{domain}' does not exist or cannot be reached.", {}
    except Exception:
        pass

    return True, "Email validated successfully.", {'fallback': True}
