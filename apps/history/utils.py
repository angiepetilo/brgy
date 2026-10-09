import re
import logging
from django.conf import settings
from django.core.mail import get_connection, EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from apps.history.models import ActivityLog, EmailLog

logger = logging.getLogger(__name__)

SECRET_TEMPLATES = {'reg_approved', 'staff_created'}

PASSWORD_PATTERNS = [
    re.compile(r'(?i)(password\s*[:=]\s*)([^\s,;]+)'),
    re.compile(r'(?i)(temp_password\s*[:=]\s*)([^\s,;]+)'),
    re.compile(r'(?i)(needs_notes\s*[:=]\s*)([^\n,;]+)'),
]


def sanitize_audit_details(details):
    """
    Strips or masks temp_password, password, needs_notes, and sensitive tokens.
    """
    if not details:
        return ''
    text = str(details)
    for pat in PASSWORD_PATTERNS:
        text = pat.sub(r'\1[REDACTED]', text)
    return text


def is_secret_template(template_name):
    clean = str(template_name).replace('\\', '/').split('/')[-1]
    if clean.endswith('.txt'):
        clean = clean[:-4]
    return clean.lower() in SECRET_TEMPLATES


def log_activity(actor, action, action_type, *args, **kwargs):
    """
    Records an immutable audit trail entry in ActivityLog.
    Redacts sensitive keys (passwords, needs_notes).
    """
    try:
        user_actor = actor if (actor and getattr(actor, 'is_authenticated', False)) else None

        target_id = kwargs.get('target_id', '')
        target_name = kwargs.get('target_name', '')
        details = kwargs.get('details', '')
        ip_address = kwargs.get('ip_address', '')
        request = kwargs.get('request')
        if request and not ip_address:
            from apps.core.net import get_client_ip
            ip_address = get_client_ip(request)

        if args:
            if len(args) == 1:
                if not details and len(str(args[0])) > 20 and ' ' in str(args[0]):
                    details = args[0]
                elif not target_id:
                    target_id = args[0]
            elif len(args) == 2:
                if not target_id:
                    target_id = args[0]
                if not target_name:
                    target_name = args[1]
            elif len(args) >= 3:
                if not target_id:
                    target_id = args[0]
                if not target_name:
                    target_name = args[1]
                if not details:
                    details = args[2]
                if len(args) >= 4 and not ip_address:
                    ip_address = args[3]

        clean_details = sanitize_audit_details(details)

        return ActivityLog.objects.create(
            actor=user_actor,
            action=action,
            action_type=action_type,
            target_id=str(target_id or ''),
            target_name=str(target_name or ''),
            details=clean_details,
            ip_address=str(ip_address or ''),
        )
    except Exception as exc:
        logger.error(f"Failed to write ActivityLog: {exc}")
        return None


def log_email(recipient, subject, email_type='', recipient_name='', status='sent', error_message='', body='', is_secret=False, ref_table='', ref_id=''):
    """
    Records an email dispatch audit record in EmailLog.
    Never stores secret temporary passwords or body.
    """
    try:
        clean_body = '' if is_secret else body
        clean_error = sanitize_audit_details(error_message)
        return EmailLog.objects.create(
            recipient=recipient,
            recipient_name=recipient_name or '',
            subject=subject,
            body=clean_body,
            email_type=email_type or '',
            ref_table=ref_table or '',
            ref_id=str(ref_id or ''),
            status=status,
            attempts=1 if status in [EmailLog.STATUS_SENT, EmailLog.STATUS_FAILED] else 0,
            last_attempt_at=timezone.now() if status in [EmailLog.STATUS_SENT, EmailLog.STATUS_FAILED] else None,
            error_message=clean_error,
            is_secret=is_secret,
        )
    except Exception as exc:
        logger.error(f"Failed to write EmailLog: {exc}")
        return None


