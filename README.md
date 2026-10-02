# Barangay Information and Management System

A production-ready, real-time Barangay Information and Management System built with **Python 3.12+**, **Django 5.x**, **Django Channels**, **Daphne (ASGI)**, and modular **Sass (SCSS)**.

---

## 🌟 Comprehensive Functional Modules

### 1. Registry of Barangay Inhabitants (RBI) & Demographics
- **Extended User Model & Demographics:**
  - Purok jurisdiction (Purok 1 through Purok 7).
  - Civil status (Single, Married, Widowed, Separated).
  - Occupation and Date of Birth.
  - Social welfare & vulnerability tags: **Senior Citizen (60+)**, **Person with Disability (PWD)**, and **4Ps Beneficiary**.
- **Household Management (`Household`):**
  - Unique household tracking number (e.g., `HH-2026-001`).
  - Head of the household designation and address mapping.
  - Linked members through the RBI directory.
- **Searchable RBI Directory (`/accounts/rbi/`):**
  - Filterable by Purok, Senior Citizens, PWDs, 4Ps, and Household reference.
  - Real-time demographic KPI cards and pagination.

### 2. Peace, Order & Katarungang Pambarangay (`/blotter/`)
- **Incident Blotter Logging (`BlotterRecord`):**
  - Track incidents with unique case numbers (`BLOT-YYYY-XXXX`).
  - Complainant and Respondent profiles, incident location, time, and factual narrative.
  - Status lifecycle: `Open`, `Settled`, `Referred to Court`.
- **Katarungang Pambarangay Mediation (`KPCase`):**
  - Scheduled conciliation hearing dates and times.
  - Lupon Tagapamayapa mediation proceedings and agreements.
  - Upload scanned Kasunduan / Amicable Settlement documents.
  - Flag issuance of official **Certificate to File Action (CFA)** when disputes cannot be resolved at the barangay level.

### 3. Legislative & Transparency Portal (`/communications/transparency/`)
- **Full Disclosure Legislation Registry (`LegislativeRecord`):**
  - Public archive of enacted **Barangay Ordinances**, **Resolutions**, and **Executive Orders**.
  - Document numbers, dates enacted/signed, and summaries.
  - Downloadable official signed PDF documents for citizens.

### 4. Automated Clearance Verification & QR Code Generation (`/appointments/`)
- **Automated Issuance Signal (`apps/appointments/signals.py`):**
  - When an appointment status transitions to `completed`, a `post_save` signal generates an `IssuedDocumentLog`.
  - Automatically calculates unique sequential control numbers (e.g. `BRGY-2026-0001`).
  - Programmatically generates an official QR code embedding the verification link.
- **Public Verification Endpoint (`/appointments/verify/<control_number>/`):**
  - Publicly accessible page confirming document authenticity and certifying official details.

### 5. Finance & Asset Inventory (`/finance/`)
- **Document Throughput & Clearance Activity:**
  - Real-time ledger of all issued clearances, residency, indigency, and award certificates.
- **Barangay Property & Equipment Inventory (`AssetInventory`):**
  - Categories: *Vehicles*, *Equipment*, *Emergency Tools*, *Furniture*.
  - Accountability tracking with condition badges (*Good*, *Maintenance*, *Disposed*), serial numbers, acquisition dates, and custodial locations.

### 6. Barangay Kapitan Real-Time Status Tracker (`/communications/kapitan/tracker/`)
- Toggle between **On Duty** and **On Leave** (with required leave reason and expected return date).
- Instant WebSocket broadcast to the **`barangay_broadcast`** channel layer.
- Dynamic topbar pill indicator pulses green when On Duty, and transitions to amber with tooltip explanation and expected return date when On Leave—updating live without page refresh!

### 7. Real-Time Chat & Notification System (`/chat/`)
- Bidirectional 1-on-1 direct messaging powered by Django Channels `AsyncWebsocketConsumer`.
- Full persistent history stored in SQLite via Django ORM (`Message` model).
- Global notification bell with active unread counter badge and toast alert popups.

---

## 📂 Architecture Overview

```
c:\brgy\
├── manage.py
├── compile_scss.py             # Libsass compilation script
├── seed_demo_data.py           # Preloaded demo accounts & test data
├── requirements.txt
├── config/
│   ├── settings.py             # Daphne, Channels, Custom User Model, Middleware
│   ├── asgi.py                 # ProtocolTypeRouter, AuthMiddlewareStack, WebSocket URLRouter
│   ├── urls.py                 # Core routing & media serving
│   └── wsgi.py
├── apps/
│   ├── accounts/               # Custom User model, Household (RBI), approval gate middleware
│   ├── appointments/           # Document requests, IssuedDocumentLog, QR code signals
│   ├── blotter/                # BlotterRecord, KPCase, peace & order mediation
│   ├── communications/         # Announcements, LegislativeRecord (Transparency), Kapitan duty tracker
│   ├── finance/                # AssetInventory, document issuing throughput
│   └── chat/                   # AsyncWebsocketConsumer, routing, 1-on-1 chat, notifications
├── static/
│   ├── scss/                   # _variables.scss, main.scss
│   ├── css/                    # Compiled main.css
│   └── js/                     # websocket.js, main.js
├── media/                      # Uploaded ID proofs, QR codes, KP docs, legislative PDFs
└── templates/
    ├── base.html               # Responsive shell, live Kapitan pill, notification bell
    ├── accounts/               # Login, signup, pending gate, role dashboards, approvals, RBI
    ├── appointments/           # Appointment list, request form, stepper detail, QR verification
    ├── blotter/                # Blotter dashboard, incident logger, KP mediation detail
    ├── communications/         # Feed, article detail, markdown form, Kapitan tracker, Transparency
    ├── finance/                # Overview, asset registration & edit forms
    └── chat/                   # Inbox, live chat room, notification center
```

---

## 🚀 Quickstart & Running the App

### 1. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Run Migrations & Seed Demo Data
```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe seed_demo_data.py
```

### 3. Start the Daphne ASGI Server
```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```
Open **`http://127.0.0.1:8000/`** in your browser.

---

## 👥 Preloaded Demo Credentials

| Role | Username | Password | Notes |
|---|---|---|---|
| **Barangay Admin** | `admin` | `admin123` | Full access, RBI directory, Blotter, Finance & Assets, Approvals |
| **Barangay Kapitan** | `kapitan` | `kapitan123` | Executive duty tracker, Peace & Order mediation, Legislation |
| **Approved Resident** | `maria` | `resident123` | Verified resident, Head of `HH-2026-001` (Purok 2), active clearance |
| **Pending Resident** | `juan` | `resident123` | Gated resident demonstrating the Pending Verification notice page |
| **Senior Citizen Resident** | `pedro` | `resident123` | Senior Citizen & PWD resident, Head of `HH-2026-003` (Purok 1) |
| **4Ps Beneficiary Resident** | `elena` | `resident123` | 4Ps Program Beneficiary resident (Purok 3) |

---

## 🧪 Automated Test Suite
Run the 11 integration tests covering roles, the approval gate, appointments, automated QR code generation, RBI directory, Blotter proceedings, Transparency, and Asset inventory:
```powershell
.\.venv\Scripts\python.exe manage.py test
```
All 11 tests pass with 0 errors.
