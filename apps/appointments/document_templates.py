"""
Dynamic Official Document Letter Template Engine
Provides default templates for Philippine Barangay Clearances & Certificates,
and replaces dynamic placeholders with real resident and issuance data.
Supports dynamic header, title, salutation, body paragraphs, signatories, and footer notes.
"""
from datetime import date
from django.utils import timezone
from apps.accounts.models import BarangayInfo, Officer, Resident, User


DEFAULT_TEMPLATES = {
    'clearance': """This is to certify that [FULL_NAME], [AGE], [CITIZENSHIP] citizen, [CIVIL_STATUS], is a bonafide resident of [ADDRESS], [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].

Based on official records kept in this office, the subject individual has no derogatory record or pending criminal or civil case filed against him/her and is known to be of good moral character and a peaceful, law-abiding citizen in this community.

This certification is issued upon the request of the above-named person for the purpose of: [PURPOSE].

Issued this [DATE_ISSUED] at the Office of the Punong Barangay, [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].""",

    'residency': """This is to certify that [FULL_NAME], [AGE], [CITIZENSHIP] citizen, is a permanent and bonafide resident of [ADDRESS], [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].

Records show that the subject individual has been residing within the territorial jurisdiction of this Barangay and has maintained continuous good standing as a community member.

This Certificate of Residency is issued upon the request of the subject individual for the purpose of: [PURPOSE].

Issued this [DATE_ISSUED] at the Barangay Administration Center, [BARANGAY_NAME].""",

    'indigency': """This is to certify that [FULL_NAME], [AGE], [CITIZENSHIP] citizen, is a bonafide resident of [ADDRESS], [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].

This further certifies that the above-named person belongs to the indigent family bracket of this Barangay, earning subsistence income and requiring public or humanitarian assistance.

This Certificate of Indigency is issued upon the request of the interested party for the purpose of: [PURPOSE] (e.g., Medical Assistance, Educational Assistance, Financial Aid).

Issued this [DATE_ISSUED] at [BARANGAY_NAME] Session Hall.""",

    'business': """This is to certify that the business establishment under the business name "[PURPOSE]" owned and operated by [FULL_NAME] with business address at [ADDRESS], [BARANGAY_NAME], [MUNICIPALITY] has complied with Barangay rules and regulations.

The management is found to maintain good community order and sanitation, and is hereby granted this BARANGAY BUSINESS CLEARANCE for the purpose of Municipal Business Permit application.

Issued this [DATE_ISSUED] at [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].""",

    'default': """This is to certify that [FULL_NAME], [AGE], [CITIZENSHIP] citizen, is a bonafide resident of [ADDRESS], [BARANGAY_NAME], [MUNICIPALITY], [PROVINCE].

Based on official records in this office, the subject individual is known to be of good moral character and a law-abiding citizen in the community.

This certification is issued upon the request of the above-named person for the purpose of: [PURPOSE].

Issued this [DATE_ISSUED] at the Barangay Administration Center, [BARANGAY_NAME]."""
}


def get_default_letter_template(doc_name='', doc_code=''):
    """
    Returns standard official text for a document type.
    """
    search_str = f"{doc_name} {doc_code}".lower()
    if 'indigen' in search_str:
        return DEFAULT_TEMPLATES['indigency']
    if 'residen' in search_str:
        return DEFAULT_TEMPLATES['residency']
    if 'business' in search_str or 'permit' in search_str:
        return DEFAULT_TEMPLATES['business']
    if 'clearance' in search_str:
        return DEFAULT_TEMPLATES['clearance']
    return DEFAULT_TEMPLATES['default']


def compute_resident_age(birthdate):
    if not birthdate:
        return None
    today = date.today()
    try:
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return age if age >= 0 else None
    except Exception:
        return None


def ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def get_document_tokens(appointment, log):
    """
    Builds the dictionary of dynamic replacement tokens for a document issuance.
    """
    doc_type = getattr(appointment, 'document_type', None)
    user = appointment.resident
    first_name = appointment.applicant_first_name or (user.first_name if user else '')
    last_name = appointment.applicant_last_name or (user.last_name if user else '')
    full_name = appointment.get_applicant_name() or (user.get_full_name() if user else 'N/A')
    address = appointment.get_applicant_address() or (user.address if user else 'this Barangay')

    civil_status = 'Single'
    birthdate = getattr(user, 'date_of_birth', None) if user else None
    purok_name = user.purok.name if (user and user.purok) else ''

    resident_profile = None
    if user:
        resident_profile = Resident.objects.filter(last_name__iexact=user.last_name, first_name__iexact=user.first_name).first()
    if not resident_profile and last_name and first_name:
        resident_profile = Resident.objects.filter(last_name__iexact=last_name, first_name__iexact=first_name).first()

    if resident_profile:
        if resident_profile.civil_status:
            civil_status = resident_profile.get_civil_status_display()
        if resident_profile.birthdate:
            birthdate = resident_profile.birthdate
        if resident_profile.purok:
            purok_name = resident_profile.purok.name
        if resident_profile.address and not address:
            address = resident_profile.address

    calculated_age = compute_resident_age(birthdate)
    age_str = f"{calculated_age} years old" if (calculated_age is not None and calculated_age > 0) else "of legal age"

    brgy_info = BarangayInfo.get_solo()
    brgy_name = brgy_info.name or 'Barangay Poblacion'
    city_name = brgy_info.city or 'General Santos City'
    province_name = brgy_info.province or 'South Cotabato'

    kapitan_officer = Officer.objects.filter(position=Officer.POSITION_PUNONG_BARANGAY).select_related('user').first()
    kapitan_name = (kapitan_officer.user.get_full_name() if (kapitan_officer and kapitan_officer.user) else "HON. ERNESTO VALENZUELA")

    secretary_officer = Officer.objects.filter(position=Officer.POSITION_SECRETARY).select_related('user').first()
    secretary_name = (secretary_officer.user.get_full_name() if (secretary_officer and secretary_officer.user) else "RODRIGO ADMIN")

    processor_name = (log.issued_by.get_full_name() if (log and log.issued_by) else secretary_name)
    control_no = log.control_number if log else (appointment.reference_no or 'BRGY-2026-0001')

    issued_dt = log.issued_at if (log and log.issued_at) else timezone.now()
    day_ord = ordinal(issued_dt.day)
    date_str = f"{day_ord} day of {issued_dt.strftime('%B, %Y')}"

    fee_val = doc_type.fee if doc_type else getattr(appointment, 'fee_at_booking', 0)
    fee_str = f"₱{fee_val:.2f}" if fee_val and fee_val > 0 else "Free"

    doc_service_title = appointment.get_service_title()

    return {
        '[FULL_NAME]': full_name.upper(),
        '[FIRST_NAME]': first_name.upper(),
        '[LAST_NAME]': last_name.upper(),
        '[ADDRESS]': address,
        '[PUROK]': purok_name or 'Barangay Proper',
        '[AGE]': age_str,
        '[CIVIL_STATUS]': civil_status,
        '[CITIZENSHIP]': 'Filipino',
        '[PURPOSE]': (appointment.purpose or 'OFFICIAL TRANSACTION').upper(),
        '[DATE_ISSUED]': date_str,
        '[CONTROL_NO]': control_no,
        '[BARANGAY_NAME]': brgy_name,
        '[MUNICIPALITY]': city_name,
        '[CITY]': city_name,
        '[PROVINCE]': province_name,
        '[PUNONG_BARANGAY]': kapitan_name,
        '[SECRETARY]': secretary_name,
        '[PROCESSED_BY]': processor_name,
        '[OR_NO]': appointment.reference_no or 'N/A',
        '[FEE]': fee_str,
        '[SERVICE_TITLE]': doc_service_title.upper(),
    }


