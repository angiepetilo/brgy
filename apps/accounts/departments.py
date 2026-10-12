import json
from apps.accounts.models import Officer, StaffAssignment

DEPARTMENTS = [
    {
        'id': 'health',
        'name': 'Barangay Health Center',
        'code': 'BHC',
        'icon': 'stethoscope',
        'color': '#16A34A',
        'description': 'Primary community healthcare, prenatal care, immunization, first aid, and medical consultations.',
        'head': 'Health Center Officer',
        'location': 'Ground Floor, Barangay Health Station',
        'operating_hours': 'Monday – Friday: 8:00 AM – 5:00 PM',
        'contact': 'health@barangay.gov.ph · Local 104',
        'services': ['General Consultations', 'Child Immunization', 'Prenatal & Postnatal Care', 'Medicine Dispensation'],
    },
    {
        'id': 'security',
        'name': 'Peace and Order & Public Safety',
        'code': 'POPS',
        'icon': 'shield',
        'color': '#1E3A8A',
        'description': 'Barangay Tanod brigade, night patrols, community safety, disaster response, and crisis management.',
        'head': 'Chief Tanod',
        'location': 'Barangay Security & Outpost Command',
        'operating_hours': '24/7 Operations & Emergency Dispatch',
        'contact': 'emergency@barangay.gov.ph · Hotlines',
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
        'contact': 'secretary@barangay.gov.ph · Local 101',
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
        'contact': 'treasury@barangay.gov.ph · Local 102',
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
        'contact': 'welfare@barangay.gov.ph · Local 105',
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
        'contact': 'sk@barangay.gov.ph · Local 106',
        'services': ['Youth Governance', 'Sports Tournaments', 'Educational Assistance', 'Community Youth Programs'],
    },
]

