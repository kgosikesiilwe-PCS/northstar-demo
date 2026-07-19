# NorthStar MVP

NorthStar is a runnable MVP for a Medicare-aligned family information app. It lets a Medicare-eligible individual store plan details, PCP/provider information, medications, allergies, Medicare advisor/AOR information supplied by the beneficiary, emergency contacts, document uploads or document locations, and important family notes. The profile owner can share selected sections only with chosen family members or trusted relatives.

This is an MVP codebase, not a production compliance certification. Treat all health-related data in this app as ePHI and complete legal, security, vendor, BAA, policy, and risk-analysis work before real users.

## Fastest preview

### Mac

Double-click `start_mac.command`. It installs what it needs, starts the app, and opens your browser. Leave the Terminal window open while testing.

If macOS blocks the launcher, open Terminal, type `cd `, drag the `northstar_mvp` folder into Terminal, press Enter, then run:

```bash
python3 START_HERE.py
```

### Windows

Double-click `start_windows.bat`. It installs what it needs, starts the app, and opens your browser. Leave the Command Prompt window open while testing.

### Any computer with Docker Desktop

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

## What is included

- Medicare-focused landing page and dashboard
- Medicare Review Packet printable page
- Senior-friendly web UI
- User registration and login
- Beneficiary profile
- Emergency contacts and next of kin
- Medications
- Allergies
- Medicare and insurance information
- PCP / doctors / providers
- Medicare advisor / agent-of-record information supplied by the beneficiary
- Surgeries
- Legal and insurance document upload/location tracking
- Important family notes
- Financial & life info locator with warnings against full banking/password storage
- Family-only access authorization
- Section-level permissions
- Revoke access
- Audit log
- Printable emergency card
- SQLite database for local development
- Encrypted document storage using Fernet
- Field-level encryption for selected sensitive fields
- CSRF protection for forms
- PBKDF2 password hashing

## Not included yet

- Agent subscription portal
- Agent access to profiles
- Agent billing/subscription management
- Carrier AOR verification
- PCP verification
- Scope of Appointment workflow
- CMS Blue Button integration
- Claims data integrations
- Email/SMS sending
- MFA/passkeys
- Production cloud deployment
- HIPAA policy package
- BAA management workflow
- Full admin support tooling

## Local setup

```bash
cd northstar_mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main init-db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the app at:

```text
http://127.0.0.1:8000
```

Or use:

```bash
./run.sh
```

## Docker setup

```bash
docker build -t northstar-mvp .
docker run --rm -p 8000:8000 -v "$(pwd)/instance:/app/instance" northstar-mvp
```

## Environment variables

Copy `.env.example` to `.env` for production-like configuration.

Important variables:

```text
NORTHSTAR_SESSION_SECRET=generate-a-long-random-secret
NORTHSTAR_FERNET_KEY=generate-with-Fernet.generate_key()
NORTHSTAR_DB_PATH=instance/northstar.sqlite3
NORTHSTAR_UPLOAD_DIR=instance/uploads
```

For local development, the app auto-generates dev secrets in `instance/`. Do not use auto-generated dev secrets in production.

## MVP user flow

1. Senior creates a profile.
2. Senior adds emergency contacts, medications, allergies, PCP, insurance, Medicare advisor, documents, and important notes.
3. Senior opens the Medicare Review Packet to check plan, PCP, medications, advisor, and insurance-card readiness.
4. Senior creates a Family Access Authorization for a child, spouse, relative, or trusted person.
5. App generates an invite link.
6. Trusted person accepts invite and can only see selected sections.
7. Senior can revoke access.
8. Audit log tracks views, edits, uploads, downloads, grants, revocations, and other sensitive actions.

## Family sharing model

Access is section-based. The senior can authorize access to:

- Emergency contacts / next of kin
- Medications
- Allergies
- Medicare & insurance
- PCP / doctors / providers
- Medicare advisor / agent
- Surgeries
- Legal documents
- Important info
- Financial & life info locator
- Photo ID

Each grant stores:

- Recipient
- Relationship
- Allowed sections
- View/edit/upload/download permissions
- Expiration date
- Electronic signature
- Authorization language version
- Signed timestamp
- Revocation timestamp, if revoked

## Sensitive-data guardrails

The app intentionally discourages or rejects storage of:

- Passwords
- PINs
- CVV/CVC codes
- Full credit card numbers
- Full bank account numbers
- Social Security numbers
- Security question answers
- Usernames/logins

The Financial & Life Info Locator is designed to store institution names, contact information, last four digits only, and document locations.

## HIPAA-oriented controls included in code

- Unique user accounts
- Password hashing with PBKDF2
- Session CSRF protection
- Section-based access control
- Encrypted selected fields
- Encrypted document storage
- Audit logs
- No PHI in outbound email/SMS because no email/SMS integration is included
- Limited family sharing by explicit authorization
- Revocation support

## HIPAA work still required before launch

Code alone does not make a product HIPAA compliant. Before using this with real beneficiaries or covered-entity workflows, complete at least:

- Business Associate Agreements with covered entities
- Subcontractor BAAs with cloud, database, logging, auth, support, and storage vendors that touch ePHI
- HIPAA Security Rule risk analysis
- Risk management plan
- Incident response plan
- Breach notification procedure
- Workforce training
- Sanctions policy
- Access control policy
- Device and workstation policy
- Backup and disaster recovery testing
- Data retention/destruction policy
- Vendor review process
- Production encryption/key management design
- MFA/passkeys
- Security monitoring
- Vulnerability management