def replace_tokens(text, tokens):
    rendered = str(text or '')
    for tag, val in tokens.items():
        rendered = rendered.replace(tag, str(val))
        rendered = rendered.replace(tag.lower(), str(val))
        rendered = rendered.replace(tag.capitalize(), str(val))
    return rendered


def render_document_letter(appointment, log, raw_template=None):
    """
    Renders body paragraphs with dynamic token replacement.
    """
    doc_type = getattr(appointment, 'document_type', None)
    if raw_template is not None and str(raw_template).strip():
        template_text = str(raw_template).strip()
    elif log and getattr(log, 'customized_letter_body', '') and log.customized_letter_body.strip():
        template_text = log.customized_letter_body.strip()
    elif doc_type and getattr(doc_type, 'letter_body', '') and doc_type.letter_body.strip():
        template_text = doc_type.letter_body.strip()
    else:
        doc_name = doc_type.name if doc_type else appointment.get_service_title()
        doc_code = doc_type.code if doc_type else ''
        template_text = get_default_letter_template(doc_name, doc_code)

    tokens = get_document_tokens(appointment, log)
    return replace_tokens(template_text, tokens)


def render_document_header(appointment, log, raw_header=None):
    """
    Renders header / letterhead lines.
    """
    doc_type = getattr(appointment, 'document_type', None)
    header_text = None

    if raw_header is not None and str(raw_header).strip():
        header_text = str(raw_header).strip()
    elif log and getattr(log, 'customized_letter_header', '') and log.customized_letter_header.strip():
        header_text = log.customized_letter_header.strip()
    elif doc_type and getattr(doc_type, 'letter_header', '') and doc_type.letter_header.strip():
        header_text = doc_type.letter_header.strip()

    tokens = get_document_tokens(appointment, log)

    if header_text:
        rendered = replace_tokens(header_text, tokens)
        lines = [line.strip() for line in rendered.split('\n') if line.strip()]
        return lines

    # Default official Philippine header
    return [
        "Republic of the Philippines",
        f"Province of {tokens.get('[PROVINCE]')} · {tokens.get('[MUNICIPALITY]')}",
        tokens.get('[BARANGAY_NAME]', 'Barangay Poblacion').upper(),
        "OFFICE OF THE PUNONG BARANGAY"
    ]


def render_document_title(appointment, log, raw_title=None):
    """
    Renders official certificate title (e.g. BARANGAY CLEARANCE).
    """
    doc_type = getattr(appointment, 'document_type', None)
    title_text = None

    if raw_title is not None and str(raw_title).strip():
        title_text = str(raw_title).strip()
    elif log and getattr(log, 'customized_letter_title', '') and log.customized_letter_title.strip():
        title_text = log.customized_letter_title.strip()
    elif doc_type and getattr(doc_type, 'letter_title', '') and doc_type.letter_title.strip():
        title_text = doc_type.letter_title.strip()
    else:
        title_text = appointment.get_service_title()

    tokens = get_document_tokens(appointment, log)
    return replace_tokens(title_text, tokens).upper()


def render_document_footer(appointment, log, raw_footer=None):
    """
    Renders official footer notes, validity clause, and dry seal notice.
    """
    doc_type = getattr(appointment, 'document_type', None)
    footer_text = None

    if raw_footer is not None and str(raw_footer).strip():
        footer_text = str(raw_footer).strip()
    elif log and getattr(log, 'customized_letter_footer', '') and log.customized_letter_footer.strip():
        footer_text = log.customized_letter_footer.strip()
    elif doc_type and getattr(doc_type, 'letter_footer', '') and doc_type.letter_footer.strip():
        footer_text = doc_type.letter_footer.strip()

    tokens = get_document_tokens(appointment, log)

    if footer_text:
        rendered = replace_tokens(footer_text, tokens)
        lines = [line.strip() for line in rendered.split('\n') if line.strip()]
        return lines

    # Default official footer lines
    return [
        "Official Verification: This document is officially recorded in the Barangay Clearance Registry.",
        "Valid for six (6) months from date of issuance unless revoked for cause.",
        "Not valid without the official Barangay dry seal."
    ]