DEFAULT_DEPT_STAFF = {
    'health': [
        {
            'name': 'Dr. Remedios Santos, MD',
            'role': 'Municipal Health Physician',
            'phone': '(02) 8920-1122',
            'email': 'health.physician@barangay.gov.ph',
            'initials': 'RS',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Nurse Maria Elena Cruz, RN',
            'role': 'Barangay Health Nurse',
            'phone': '0917-552-3401',
            'email': 'nurse.cruz@barangay.gov.ph',
            'initials': 'MC',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Bernadette Alcantara',
            'role': 'Barangay Nutrition Scholar & BHW Focal',
            'phone': '0919-445-6712',
            'email': 'bhw.alcantara@barangay.gov.ph',
            'initials': 'BA',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
    'security': [
        {
            'name': 'Commander Danilo Reyes',
            'role': 'Chief Tanod',
            'phone': '0918-882-9901',
            'email': 'chief.tanod@barangay.gov.ph',
            'initials': 'DR',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Officer Roberto Diaz',
            'role': 'Deputy Tanod Officer',
            'phone': '0920-334-1188',
            'email': 'tanod.diaz@barangay.gov.ph',
            'initials': 'RD',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Sgt. Fernando Morales',
            'role': 'Disaster Risk Reduction & Triage Officer',
            'phone': '0917-223-9988',
            'email': 'drrmo.morales@barangay.gov.ph',
            'initials': 'FM',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
    'records': [
        {
            'name': 'Rodrigo Admin',
            'role': 'Barangay Secretary & Records Custodian',
            'phone': '0917-123-4567',
            'email': 'admin@barangay.ph',
            'initials': 'RA',
            'duty_status': 'on_duty',
            'can_message': True,
            'id': 1,
        },
        {
            'name': 'Hon. Ernesto Valenzuela',
            'role': 'Punong Barangay',
            'phone': '0918-999-0001',
            'email': 'kapitan@barangay.ph',
            'initials': 'EV',
            'duty_status': 'on_duty',
            'can_message': True,
            'id': 2,
        },
        {
            'name': 'Clara Mendoza',
            'role': 'Clearance Processor & Civil Registry Assistant',
            'phone': '0917-882-3419',
            'email': 'clearance.mendoza@barangay.gov.ph',
            'initials': 'CM',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
    'treasury': [
        {
            'name': 'Ma. Teresa Ramos',
            'role': 'Barangay Treasurer',
            'phone': '0917-771-8820',
            'email': 'treasurer.ramos@barangay.gov.ph',
            'initials': 'TR',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Arman Bautista',
            'role': 'Revenue Collection Officer',
            'phone': '0922-445-1200',
            'email': 'treasury.bautista@barangay.gov.ph',
            'initials': 'AB',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
    'social_welfare': [
        {
            'name': 'Elena Gomez, RSW',
            'role': 'Social Welfare Focal Person & MSWD Liaison',
            'phone': '0917-334-5511',
            'email': 'welfare.gomez@barangay.gov.ph',
            'initials': 'EG',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Lorna Villanueva',
            'role': 'Senior Citizens & PWD Affairs Coordinator',
            'phone': '0920-112-9844',
            'email': 'osca.villanueva@barangay.gov.ph',
            'initials': 'LV',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Marivic Perez',
            'role': '4Ps & Solo Parent Community Coordinator',
            'phone': '0919-667-3321',
            'email': '4ps.perez@barangay.gov.ph',
            'initials': 'MP',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
    'youth_sports': [
        {
            'name': 'Hon. Christian Dave Flores',
            'role': 'SK Chairperson',
            'phone': '0917-662-8833',
            'email': 'sk.chairperson@barangay.gov.ph',
            'initials': 'CF',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
        {
            'name': 'Justin Ray Aguilar',
            'role': 'SK Secretary & Sports League Coordinator',
            'phone': '0922-881-0022',
            'email': 'sk.sports@barangay.gov.ph',
            'initials': 'JA',
            'duty_status': 'on_duty',
            'can_message': False,
            'id': 0,
        },
    ],
}


def get_departments_with_staff():
    """
    Returns departments enriched with dynamically assigned officers/staff
    and serialized JSON for client-side modal inspection.
    """
    officers = list(Officer.objects.select_related('user').all())
    staff_assignments = list(StaffAssignment.objects.select_related('user', 'officer').all())

    dept_keywords = {
        'health': ['health', 'bhw', 'nutrition', 'medical', 'clinic'],
        'security': ['peace', 'order', 'tanod', 'security', 'police', 'pops'],
        'records': ['secretary', 'record', 'clearance', 'punong barangay', 'clerk', 'admin'],
        'treasury': ['treasur', 'finance', 'revenue', 'budget', 'cedula'],
        'social_welfare': ['welfare', 'social', 'pwd', 'senior', '4ps', 'family', 'education'],
        'youth_sports': ['sk', 'youth', 'sport'],
    }

    results = []
    for dept in DEPARTMENTS:
        dept_copy = dict(dept)
        dept_id = dept['id']
        keywords = dept_keywords.get(dept_id, [dept_id])

        matched_staff = []
        seen_user_ids = set()

        for off in officers:
            pos_lower = (off.position or '').lower()
            com_lower = (off.committee or '').lower()
            if any(kw in pos_lower or kw in com_lower for kw in keywords):
                if off.user and off.user.id not in seen_user_ids:
                    u = off.user
                    seen_user_ids.add(u.id)
                    initials = f"{u.first_name[:1]}{u.last_name[:1]}".strip().upper() or u.username[:2].upper()
                    avatar_url = u.avatar.url if u.avatar else ''
                    role_title = off.position
                    if off.committee:
                        role_title += f" ({off.committee})"
                    matched_staff.append({
                        'id': u.id,
                        'name': u.get_full_name() or u.username,
                        'role': role_title,
                        'phone': getattr(u, 'phone_number', '') or '0917-000-0000',
                        'email': u.email or f"{u.username}@barangay.gov.ph",
                        'avatar_url': avatar_url,
                        'initials': initials,
                        'duty_status': 'on_duty',
                        'can_message': True,
                    })

        for sa in staff_assignments:
            scope_lower = (sa.scope_value or '').lower()
            if any(kw in scope_lower for kw in keywords):
                if sa.user and sa.user.id not in seen_user_ids:
                    u = sa.user
                    seen_user_ids.add(u.id)
                    initials = f"{u.first_name[:1]}{u.last_name[:1]}".strip().upper() or u.username[:2].upper()
                    avatar_url = u.avatar.url if u.avatar else ''
                    role_title = sa.officer.position if sa.officer else 'Department Staff'
                    matched_staff.append({
                        'id': u.id,
                        'name': u.get_full_name() or u.username,
                        'role': role_title,
                        'phone': getattr(u, 'phone_number', '') or '0917-000-0000',
                        'email': u.email or f"{u.username}@barangay.gov.ph",
                        'avatar_url': avatar_url,
                        'initials': initials,
                        'duty_status': 'on_duty',
                        'can_message': True,
                    })

        defaults = DEFAULT_DEPT_STAFF.get(dept_id, [])
        for def_st in defaults:
            if def_st.get('id') and def_st['id'] in seen_user_ids:
                continue
            if any(m['name'].lower() == def_st['name'].lower() for m in matched_staff):
                continue
            matched_staff.append(def_st)

        dept_copy['staff'] = matched_staff
        dept_copy['staff_count'] = len(matched_staff)
        dept_copy['staff_json'] = json.dumps(matched_staff)
        dept_copy['services_json'] = json.dumps(dept.get('services', []))
        results.append(dept_copy)

    return results
