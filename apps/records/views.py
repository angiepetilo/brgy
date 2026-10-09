from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from apps.accounts.permissions import resident_forbidden
from apps.accounts import selectors
from apps.accounts.models import Officer, StaffAssignment, Purok
from apps.appointments.models import Appointment, IssuedDocumentLog


DEPARTMENTS = [
    {
        'id': 'health',
        'name': 'Barangay Health Center',
        'code': 'BHC',
        'icon': 'stethoscope',
        'color': '#16A34A',
        'description': 'Primary community healthcare, prenatal care, immunization, first aid, and medical consultations.',
        'head': 'Health Center Officer / Barangay Nutrition Scholar',
        'location': 'Ground Floor, Barangay Health Station',
        'operating_hours': 'Monday – Friday: 8:00 AM – 5:00 PM',
        'contact': 'health@barangay.gov.ph / Local 104',
        'services': ['General Consultations', 'Child Immunization', 'Prenatal & Postnatal Care', 'Medicine Dispensation'],
    },
    {
        'id': 'security',
        'name': 'Peace and Order & Public Safety',
        'code': 'POPS',
        'icon': 'shield',
        'color': '#1E3A8A',
        'description': 'Barangay Tanod brigade, night patrols, community safety, disaster response, and crisis management.',
        'head': 'Chief Tanod / Committee Chair on Peace and Order',
        'location': 'Barangay Security & Outpost Command',
        'operating_hours': '24/7 Operations & Emergency Dispatch',
        'contact': 'emergency@barangay.gov.ph / Hotlines',
        'services': ['Community Patrols', 'Emergency Response', 'Incident Reporting', 'Traffic & Crowd Management'],
    },
    {
        'id': 'records',
        'name': 'Records, Clearances & Secretariat',
        'code': 'SEC',
        'icon': 'folder-open',
        'color': '#1E3A8A',
        'description': 'Official records custody, issuance of barangay clearances, residency certificates, indigency proofs, and council documentation.',
        'head': 'Barangay Secretary',
        'location': 'Office of the Secretary, Main Hall',
        'operating_hours': 'Monday – Friday: 8:00 AM – 5:00 PM',
        'contact': 'secretary@barangay.gov.ph / Local 101',
        'services': ['Barangay Clearance', 'Certificate of Residency', 'Certificate of Indigency', 'Official Records Custody'],
    },
    {
        'id': 'treasury',
        'name': 'Treasury & Financial Services',
        'code': 'TRS',
        'icon': 'coins',
        'color': '#374151',
        'description': 'Collection of official fees, community tax assessment, disbursement of approved funds, and budget monitoring.',
        'head': 'Barangay Treasurer',
        'location': 'Treasury Window, Main Hall',
        'operating_hours': 'Monday – Friday: 8:30 AM – 4:30 PM',
        'contact': 'treasury@barangay.gov.ph / Local 102',
        'services': ['Fee Collections & Official Receipts', 'Document Fee Processing', 'Financial Statements & Audits'],
    },
    {
        'id': 'social_welfare',
        'name': 'Social Welfare & Community Affairs',
        'code': 'MSWD',
        'icon': 'hand-heart',
        'color': '#374151',
        'description': 'Programs for Senior Citizens, Persons with Disabilities (PWD), 4Ps beneficiaries, and marginalized families.',
        'head': 'Focal Person for Social Welfare',
        'location': 'Social Services Desk, Room 2',
        'operating_hours': 'Monday – Friday: 8:00 AM – 5:00 PM',
        'contact': 'welfare@barangay.gov.ph / Local 105',
        'services': ['Senior Citizen Assistance', 'PWD IDs & Benefits Coordination', '4Ps Monitoring & Support'],
    },
    {
        'id': 'youth_sports',
        'name': 'Youth Development & Sports (SK)',
        'code': 'SK',
        'icon': 'trophy',
        'color': '#1E3A8A',
        'description': 'Youth leadership, sports leagues, educational assistance, student development, and anti-drug advocacy.',
        'head': 'SK Chairperson',
        'location': 'SK Office & Community Center',
        'operating_hours': 'Monday – Saturday: 9:00 AM – 6:00 PM',
        'contact': 'sk@barangay.gov.ph / Local 106',
        'services': ['Youth Governance', 'Sports Tournaments', 'Educational Assistance', 'Community Youth Programs'],
    },
]


@resident_forbidden
def records_hub_view(request):
    """
    Module: Records (Staff & Admin Only).
    Placeholder state while under renovation.
    """
    return render(request, 'records/records_hub.html', {})


@resident_forbidden
def print_document_view(request, pk):
    """
    Print-ready layout for official issued barangay certificates / clearances.
    """
    log_entry = get_object_or_404(IssuedDocumentLog.objects.select_related('appointment', 'issued_to', 'issued_by'), pk=pk)
    return render(request, 'records/print_document.html', {'log': log_entry, 'appointment': log_entry.appointment})


@resident_forbidden
def print_health_record_view(request, pk):
    """
    Print-ready layout for completed health center consultation record.
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related('healthcare_service', 'resident', 'processed_by'),
        pk=pk,
        category=Appointment.CATEGORY_HEALTHCARE
    )
    return render(request, 'records/print_health_record.html', {'appointment': appointment})