def send_templated_email(template_name, to_email, context, ref_table='', ref_id='', immediate=False):
    """
    Renders templates/emails/<template_name>.txt (subject on line 1 prefixed Subject:).
    Context automatically reads name, contact and venue from BarangayInfo.

    Secret emails (reg_approved, staff_created):
    - Contain temporary password.
    - Dispatched immediately with short SMTP timeout (5s).
    - NEVER store password or body in EmailLog, outbox or any log.
    - Mail failure NEVER raises or blocks approval.

    Immediate emails (reg_received, or immediate=True):
    - Dispatched immediately so registering resident receives receipt notice promptly.
    - Logged to EmailLog with status='sent' (or 'queued' if offline).

    Other non-secret emails:
    - Queued to EmailLog outbox (status='queued').
    - Picked up and sent by send_queued_emails scheduled command.
    """
    if not to_email:
        return False, "No recipient email provided"

    clean_name = template_name if template_name.endswith('.txt') else f"{template_name}.txt"
    template_path = f"emails/{clean_name}"

    info = None
    try:
        from apps.accounts.models import BarangayInfo
        info = BarangayInfo.objects.first()
    except Exception:
        pass

    brgy_name = info.name if (info and info.name) else getattr(settings, 'BARANGAY_NAME', 'Barangay')
    brgy_contact = info.contact_no if info else '(02) 8123-4567'
    brgy_venue = info.venue if info else 'Barangay Session Hall'
    brgy_addr = info.address if info else 'Barangay Hall'
    office_hours = info.office_hours if info else 'Monday - Friday, 8:00 AM - 5:00 PM'

    ctx = {
        'barangay_name': brgy_name,
        'barangay_address': brgy_addr,
        'barangay_contact': brgy_contact,
        'contact_no': brgy_contact,
        'venue': brgy_venue,
        'barangay_venue': brgy_venue,
        'office_hours': office_hours,
        'login_url': '/accounts/login/',
        'register_url': '/accounts/signup/',
    }
    if context:
        ctx.update(context)
        # Ensure default fallback if empty
        if info and info.name and context.get('barangay_name') in ['Barangay', 'Poblacion', None]:
            ctx['barangay_name'] = info.name

    try:
        rendered = render_to_string(template_path, ctx).strip()
        lines = rendered.split('\n', 1)
        first_line = lines[0].strip()
        if first_line.lower().startswith('subject:'):
            subject = first_line.split(':', 1)[1].strip()
            body = lines[1].strip() if len(lines) > 1 else ''
        else:
            subject = first_line
            body = lines[1].strip() if len(lines) > 1 else ''

        secret = is_secret_template(clean_name)
        send_now = immediate or (clean_name in ['reg_received.txt', 'reg_received'])
        log_type = str(template_name)

        if secret:
            # Send immediately with short SMTP timeout (5s)
            try:
                try:
                    connection = get_connection(timeout=5)
                except TypeError:
                    connection = get_connection()

                email_msg = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                    connection=connection,
                )
                email_msg.send(fail_silently=False)

                EmailLog.objects.create(
                    recipient=to_email,
                    recipient_name=str(ctx.get('first_name', '')),
                    subject=subject,
                    body='',  # NEVER store body or password for secret emails
                    email_type=log_type,
                    ref_table=ref_table or '',
                    ref_id=str(ref_id or ''),
                    status=EmailLog.STATUS_SENT,
                    attempts=1,
                    last_attempt_at=timezone.now(),
                    is_secret=True,
                )
                return True, "Email sent successfully"
            except Exception as exc:
                clean_err = sanitize_audit_details(str(exc))
                logger.error(f"Failed sending secret email '{clean_name}' to {to_email}: {clean_err}")
                EmailLog.objects.create(
                    recipient=to_email,
                    recipient_name=str(ctx.get('first_name', '')),
                    subject=subject,
                    body='',  # NEVER store body or password
                    email_type=log_type,
                    ref_table=ref_table or '',
                    ref_id=str(ref_id or ''),
                    status=EmailLog.STATUS_FAILED,
                    attempts=1,
                    last_attempt_at=timezone.now(),
                    error_message=clean_err,
                    is_secret=True,
                )
                return False, clean_err
        elif send_now:
            # Send non-secret email immediately (e.g. resident signup receipt)
            try:
                try:
                    connection = get_connection(timeout=5)
                except TypeError:
                    connection = get_connection()

                email_msg = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                    connection=connection,
                )
                email_msg.send(fail_silently=False)

                EmailLog.objects.create(
                    recipient=to_email,
                    recipient_name=str(ctx.get('first_name', '')),
                    subject=subject,
                    body=body,
                    email_type=log_type,
                    ref_table=ref_table or '',
                    ref_id=str(ref_id or ''),
                    status=EmailLog.STATUS_SENT,
                    attempts=1,
                    last_attempt_at=timezone.now(),
                    error_message='',
                    is_secret=False,
                )
                return True, "Email sent successfully"
            except Exception as exc:
                clean_err = sanitize_audit_details(str(exc))
                logger.warning(f"Could not send email immediately to {to_email}, queued in outbox: {clean_err}")
                EmailLog.objects.create(
                    recipient=to_email,
                    recipient_name=str(ctx.get('first_name', '')),
                    subject=subject,
                    body=body,
                    email_type=log_type,
                    ref_table=ref_table or '',
                    ref_id=str(ref_id or ''),
                    status=EmailLog.STATUS_QUEUED,
                    attempts=1,
                    last_attempt_at=timezone.now(),
                    error_message=clean_err,
                    is_secret=False,
                )
                return True, f"Email queued in outbox: {clean_err}"
        else:
            # Non-secret email: Place in Outbox (status='queued')
            EmailLog.objects.create(
                recipient=to_email,
                recipient_name=str(ctx.get('first_name', '')),
                subject=subject,
                body=body,
                email_type=log_type,
                ref_table=ref_table or '',
                ref_id=str(ref_id or ''),
                status=EmailLog.STATUS_QUEUED,
                attempts=0,
                last_attempt_at=None,
                error_message='',
                is_secret=False,
            )
            return True, "Email queued in outbox"

    except Exception as exc:
        clean_err = sanitize_audit_details(str(exc))
        logger.error(f"Error preparing templated email '{template_name}' for {to_email}: {clean_err}")
        return False, clean_err
