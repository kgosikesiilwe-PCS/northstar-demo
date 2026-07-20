from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import db
from .crypto import decrypt_bytes, decrypt_text, encrypt_bytes, encrypt_text
from .security import csrf_token, hash_password, new_token, session_secret, validate_csrf, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("NORTHSTAR_UPLOAD_DIR", "instance/uploads"))
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}

# Whitelist of valid table/column names for dynamic SQL.
# Any new SectionConfig must have its table added here.
_VALID_TABLES: frozenset[str] = frozenset({
    "trusted_people", "medications", "allergies", "insurance_policies",
    "providers", "medicare_advisors", "surgeries", "important_notes",
    "financial_locators",
})
_VALID_PROFILE_COLUMNS: frozenset[str] = frozenset({"beneficiary_profile_id"})


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    db.init_db()
    _auto_seed()
    yield


def _auto_seed():
    """Seed the demo account on every cold boot if it doesn't exist."""
    import os as _os
    if not _os.getenv("SEED_TOKEN"):
        return  # Only auto-seed when SEED_TOKEN is set (i.e. on Render)
    try:
        existing = db.query_one("SELECT id FROM users WHERE email = ?", ("demo@northstar-demo.com",))
        if existing:
            return
        from app.security import hash_password as _hp
        from app.crypto import encrypt_text as _enc
        uid = db.execute(
            "INSERT INTO users (email, phone, full_name, password_hash, role, status) VALUES (?,?,?,?,?,?)",
            ("demo@northstar-demo.com","702-555-0100","Mary Johnson",_hp("NorthStarDemo2026!"),"user","active"))
        pid = db.execute(
            "INSERT INTO beneficiary_profiles (owner_user_id, full_name, preferred_name, date_of_birth, address_line_1, address_line_2, city, state, zip, phone, email, preferred_language, last_reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid,"Mary Johnson","Mary","1945-03-15","1234 Desert Sage Drive","Unit 1","Las Vegas","NV","89117","702-555-0100","mary.johnson@example.com","English","2026-07-01"))
        db.execute("INSERT INTO medicare_cards (beneficiary_profile_id, mbi_encrypted, name_on_card, part_a_date, part_b_date) VALUES (?,?,?,?,?)",
            (pid,_enc("1EG4-TE5-MK72"),"MARY L JOHNSON","2010-03-01","2010-03-01"))
        for name,rel,phone,email,addr,pri in [
            ("David Johnson","Spouse","702-555-0101","david.johnson@example.com","1234 Desert Sage Drive, Las Vegas NV 89117",1),
            ("Sarah Johnson","Daughter","702-555-0155","sarah.johnson@example.com","5678 Sunrise Blvd, Henderson NV 89002",2),
            ("Michael Torres","Son","702-555-0188","michael.torres@example.com","900 Lake Mead Pkwy, Las Vegas NV 89015",3)]:
            db.execute("INSERT INTO trusted_people (beneficiary_profile_id, name, relationship, phone, email, address, is_emergency_contact, priority_order, invite_status) VALUES (?,?,?,?,?,?,?,?,?)",
                (pid,name,rel,phone,email,addr,1,pri,"created"))
        for mn,dose,freq,ph,phph,doc,rsn,start,notes in [
            ("Metformin","500 mg","Twice daily with meals","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Type 2 diabetes","2018-01-15","Take with food"),
            ("Lisinopril","10 mg","Once daily in the morning","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","High blood pressure","2018-03-01","Monitor for dry cough"),
            ("Atorvastatin","20 mg","Once daily at bedtime","Walgreens Summerlin","702-555-0210","Dr. Kevin Park","High cholesterol","2020-07-15","Avoid grapefruit juice"),
            ("Aspirin","81 mg","Once daily","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Cardiac prevention","2018-01-15","Take with water"),
            ("Amlodipine","5 mg","Once daily","Walgreens Summerlin","702-555-0210","Dr. Kevin Park","Chest pain / angina","2021-04-10","May cause ankle swelling"),
            ("Vitamin D3","2000 IU","Once daily with breakfast","","","Dr. Elena Ramirez","Bone health","2019-06-01","OTC supplement")]:
            db.execute("INSERT INTO medications (beneficiary_profile_id, medication_name, dosage, frequency, pharmacy_name, pharmacy_phone, prescribing_doctor, reason, start_date, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pid,mn,dose,freq,ph,phph,doc,rsn,start,notes))
        for pn,pt,sp,prac,addr,ph,fx,net,portal,pcp,lv,na in [
            ("Dr. Elena Ramirez","Primary care doctor / PCP","Family Medicine","Desert Springs Medical Group","2075 E Flamingo Rd, Las Vegas NV 89119","702-555-0140","702-555-0141","Humana Gold Plus PPO","https://mydesertsprings.com",1,"2026-05-12","2026-11-10"),
            ("Dr. Kevin Park","Specialist","Cardiology","Nevada Heart Associates","3121 S Maryland Pkwy Ste 400, Las Vegas NV 89109","702-555-0188","702-555-0189","Humana Gold Plus PPO","https://nevadaheart.com",0,"2026-03-20","2026-09-20"),
            ("Desert Eye Associates","Eye Doctor","Ophthalmology","Desert Eye Associates","8551 W Lake Mead Blvd, Las Vegas NV 89128","702-555-0210","702-555-0211","","",0,"2026-01-15","2027-01-15"),
            ("Dr. Patricia Hill","Dentist","General Dentistry","Summerlin Dental Care","1980 Village Center Cir, Las Vegas NV 89134","702-555-0230","702-555-0231","","",0,"2026-04-08","2026-10-08")]:
            db.execute("INSERT INTO providers (beneficiary_profile_id, name, provider_type, specialty, practice_name, address, phone, fax, doctor_network, patient_portal_url, last_visit_date, next_appointment_date, is_pcp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid,pn,pt,sp,prac,addr,ph,fx,net,portal,lv,na,pcp))
        for an,at,rx,sv,notes in [
            ("Penicillin","Medication","Hives, facial swelling, difficulty breathing","Severe","Listed on hospital wristband; carry epinephrine"),
            ("Shellfish","Food","Anaphylaxis — throat swelling, vomiting","Severe","Epinephrine auto-injector prescribed"),
            ("Sulfa drugs","Medication","Rash, fever, joint pain","Moderate","No sulfonamide antibiotics"),
            ("Latex","Environmental","Skin irritation, hives","Mild","Alert surgical teams"),
            ("Ragweed / Pollen","Environmental","Nasal congestion, sneezing","Mild","Seasonal — peaks Aug-Oct")]:
            db.execute("INSERT INTO allergies (beneficiary_profile_id, allergy_name, allergy_type, reaction, severity, notes) VALUES (?,?,?,?,?,?)",
                (pid,an,at,rx,sv,notes))
        db.execute("INSERT INTO insurance_policies (beneficiary_profile_id, policy_type, insurance_company, plan_name, plan_number, member_id_encrypted, rx_bin_encrypted, rx_pcn_encrypted, group_number_encrypted, effective_date, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid,"Medicare Advantage (Part C)","Humana","Gold Plus H5619-003","H5619-003",_enc("H5619-4821-00"),_enc("610014"),_enc("MEDDADV"),_enc("N/A"),"2026-01-01","OOP max $5,000 in-network; $0 copay PCP; $45 specialist"))
        db.execute("INSERT INTO insurance_policies (beneficiary_profile_id, policy_type, insurance_company, plan_name, plan_number, member_id_encrypted, rx_bin_encrypted, rx_pcn_encrypted, effective_date, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid,"Part D Prescription Drug","SilverScript Choice (CVS)","SilverScript Choice","S5601-068",_enc("SS-9234-7701"),_enc("004336"),_enc("ADV"),"2026-01-01","Preferred pharmacy: CVS; Tier 1-2 generics $0-$10"))
        db.execute("INSERT INTO insurance_policies (beneficiary_profile_id, policy_type, insurance_company, plan_name, member_id_encrypted, effective_date, notes) VALUES (?,?,?,?,?,?,?)",
            (pid,"Medicare Part A & B (Original Medicare)","CMS / Social Security","Original Medicare",_enc("1EG4-TE5-MK72"),"2010-03-01","Keep red-white-blue card in wallet"))
        db.execute("INSERT INTO medicare_advisors (beneficiary_profile_id, advisor_name, agency_name, phone, email, npn, insurance_company, plan_name, last_helped_date, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid,"Thabang Kesiilwe","Kesiilwe Insurance","702-555-0177","kgosi.kesiilwe@gmail.com","12345678","Humana","Gold Plus H5619","2025-10-15","Annual review every Oct-Nov; call before AEP"))
        for sname,sdate,fac,doc,notes in [
            ("Right total knee replacement","2019-03-14","Sunrise Hospital Las Vegas","Dr. Marcus Webb","Full recovery; follow-up annually"),
            ("Cataract surgery — left eye","2022-08-09","Desert Eye Surgery Center","Dr. Patricia Cole","No complications; vision improved to 20/30"),
            ("Appendectomy","1978-06-02","St. Rose Dominican Hospital","Unknown","Emergency procedure; full recovery"),
            ("Hysterectomy (partial)","2001-11-20","Valley Hospital Medical Center","Dr. Sandra Reyes","Benign fibroid; full recovery")]:
            db.execute("INSERT INTO surgeries (beneficiary_profile_id, surgery_name, approximate_date, facility, doctor, notes) VALUES (?,?,?,?,?,?)",
                (pid,sname,sdate,fac,doc,notes))
        for cat,note in [
            ("Medical","Preferred hospital: Valley Hospital Medical Center (620 Shadow Ln, Las Vegas NV 89106)"),
            ("Medical","DNR (Do Not Resuscitate) order on file with Dr. Ramirez and Valley Hospital — updated Jan 2026"),
            ("Medical","Healthcare Power of Attorney: daughter Sarah Johnson (702-555-0155)"),
            ("Legal","Will and Revocable Living Trust on file with Henderson Law Group — 702-555-0900"),
            ("Legal","Safe deposit box at Wells Fargo Summerlin branch — key in bedroom dresser top drawer"),
            ("Home","Spare house key with neighbor Mrs. Rosa Torres at 1236 Desert Sage Drive"),
            ("Insurance","Medicare supplement gap reviewed Oct 2025 with Thabang; plan adequate through 2026"),
            ("Financial","Social Security deposited 3rd Wednesday each month to Wells Fargo checking account"),
            ("Financial","RMDs from Fidelity IRA started 2015; quarterly statements mailed")]:
            db.execute("INSERT INTO important_notes (beneficiary_profile_id, category, note_text_encrypted, created_by) VALUES (?,?,?,?)",
                (pid,cat,_enc(note),uid))
        for cat,inst,phone,web,last4,docloc,trusted,notes in [
            ("Bank","Wells Fargo — Checking and Savings","1-800-869-3557","www.wellsfargo.com","7821","Home fireproof safe (master bedroom closet)","David Johnson (spouse)","Checking for bills; savings for medical emergencies"),
            ("Investment / Retirement","Fidelity — IRA","1-800-343-3548","www.fidelity.com","4892","Fireproof safe — Fidelity brokerage statement folder","Sarah Johnson (daughter)","RMDs started 2015; quarterly statements mailed"),
            ("Life Insurance","New York Life — Whole Life Policy","1-800-695-4331","www.newyorklife.com","","Fireproof safe — insurance folder","Sarah Johnson (daughter)","Policy #NYL-4471882; death benefit $50,000; David Johnson primary beneficiary"),
            ("Legal","Henderson Law Group — Estate Attorney","702-555-0900","","","Will and trust on file at attorney office","James Whitfield Esq.","Trust amended Jan 2024; successor trustee: Sarah Johnson"),
            ("Government","Social Security Administration","1-800-772-1213","www.ssa.gov","","Social Security card in fireproof safe","","Medicare Part A and B enrollment via SSA")]:
            db.execute("INSERT INTO financial_locators (beneficiary_profile_id, category, institution_name, contact_phone, website, last_four_only_encrypted, document_location, trusted_contact, notes_encrypted) VALUES (?,?,?,?,?,?,?,?,?)",
                (pid,cat,inst,phone,web,_enc(last4) if last4 else "",docloc,trusted,_enc(notes)))
    except Exception as e:
        import traceback; traceback.print_exc()


app = FastAPI(title="NorthStar Medicare Family File MVP", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=session_secret(), same_site="lax", https_only=False)

# ---------------------------------------------------------------------------
# Demo password gate — set DEMO_PASSWORD env var to enable
# ---------------------------------------------------------------------------

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "")

_GATE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NorthStar — Demo Access</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:system-ui,sans-serif;background:#0B1E38;min-height:100vh;display:flex;align-items:center;justify-content:center;}
.card{background:#fff;border-radius:16px;padding:2.5rem;width:100%;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,.3);}
.logo{display:flex;align-items:center;gap:.6rem;margin-bottom:1.75rem;}
.brand{font-family:Georgia,serif;font-size:1.4rem;font-weight:700;color:#0B1E38;}
.divider{width:36px;height:3px;background:#A4814D;border-radius:2px;margin-bottom:1.5rem;}
h1{font-family:Georgia,serif;font-size:1.3rem;color:#0B1E38;margin-bottom:.4rem;}
p{font-size:.88rem;color:#5A6478;margin-bottom:1.5rem;}
label{display:flex;flex-direction:column;gap:.3rem;font-weight:600;font-size:.88rem;margin-bottom:1rem;}
input{padding:.65rem .85rem;border:1.5px solid #C4CBD8;border-radius:8px;font:inherit;font-size:.95rem;}
input:focus{outline:none;border-color:#0B1E38;}
button{width:100%;padding:.75rem;background:#0B1E38;color:#fff;border:none;border-radius:8px;font:inherit;font-size:.95rem;font-weight:700;cursor:pointer;}
button:hover{background:#1A3256;}
.error{background:#FDE7E9;border:1px solid #F5B8BB;border-radius:6px;padding:.6rem .85rem;font-size:.85rem;color:#B3261E;margin-bottom:1rem;}
</style></head>
<body><div class="card">
<div class="logo">
<svg width="30" height="30" viewBox="0 0 34 34" fill="none">
<polygon points="3,27 3,7 8,7 17,19 17,7 22,7 22,27 17,27 8,15 8,27" fill="#0B1E38"/>
<path d="M25 3L26.1 7.9L31 9L26.1 10.1L25 15L23.9 10.1L19 9L23.9 7.9Z" fill="#A4814D"/>
</svg><span class="brand">NorthStar</span></div>
<div class="divider"></div>
<h1>Demo access</h1>
<p>This is a private demo. Enter the access password to continue.</p>
{error}
<form method="post" action="/demo-login">
<label>Password<input name="pw" type="password" autofocus placeholder="Enter demo password"></label>
<button type="submit">Enter demo</button>
</form>
</div></body></html>"""

_ALLOWED_PATHS = {"/demo-login", "/ping", "/login", "/register", "/logout"}

@app.middleware("http")
async def demo_gate_middleware(request: Request, call_next):
    if not DEMO_PASSWORD:
        return await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path.startswith("/accept-invite") or path.startswith("/seed-demo") or path in _ALLOWED_PATHS:
        return await call_next(request)
    if request.cookies.get("demo_access") == DEMO_PASSWORD:
        return await call_next(request)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_GATE_HTML.replace("{error}", ""))


@app.post("/demo-login")
async def demo_login_post(request: Request):
    from fastapi.responses import RedirectResponse, HTMLResponse
    form = await request.form()
    pw = str(form.get("pw", ""))
    if pw == DEMO_PASSWORD:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("demo_access", DEMO_PASSWORD, max_age=86400*7, httponly=True, samesite="lax")
        return resp
    return HTMLResponse(_GATE_HTML.replace("{error}", '<div class="error">Incorrect password. Try again.</div>'))

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    column: str | None = None
    type: str = "text"
    required: bool = False
    options: tuple[str, ...] = field(default_factory=tuple)
    encrypted: bool = False
    help: str = ""

    @property
    def db_column(self) -> str:
        return self.column or self.name


@dataclass(frozen=True)
class SectionConfig:
    key: str
    title: str
    singular: str
    table: str
    access_section: str
    profile_column: str = "beneficiary_profile_id"
    intro: str = ""
    warning: str = ""
    fields: tuple[FieldDef, ...] = field(default_factory=tuple)
    list_fields: tuple[str, ...] = field(default_factory=tuple)
    source_column: bool = True
    confirm_column: bool = True
    reject_sensitive: bool = False


SECTION_CONFIGS: dict[str, SectionConfig] = {
    "emergency-contacts": SectionConfig(
        key="emergency-contacts",
        title="Emergency Contacts & Next of Kin",
        singular="contact",
        table="trusted_people",
        access_section="emergency_contacts",
        intro="Add the people your family or caregivers should contact first.",
        fields=(
            FieldDef("name", "Name", required=True),
            FieldDef("relationship", "Relationship", type="select", required=True, options=("Spouse", "Child", "Sibling", "Relative", "Friend", "Legal guardian", "Other")),
            FieldDef("phone", "Phone", required=True),
            FieldDef("email", "Email"),
            FieldDef("address", "Address", type="textarea"),
            FieldDef("is_emergency_contact", "Emergency contact", type="checkbox"),
            FieldDef("priority_order", "Priority order", type="number"),
        ),
        list_fields=("name", "relationship", "phone", "email", "priority_order"),
        source_column=False,
        confirm_column=False,
    ),
    "medications": SectionConfig(
        key="medications",
        title="Medications",
        singular="medication",
        table="medications",
        access_section="medications",
        intro="Keep this list current so trusted family has accurate information in an emergency.",
        warning="This app does not replace medical advice from a doctor or pharmacist.",
        fields=(
            FieldDef("medication_name", "Medication name", required=True),
            FieldDef("dosage", "Dosage"),
            FieldDef("frequency", "Frequency"),
            FieldDef("pharmacy_name", "Pharmacy"),
            FieldDef("pharmacy_phone", "Pharmacy phone"),
            FieldDef("prescribing_doctor", "Prescribing doctor"),
            FieldDef("reason", "Reason for medication"),
            FieldDef("start_date", "Start date", type="date"),
            FieldDef("notes", "Notes", type="textarea"),
        ),
        list_fields=("medication_name", "dosage", "frequency", "pharmacy_name"),
    ),
    "allergies": SectionConfig(
        key="allergies",
        title="Allergies",
        singular="allergy",
        table="allergies",
        access_section="allergies",
        intro="Add food, medication, or other allergies. You can also add 'No known allergies'.",
        fields=(
            FieldDef("allergy_type", "Allergy type", type="select", required=True, options=("Food", "Medication", "Other", "No known allergies")),
            FieldDef("allergy_name", "Allergy name", required=True),
            FieldDef("reaction", "Reaction"),
            FieldDef("severity", "Severity", type="select", options=("Unknown", "Mild", "Moderate", "Severe")),
            FieldDef("notes", "Notes", type="textarea"),
        ),
        list_fields=("allergy_type", "allergy_name", "reaction", "severity"),
    ),
    "insurance": SectionConfig(
        key="insurance",
        title="Medicare & Insurance",
        singular="insurance policy",
        table="insurance_policies",
        access_section="insurance",
        intro="Add Medicare, Medicare Advantage, Medigap, Part D, dental, vision, or other coverage for annual reviews and emergency planning.",
        warning="Insurance cards may contain sensitive information. Only authorized people should access them.",
        fields=(
            FieldDef("policy_type", "Plan type", type="select", required=True, options=("Original Medicare", "Medicare Advantage", "Medicare Supplement / Medigap", "Part D Prescription Drug Plan", "Dental", "Vision", "Other", "I'm not sure")),
            FieldDef("insurance_company", "Insurance company"),
            FieldDef("plan_name", "Plan name"),
            FieldDef("plan_number", "Plan number"),
            FieldDef("member_id", "Member ID", column="member_id_encrypted", encrypted=True),
            FieldDef("rx_bin", "RxBIN", column="rx_bin_encrypted", encrypted=True),
            FieldDef("rx_pcn", "RxPCN", column="rx_pcn_encrypted", encrypted=True),
            FieldDef("group_number", "Group number", column="group_number_encrypted", encrypted=True),
            FieldDef("effective_date", "Effective date", type="date"),
            FieldDef("notes", "Notes", type="textarea"),
        ),
        list_fields=("policy_type", "insurance_company", "plan_name", "member_id"),
    ),
    "providers": SectionConfig(
        key="providers",
        title="PCP & Doctors",
        singular="provider",
        table="providers",
        access_section="providers",
        intro="Add the main doctor/PCP and any specialists needed for Medicare plan reviews, network checks, and emergency planning.",
        fields=(
            FieldDef("provider_type", "Provider type", type="select", required=True, options=("Primary care doctor / PCP", "Specialist", "Dentist", "Eye doctor", "Hospital", "Other")),
            FieldDef("name", "Doctor/provider name", required=True),
            FieldDef("practice_name", "Practice name"),
            FieldDef("specialty", "Specialty"),
            FieldDef("address", "Address", type="textarea"),
            FieldDef("phone", "Phone"),
            FieldDef("fax", "Fax"),
            FieldDef("doctor_network", "Doctor network"),
            FieldDef("patient_portal_url", "Patient portal link"),
            FieldDef("last_visit_date", "Last visit", type="date"),
            FieldDef("next_appointment_date", "Next appointment", type="date"),
            FieldDef("is_pcp", "This is my main doctor / PCP", type="checkbox"),
        ),
        list_fields=("name", "provider_type", "specialty", "phone"),
    ),
    "medicare-advisor": SectionConfig(
        key="medicare-advisor",
        title="Medicare Advisor / Agent of Record",
        singular="Medicare advisor",
        table="medicare_advisors",
        access_section="medicare_advisor",
        intro="Add the Medicare advisor or agent the beneficiary says helps with their coverage. This is beneficiary-provided and not carrier-verified in the MVP.",
        fields=(
            FieldDef("advisor_name", "Medicare advisor / agent name"),
            FieldDef("agency_name", "Agency name"),
            FieldDef("phone", "Phone"),
            FieldDef("email", "Email"),
            FieldDef("npn", "NPN, if known"),
            FieldDef("insurance_company", "Insurance company they helped with"),
            FieldDef("plan_name", "Plan name"),
            FieldDef("last_helped_date", "Last Medicare review or enrollment help", type="date"),
            FieldDef("notes", "Notes", type="textarea"),
        ),
        list_fields=("advisor_name", "agency_name", "phone", "insurance_company"),
    ),
    "surgeries": SectionConfig(
        key="surgeries",
        title="Surgeries",
        singular="surgery",
        table="surgeries",
        access_section="surgeries",
        intro="Add surgeries that family members or doctors should know about.",
        fields=(
            FieldDef("surgery_name", "Surgery", required=True),
            FieldDef("approximate_date", "Approximate date", type="date"),
            FieldDef("facility", "Hospital/facility"),
            FieldDef("doctor", "Doctor"),
            FieldDef("notes", "Notes", type="textarea"),
        ),
        list_fields=("surgery_name", "approximate_date", "facility", "doctor"),
        confirm_column=False,
    ),
    "important-notes": SectionConfig(
        key="important-notes",
        title="Important Info",
        singular="important note",
        table="important_notes",
        access_section="important_notes",
        intro="Add the things a family member would need to know if something happens.",
        warning="Do not enter passwords, PINs, Social Security numbers, or full financial account numbers.",
        fields=(
            FieldDef("category", "Category", type="select", required=True, options=("What family should know", "Home access", "Pets", "Preferred hospital", "Religious or personal wishes", "Bills or appointments", "Other")),
            FieldDef("note_text", "Note", column="note_text_encrypted", type="textarea", required=True, encrypted=True),
        ),
        list_fields=("category", "note_text"),
        source_column=False,
        confirm_column=False,
        reject_sensitive=True,
    ),
    "financial-locators": SectionConfig(
        key="financial-locators",
        title="Financial & Life Info Locator",
        singular="locator item",
        table="financial_locators",
        access_section="financial_locator",
        intro="Use this only to help family know which companies to contact and where documents are located.",
        warning="Do not enter passwords, PINs, full account numbers, full credit card numbers, CVV codes, Social Security numbers, or security question answers. Use last four digits only.",
        fields=(
            FieldDef("category", "Category", type="select", required=True, options=("Attorney", "Bank", "Credit card", "Subscription", "Loan", "Mortgage", "Auto loan", "Burial / funeral", "Other")),
            FieldDef("institution_name", "Institution / company / attorney", required=True),
            FieldDef("contact_phone", "Contact phone"),
            FieldDef("website", "Website"),
            FieldDef("last_four_only", "Last four digits only", column="last_four_only_encrypted", encrypted=True, help="Only enter the last four digits. Do not enter full account numbers."),
            FieldDef("document_location", "Where documents are located"),
            FieldDef("trusted_contact", "Trusted person to contact"),
            FieldDef("notes", "Notes", column="notes_encrypted", type="textarea", encrypted=True),
        ),
        list_fields=("category", "institution_name", "contact_phone", "last_four_only"),
        source_column=False,
        confirm_column=False,
        reject_sensitive=True,
    ),
}

ACCESS_SECTIONS = [
    ("emergency_contacts", "Emergency contacts / next of kin"),
    ("medications", "Medications"),
    ("allergies", "Allergies"),
    ("insurance", "Medicare & insurance"),
    ("providers", "PCP / doctors / providers"),
    ("medicare_advisor", "Medicare advisor / agent"),
    ("surgeries", "Surgeries"),
    ("legal_documents", "Legal documents"),
    ("important_notes", "Important info"),
    ("financial_locator", "Financial & life info locator"),
    ("photo_id", "Photo ID"),
]

DOC_TYPE_TO_SECTION = {
    "Medicare card": "insurance",
    "Insurance card": "insurance",
    "Photo ID": "photo_id",
    "Will": "legal_documents",
    "Trust": "legal_documents",
    "Advance directive": "legal_documents",
    "Living will": "legal_documents",
    "Health care power of attorney": "legal_documents",
    "Financial power of attorney": "legal_documents",
    "DNR / do-not-resuscitate document": "legal_documents",
    "Burial / prepaid funeral document": "financial_locator",
    "Other": "important_notes",
}

SENSITIVE_WORDS = re.compile(r"\b(password|passcode|pin|cvv|cvc|security question|social security|ssn|routing number|full account|account number|username|login)\b", re.I)
LONG_DIGIT_RUN = re.compile(r"\d[\d\s\-]{5,}\d")

# is_pcp is stored as "1"/"0" (checkbox via values_from_form). This set covers all
# truthy forms that might appear from DB or form replay.
_PCP_TRUTHY = {"1", "true", "True", "on"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def set_flash(request: Request, message: str, level: str = "info") -> None:
    request.session.setdefault("flashes", []).append({"message": message, "level": level})


def consume_flashes(request: Request) -> list[dict[str, str]]:
    flashes = request.session.get("flashes", [])
    request.session["flashes"] = []
    return flashes


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def audit(request: Request, profile_id: int | None, action: str, section: str | None = None, record_id: int | None = None) -> None:
    actor = request.session.get("user_id")
    db.execute(
        "INSERT INTO audit_logs (actor_user_id, beneficiary_profile_id, action, section, record_id, ip_address, device_info) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (actor, profile_id, action, section, record_id, client_ip(request), request.headers.get("user-agent", "")[:250]),
    )


def current_user(request: Request) -> dict[str, Any] | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    row = db.query_one("SELECT * FROM users WHERE id = ? AND status = 'active'", (user_id,))
    return row_to_dict(row)


def require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise PermissionError("You must be logged in.")
    return user


def parse_allowed_sections(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
        if isinstance(value, list):
            return [str(x) for x in value]
    except Exception:
        pass
    return []


def active_grants_for_user(user_id: int) -> list[dict[str, Any]]:
    rows = db.query(
        """
        SELECT ag.*, bp.full_name AS profile_name, tp.relationship AS relationship, tp.name AS trusted_name
        FROM access_grants ag
        JOIN beneficiary_profiles bp ON bp.id = ag.beneficiary_profile_id
        JOIN trusted_people tp ON tp.id = ag.trusted_person_id
        WHERE ag.recipient_user_id = ?
          AND ag.revoked_at IS NULL
          AND (ag.expires_at IS NULL OR ag.expires_at = '' OR date(ag.expires_at) >= date('now'))
        ORDER BY bp.full_name
        """,
        (user_id,),
    )
    return [dict(r) for r in rows]


def get_profile_context(request: Request, requested_profile_id: int | None = None) -> dict[str, Any]:
    user = require_user(request)
    profile_id = requested_profile_id or request.session.get("active_profile_id")

    def owner_ctx(profile: dict[str, Any]) -> dict[str, Any]:
        request.session["active_profile_id"] = profile["id"]
        return {"user": user, "profile": profile, "is_owner": True, "grant": None, "allowed_sections": ["all"], "can_edit": True, "can_upload": True, "can_download": True}

    def grant_ctx(grant: dict[str, Any]) -> dict[str, Any]:
        profile = row_to_dict(db.query_one("SELECT * FROM beneficiary_profiles WHERE id = ?", (grant["beneficiary_profile_id"],)))
        if not profile:
            raise PermissionError("Profile not found.")
        request.session["active_profile_id"] = profile["id"]
        return {
            "user": user,
            "profile": profile,
            "is_owner": False,
            "grant": grant,
            "allowed_sections": parse_allowed_sections(grant.get("allowed_sections")),
            "can_edit": bool(grant.get("can_edit")),
            "can_upload": bool(grant.get("can_upload")),
            "can_download": bool(grant.get("can_download")),
        }

    grants = active_grants_for_user(user["id"])

    if profile_id:
        owned = row_to_dict(db.query_one("SELECT * FROM beneficiary_profiles WHERE id = ? AND owner_user_id = ?", (profile_id, user["id"])))
        if owned:
            return owner_ctx(owned)
        for grant in grants:
            if int(grant["beneficiary_profile_id"]) == int(profile_id):
                return grant_ctx(grant)

    owned_default = row_to_dict(db.query_one("SELECT * FROM beneficiary_profiles WHERE owner_user_id = ? ORDER BY id LIMIT 1", (user["id"],)))
    if owned_default:
        return owner_ctx(owned_default)
    if grants:
        return grant_ctx(grants[0])
    raise PermissionError("You do not have access to a profile yet.")


def has_access(ctx: dict[str, Any], section: str, action: str = "view") -> bool:
    if ctx["is_owner"]:
        return True
    allowed = ctx["allowed_sections"]
    if "all" not in allowed and section not in allowed:
        return False
    if action == "view":
        return bool(ctx["grant"].get("can_view"))
    if action == "edit":
        return bool(ctx["can_edit"])
    if action == "upload":
        return bool(ctx["can_upload"])
    if action == "download":
        return bool(ctx["can_download"])
    return False


def require_section(ctx: dict[str, Any], section: str, action: str = "view") -> None:
    if not has_access(ctx, section, action):
        raise PermissionError("You do not have permission for that section.")


def base_context(request: Request, extra: dict[str, Any] | None = None, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "request": request,
        "user": ctx["user"] if ctx else current_user(request),
        "flashes": consume_flashes(request),
        "csrf_token": csrf_token(request.session),
        "sections": SECTION_CONFIGS,
        "access_sections": ACCESS_SECTIONS,
        "profile": ctx["profile"] if ctx else None,
        "is_owner": ctx["is_owner"] if ctx else False,
        "grant": ctx["grant"] if ctx else None,
        "can_edit": ctx["can_edit"] if ctx else False,
        "can_upload": ctx["can_upload"] if ctx else False,
        "can_download": ctx["can_download"] if ctx else False,
    }
    if extra:
        context.update(extra)
    return context


def render(request: Request, template: str, extra: dict[str, Any] | None = None, ctx: dict[str, Any] | None = None, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(request, template, base_context(request, extra, ctx), status_code=status_code)


def config_or_404(section_key: str) -> SectionConfig:
    if section_key not in SECTION_CONFIGS:
        raise HTTPException(status_code=404, detail="Section not found.")
    return SECTION_CONFIGS[section_key]


def _assert_safe_table(cfg: SectionConfig) -> None:
    """Guard against un-whitelisted table names in SectionConfig."""
    if cfg.table not in _VALID_TABLES:
        raise RuntimeError(f"SectionConfig references un-whitelisted table: {cfg.table!r}")
    if cfg.profile_column not in _VALID_PROFILE_COLUMNS:
        raise RuntimeError(f"SectionConfig references un-whitelisted profile_column: {cfg.profile_column!r}")


def _is_pcp(provider: dict[str, Any]) -> bool:
    """Return True if a provider record should appear in the PCP section of the review packet."""
    return str(provider.get("is_pcp", "0")) in _PCP_TRUTHY or provider.get("provider_type") == "Primary care doctor / PCP"


# Register template globals now that helper functions are defined
templates.env.globals["_is_pcp"] = _is_pcp


def values_from_form(form: Any, cfg: SectionConfig) -> tuple[dict[str, Any], str | None]:
    values: dict[str, Any] = {}
    for fd in cfg.fields:
        if fd.type == "checkbox":
            raw = "1" if form.get(fd.name) in ("1", "on", "true", "yes") else "0"
        else:
            raw = str(form.get(fd.name, "")).strip()
        if fd.required and not raw:
            return values, f"{fd.label} is required."
        if cfg.reject_sensitive and fd.name in {"note_text", "notes", "document_location", "last_four_only"}:
            if SENSITIVE_WORDS.search(raw):
                return values, "For safety, do not store passwords, PINs, CVV codes, SSNs, account numbers, usernames, or login details."
            if fd.name != "last_four_only" and LONG_DIGIT_RUN.search(raw):
                return values, "For safety, do not store long account numbers or Social Security numbers. Use last four digits only."
        if fd.name == "last_four_only" and raw and not re.fullmatch(r"\d{0,4}", raw):
            return values, "Last four digits must be four digits or fewer."
        values[fd.db_column] = encrypt_text(raw) if fd.encrypted else raw
    return values, None


def display_rows(cfg: SectionConfig, profile_id: int) -> list[dict[str, Any]]:
    _assert_safe_table(cfg)
    rows = db.query(f"SELECT * FROM {cfg.table} WHERE {cfg.profile_column} = ? ORDER BY id DESC", (profile_id,))
    output = []
    for row in rows:
        item = dict(row)
        for fd in cfg.fields:
            if fd.encrypted:
                item[fd.name] = decrypt_text(item.get(fd.db_column))
            elif fd.name not in item and fd.db_column in item:
                item[fd.name] = item.get(fd.db_column)
        output.append(item)
    return output


def display_record(cfg: SectionConfig, record_id: int, profile_id: int) -> dict[str, Any] | None:
    _assert_safe_table(cfg)
    row = db.query_one(f"SELECT * FROM {cfg.table} WHERE id = ? AND {cfg.profile_column} = ?", (record_id, profile_id))
    if not row:
        return None
    item = dict(row)
    for fd in cfg.fields:
        if fd.encrypted:
            item[fd.name] = decrypt_text(item.get(fd.db_column))
        elif fd.name not in item and fd.db_column in item:
            item[fd.name] = item.get(fd.db_column)
    return item


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    if not current_user(request):
        set_flash(request, str(exc), "warning")
        return redirect("/login")
    return render(request, "error.html", {"title": "Access denied", "message": str(exc)}, status_code=403)


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if current_user(request):
        return redirect("/dashboard")
    return render(request, "index.html")


@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return render(request, "register.html")


@app.post("/register")
async def register_post(request: Request):
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/register")
    email = str(form.get("email", "")).strip().lower()
    full_name = str(form.get("full_name", "")).strip()
    password = str(form.get("password", ""))
    date_of_birth = str(form.get("date_of_birth", "")).strip()
    phone = str(form.get("phone", "")).strip()
    if not email or not full_name or not password:
        set_flash(request, "Name, email, and password are required.", "danger")
        return redirect("/register")
    if db.query_one("SELECT id FROM users WHERE email = ?", (email,)):
        set_flash(request, "An account with that email already exists.", "danger")
        return redirect("/login")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        set_flash(request, str(exc), "danger")
        return redirect("/register")
    user_id = db.execute(
        "INSERT INTO users (email, phone, full_name, password_hash) VALUES (?, ?, ?, ?)",
        (email, phone, full_name, password_hash),
    )
    profile_id = db.execute(
        "INSERT INTO beneficiary_profiles (owner_user_id, full_name, date_of_birth, phone, email, last_reviewed_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (user_id, full_name, date_of_birth, phone, email),
    )
    request.session["user_id"] = user_id
    request.session["active_profile_id"] = profile_id
    audit(request, profile_id, "registered profile", "profile", profile_id)
    set_flash(request, "Profile created. Add emergency info first, then medication, doctor, and insurance details.", "success")
    return redirect("/dashboard")


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return render(request, "login.html")


@app.post("/login")
async def login_post(request: Request):
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/login")
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    user = row_to_dict(db.query_one("SELECT * FROM users WHERE email = ? AND status = 'active'", (email,)))
    if not user or not verify_password(password, user["password_hash"]):
        set_flash(request, "Invalid email or password.", "danger")
        return redirect("/login")
    request.session["user_id"] = user["id"]
    db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
    audit(request, None, "logged in", "auth")
    set_flash(request, "Signed in.", "success")
    return redirect("/dashboard")


@app.post("/logout")
async def logout(request: Request):
    # CSRF not required for logout: the session is being destroyed, not mutated with data.
    request.session.clear()
    return redirect("/")


# ---------------------------------------------------------------------------
# Authenticated routes
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, profile_id: int | None = None):
    ctx = get_profile_context(request, profile_id)
    profile = ctx["profile"]
    counts = {}
    for key, cfg in SECTION_CONFIGS.items():
        _assert_safe_table(cfg)
        counts[key] = db.query_one(f"SELECT COUNT(*) AS c FROM {cfg.table} WHERE {cfg.profile_column} = ?", (profile["id"],))["c"]
    doc_count = db.query_one("SELECT COUNT(*) AS c FROM documents WHERE beneficiary_profile_id = ?", (profile["id"],))["c"]
    trusted_count = db.query_one("SELECT COUNT(*) AS c FROM trusted_people WHERE beneficiary_profile_id = ?", (profile["id"],))["c"]
    profile_choices = []
    owned = db.query("SELECT id, full_name, 'owner' AS relation FROM beneficiary_profiles WHERE owner_user_id = ?", (ctx["user"]["id"],))
    for row in owned:
        profile_choices.append(dict(row))
    for grant in active_grants_for_user(ctx["user"]["id"]):
        profile_choices.append({"id": grant["beneficiary_profile_id"], "full_name": grant["profile_name"], "relation": grant["relationship"]})
    # Build readiness checklist counts for dashboard widget
    has_insurance = counts.get("insurance", 0) > 0
    has_meds = counts.get("medications", 0) > 0
    has_pcp = bool(db.query_one("SELECT id FROM providers WHERE beneficiary_profile_id = ? AND (is_pcp = 1 OR provider_type = 'Primary care doctor / PCP') LIMIT 1", (profile["id"],)))
    has_advisor = counts.get("medicare-advisor", 0) > 0
    has_emergency = counts.get("emergency-contacts", 0) > 0
    has_doc = doc_count > 0
    checklist_done = sum([has_insurance, has_meds, has_pcp, has_advisor, has_emergency, has_doc])
    checklist_total = 6
    audit(request, profile["id"], "viewed dashboard", "dashboard")
    return render(request, "dashboard.html", {"counts": counts, "doc_count": doc_count, "trusted_count": trusted_count, "profile_choices": profile_choices, "checklist_done": checklist_done, "checklist_total": checklist_total}, ctx)


@app.get("/medicare-review", response_class=HTMLResponse)
async def medicare_review(request: Request):
    ctx = get_profile_context(request)
    allowed_any = ctx["is_owner"] or any(
        has_access(ctx, section, "view")
        for section in ["insurance", "providers", "medications", "allergies", "medicare_advisor", "emergency_contacts"]
    )
    if not allowed_any:
        raise PermissionError("You do not have permission to view Medicare review prep.")

    profile_id = ctx["profile"]["id"]
    insurance = display_rows(SECTION_CONFIGS["insurance"], profile_id) if has_access(ctx, "insurance") else []
    medications = display_rows(SECTION_CONFIGS["medications"], profile_id) if has_access(ctx, "medications") else []
    providers = display_rows(SECTION_CONFIGS["providers"], profile_id) if has_access(ctx, "providers") else []
    advisors = display_rows(SECTION_CONFIGS["medicare-advisor"], profile_id) if has_access(ctx, "medicare_advisor") else []
    allergies = display_rows(SECTION_CONFIGS["allergies"], profile_id) if has_access(ctx, "allergies") else []
    documents = [
        dict(row)
        for row in db.query("SELECT * FROM documents WHERE beneficiary_profile_id = ? ORDER BY created_at DESC", (profile_id,))
        if has_access(ctx, dict(row)["access_section"], "view")
    ]
    insurance_docs = [d for d in documents if d.get("access_section") == "insurance"]
    pcp_list = [p for p in providers if _is_pcp(p)]
    checklist = [
        {"label": "Medicare or insurance plan added", "done": bool(insurance), "href": "/records/insurance"},
        {"label": "Insurance or Medicare card uploaded/location noted", "done": bool(insurance_docs), "href": "/documents"},
        {"label": "Medication list added", "done": bool(medications), "href": "/records/medications"},
        {"label": "Primary doctor / PCP added", "done": bool(pcp_list), "href": "/records/providers"},
        {"label": "Medicare advisor / agent added", "done": bool(advisors), "href": "/records/medicare-advisor"},
        {"label": "Emergency contact or next of kin added", "done": bool(db.query_one("SELECT id FROM trusted_people WHERE beneficiary_profile_id = ? LIMIT 1", (profile_id,))), "href": "/records/emergency-contacts"},
    ]
    complete_count = sum(1 for item in checklist if item["done"])
    # Medicare card data
    mc_row = db.query_one("SELECT * FROM medicare_cards WHERE beneficiary_profile_id = ?", (profile_id,))
    medicare_card = None
    if mc_row:
        mc = dict(mc_row)
        mc["mbi"] = decrypt_text(mc.get("mbi_encrypted"))
        medicare_card = mc
    audit(request, profile_id, "viewed Medicare review prep", "medicare_review")
    return render(
        request,
        "medicare_review.html",
        {
            "checklist": checklist,
            "complete_count": complete_count,
            "insurance": insurance,
            "medications": medications,
            "providers": providers,
            "pcp_list": pcp_list,
            "advisors": advisors,
            "allergies": allergies,
            "documents": documents,
            "insurance_docs": insurance_docs,
            "medicare_card": medicare_card,
        },
        ctx,
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_get(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"]:
        require_section(ctx, "personal", "view")
    audit(request, ctx["profile"]["id"], "viewed profile", "profile")
    return render(request, "profile.html", {}, ctx)


@app.post("/profile")
async def profile_post(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"] and not ctx["can_edit"]:
        raise PermissionError("Only the beneficiary or an authorized editor can update this profile.")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/profile")
    fields = ["full_name", "preferred_name", "date_of_birth", "address_line_1", "address_line_2", "city", "state", "zip", "phone", "email", "preferred_language"]
    values = [str(form.get(f, "")).strip() for f in fields]
    db.execute(
        """
        UPDATE beneficiary_profiles
        SET full_name = ?, preferred_name = ?, date_of_birth = ?, address_line_1 = ?, address_line_2 = ?, city = ?, state = ?, zip = ?, phone = ?, email = ?, preferred_language = ?, updated_at = CURRENT_TIMESTAMP, last_reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (*values, ctx["profile"]["id"]),
    )
    audit(request, ctx["profile"]["id"], "updated profile", "profile", ctx["profile"]["id"])
    set_flash(request, "Profile updated.", "success")
    return redirect("/profile")


# ---------------------------------------------------------------------------
# Generic section record routes
# ---------------------------------------------------------------------------

@app.get("/records/{section_key}", response_class=HTMLResponse)
async def record_list(request: Request, section_key: str):
    cfg = config_or_404(section_key)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "view")
    records = display_rows(cfg, ctx["profile"]["id"])
    audit(request, ctx["profile"]["id"], "viewed section", cfg.access_section)
    return render(request, "record_list.html", {"cfg": cfg, "records": records}, ctx)


@app.get("/records/{section_key}/new", response_class=HTMLResponse)
async def record_new_get(request: Request, section_key: str):
    cfg = config_or_404(section_key)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "edit")
    return render(request, "record_form.html", {"cfg": cfg, "record": {}, "mode": "new"}, ctx)


@app.post("/records/{section_key}/new")
async def record_new_post(request: Request, section_key: str):
    cfg = config_or_404(section_key)
    _assert_safe_table(cfg)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "edit")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect(f"/records/{section_key}")
    values, error = values_from_form(form, cfg)
    if error:
        set_flash(request, error, "danger")
        return render(request, "record_form.html", {"cfg": cfg, "record": dict(form), "mode": "new"}, ctx)
    columns = [cfg.profile_column] + list(values.keys())
    params: list[Any] = [ctx["profile"]["id"]] + list(values.values())
    if cfg.source_column:
        columns.append("source")
        params.append(f"{ctx['user']['full_name']} ({'beneficiary' if ctx['is_owner'] else 'trusted person'})")
    sql = f"INSERT INTO {cfg.table} ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
    db.execute(sql, params)
    record_id = db.last_insert_id()
    audit(request, ctx["profile"]["id"], "created record", cfg.access_section, record_id)
    set_flash(request, f"{cfg.singular.title()} added.", "success")
    return redirect(f"/records/{section_key}")


@app.get("/records/{section_key}/{record_id}/edit", response_class=HTMLResponse)
async def record_edit_get(request: Request, section_key: str, record_id: int):
    cfg = config_or_404(section_key)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "edit")
    record = display_record(cfg, record_id, ctx["profile"]["id"])
    if not record:
        raise PermissionError("Record not found.")
    return render(request, "record_form.html", {"cfg": cfg, "record": record, "mode": "edit"}, ctx)


@app.post("/records/{section_key}/{record_id}/edit")
async def record_edit_post(request: Request, section_key: str, record_id: int):
    cfg = config_or_404(section_key)
    _assert_safe_table(cfg)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "edit")
    if not display_record(cfg, record_id, ctx["profile"]["id"]):
        raise PermissionError("Record not found.")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect(f"/records/{section_key}")
    values, error = values_from_form(form, cfg)
    if error:
        set_flash(request, error, "danger")
        return render(request, "record_form.html", {"cfg": cfg, "record": dict(form), "mode": "edit"}, ctx)
    assignments = [f"{col} = ?" for col in values.keys()]
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    if cfg.confirm_column:
        assignments.append("last_confirmed_at = CURRENT_TIMESTAMP")
    params = list(values.values()) + [record_id, ctx["profile"]["id"]]
    db.execute(f"UPDATE {cfg.table} SET {', '.join(assignments)} WHERE id = ? AND {cfg.profile_column} = ?", params)
    audit(request, ctx["profile"]["id"], "updated record", cfg.access_section, record_id)
    set_flash(request, f"{cfg.singular.title()} updated.", "success")
    return redirect(f"/records/{section_key}")


@app.post("/records/{section_key}/{record_id}/delete")
async def record_delete(request: Request, section_key: str, record_id: int):
    cfg = config_or_404(section_key)
    _assert_safe_table(cfg)
    ctx = get_profile_context(request)
    require_section(ctx, cfg.access_section, "edit")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect(f"/records/{section_key}")
    db.execute(f"DELETE FROM {cfg.table} WHERE id = ? AND {cfg.profile_column} = ?", (record_id, ctx["profile"]["id"]))
    audit(request, ctx["profile"]["id"], "deleted record", cfg.access_section, record_id)
    set_flash(request, f"{cfg.singular.title()} deleted.", "success")
    return redirect(f"/records/{section_key}")


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@app.get("/documents", response_class=HTMLResponse)
async def documents_get(request: Request):
    ctx = get_profile_context(request)
    rows = db.query("SELECT * FROM documents WHERE beneficiary_profile_id = ? ORDER BY created_at DESC", (ctx["profile"]["id"],))
    documents = [dict(row) for row in rows if has_access(ctx, dict(row)["access_section"], "view")]
    audit(request, ctx["profile"]["id"], "viewed documents", "documents")
    return render(request, "documents.html", {"documents": documents, "doc_types": list(DOC_TYPE_TO_SECTION.keys()), "max_mb": MAX_UPLOAD_BYTES // (1024 * 1024)}, ctx)


@app.post("/documents")
async def documents_post(request: Request):
    ctx = get_profile_context(request)
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/documents")
    document_type = str(form.get("document_type", "Other")).strip() or "Other"
    access_section = DOC_TYPE_TO_SECTION.get(document_type, "important_notes")
    require_section(ctx, access_section, "upload" if not ctx["is_owner"] else "edit")
    display_name = str(form.get("display_name", "")).strip() or document_type
    document_location_text = str(form.get("document_location_text", "")).strip()
    notes = str(form.get("notes", "")).strip()
    file = form.get("file")
    encrypted_filename = None
    file_sha256 = None
    file_size = None
    original_filename = None
    mime_type = None
    if hasattr(file, "filename") and getattr(file, "filename", ""):
        original_filename = Path(file.filename).name
        # Sanitize before storing: strip chars that could cause Content-Disposition injection.
        # The actual file is saved under a UUID, so the stored name is display/header only.
        original_filename = re.sub(r'[^\w\s.\-]', '_', original_filename)
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            set_flash(request, "Allowed uploads: PDF, PNG, JPG, JPEG, WEBP, or TXT.", "danger")
            return redirect("/documents")
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_UPLOAD_BYTES:
            set_flash(request, f"File is too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", "danger")
            return redirect("/documents")
        file_sha256 = hashlib.sha256(content).hexdigest()
        encrypted_filename = f"{uuid.uuid4().hex}.fernet"
        (UPLOAD_DIR / encrypted_filename).write_bytes(encrypt_bytes(content))
        mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    if not encrypted_filename and not document_location_text:
        set_flash(request, "Upload a file or enter where the original document is located.", "danger")
        return redirect("/documents")
    db.execute(
        """
        INSERT INTO documents (beneficiary_profile_id, document_type, display_name, original_filename, encrypted_filename, file_sha256, file_size, mime_type, document_location_text, notes, uploaded_by, access_section)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ctx["profile"]["id"], document_type, display_name, original_filename, encrypted_filename, file_sha256, file_size, mime_type, document_location_text, notes, ctx["user"]["id"], access_section),
    )
    audit(request, ctx["profile"]["id"], "uploaded document" if encrypted_filename else "added document location", access_section, doc_id)
    set_flash(request, "Document saved.", "success")
    return redirect("/documents")


@app.get("/documents/{document_id}/download")
async def document_download(request: Request, document_id: int):
    ctx = get_profile_context(request)
    row = row_to_dict(db.query_one("SELECT * FROM documents WHERE id = ? AND beneficiary_profile_id = ?", (document_id, ctx["profile"]["id"])))
    if not row or not row.get("encrypted_filename"):
        raise PermissionError("Document not found.")
    require_section(ctx, row["access_section"], "download")
    # Resolve and confirm path stays inside UPLOAD_DIR to prevent traversal.
    path = (UPLOAD_DIR / row["encrypted_filename"]).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()):
        raise PermissionError("Invalid file path.")
    if not path.exists():
        raise PermissionError("Encrypted file is missing.")
    data = decrypt_bytes(path.read_bytes())
    audit(request, ctx["profile"]["id"], "downloaded document", row["access_section"], document_id)
    filename = row.get("original_filename") or f"northstar-document-{document_id}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([data]), media_type=row.get("mime_type") or "application/octet-stream", headers=headers)


@app.post("/documents/{document_id}/delete")
async def document_delete(request: Request, document_id: int):
    ctx = get_profile_context(request)
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/documents")
    row = row_to_dict(db.query_one("SELECT * FROM documents WHERE id = ? AND beneficiary_profile_id = ?", (document_id, ctx["profile"]["id"])))
    if not row:
        raise PermissionError("Document not found.")
    require_section(ctx, row["access_section"], "edit")
    if row.get("encrypted_filename"):
        try:
            (UPLOAD_DIR / row["encrypted_filename"]).unlink(missing_ok=True)
        except OSError:
            pass
    db.execute("DELETE FROM documents WHERE id = ? AND beneficiary_profile_id = ?", (document_id, ctx["profile"]["id"]))
    audit(request, ctx["profile"]["id"], "deleted document", row["access_section"], document_id)
    set_flash(request, "Document deleted.", "success")
    return redirect("/documents")


# ---------------------------------------------------------------------------
# Family access
# ---------------------------------------------------------------------------

@app.get("/family-access", response_class=HTMLResponse)
async def family_access_get(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"]:
        raise PermissionError("Only the beneficiary/profile owner can manage family access.")
    trusted = db.query(
        """
        SELECT tp.*, ag.id AS grant_id, ag.access_level, ag.allowed_sections, ag.can_edit, ag.can_upload, ag.can_download, ag.expires_at, ag.revoked_at, ag.recipient_user_id
        FROM trusted_people tp
        LEFT JOIN access_grants ag ON ag.trusted_person_id = tp.id AND ag.revoked_at IS NULL
        WHERE tp.beneficiary_profile_id = ?
        ORDER BY tp.created_at DESC
        """,
        (ctx["profile"]["id"],),
    )
    people = []
    for row in trusted:
        item = dict(row)
        item["allowed_sections_list"] = parse_allowed_sections(item.get("allowed_sections"))
        people.append(item)
    audit(request, ctx["profile"]["id"], "viewed family access", "family_access")
    return render(request, "family_access.html", {"people": people}, ctx)


@app.post("/family-access/invite")
async def family_access_invite(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"]:
        raise PermissionError("Only the beneficiary/profile owner can manage family access.")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/family-access")
    name = str(form.get("name", "")).strip()
    relationship = str(form.get("relationship", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    phone = str(form.get("phone", "")).strip()
    sections = [s for s, _ in ACCESS_SECTIONS if form.get(f"section_{s}")]
    if not name or not relationship or not email or not sections:
        set_flash(request, "Name, relationship, email, and at least one section are required.", "danger")
        return redirect("/family-access")
    token = new_token(32)
    db.execute(
        "INSERT INTO trusted_people (beneficiary_profile_id, name, relationship, email, phone, invite_token, invite_status) VALUES (?, ?, ?, ?, ?, ?, 'sent')",
        (ctx["profile"]["id"], name, relationship, email, phone, token),
    )
    trusted_person_id = db.last_insert_id()
    access_level = str(form.get("access_level", "viewer"))
    can_edit = 1 if access_level in {"editor", "manager"} else 0
    can_upload = 1 if access_level in {"editor", "manager"} else 0
    can_download = 1 if form.get("can_download") else 0
    expires_at = str(form.get("expires_at", "")).strip() or None
    signature = str(form.get("electronic_signature", "")).strip() or ctx["profile"]["full_name"]
    db.execute(
        """
        INSERT INTO access_grants (beneficiary_profile_id, trusted_person_id, access_level, allowed_sections, can_view, can_edit, can_upload, can_download, expires_at, electronic_signature, signed_at, created_by)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
        (ctx["profile"]["id"], trusted_person_id, access_level, json.dumps(sections), can_edit, can_upload, can_download, expires_at, signature, ctx["user"]["id"]),
    )
    grant_id = db.last_insert_id()
    audit(request, ctx["profile"]["id"], "granted family access", "family_access", grant_id)
    invite_url = str(request.url_for("accept_invite_get", token=token))
    set_flash(request, f"Family access created. Copy this invite link: {invite_url}", "success")
    return redirect("/family-access")


@app.post("/family-access/{grant_id}/revoke")
async def family_access_revoke(request: Request, grant_id: int):
    ctx = get_profile_context(request)
    if not ctx["is_owner"]:
        raise PermissionError("Only the beneficiary/profile owner can manage family access.")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/family-access")
    db.execute("UPDATE access_grants SET revoked_at = CURRENT_TIMESTAMP WHERE id = ? AND beneficiary_profile_id = ?", (grant_id, ctx["profile"]["id"]))
    audit(request, ctx["profile"]["id"], "revoked family access", "family_access", grant_id)
    set_flash(request, "Access revoked.", "success")
    return redirect("/family-access")


# ---------------------------------------------------------------------------
# Invite acceptance
# ---------------------------------------------------------------------------

@app.get("/accept-invite/{token}", response_class=HTMLResponse, name="accept_invite_get")
async def accept_invite_get(request: Request, token: str):
    row = row_to_dict(db.query_one(
        """
        SELECT tp.*, bp.full_name AS profile_name, ag.id AS grant_id, ag.allowed_sections, ag.access_level, ag.expires_at, ag.revoked_at
        FROM trusted_people tp
        JOIN access_grants ag ON ag.trusted_person_id = tp.id
        JOIN beneficiary_profiles bp ON bp.id = tp.beneficiary_profile_id
        WHERE tp.invite_token = ?
        """,
        (token,),
    ))
    if not row or row.get("revoked_at"):
        return render(request, "error.html", {"title": "Invite unavailable", "message": "This invite link is invalid or has been revoked."}, status_code=404)
    return render(request, "accept_invite.html", {"invite": row, "allowed": parse_allowed_sections(row.get("allowed_sections")), "token": token})


@app.post("/accept-invite/{token}")
async def accept_invite_post(request: Request, token: str):
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect(f"/accept-invite/{token}")
    invite = row_to_dict(db.query_one(
        """
        SELECT tp.*, ag.id AS grant_id
        FROM trusted_people tp
        JOIN access_grants ag ON ag.trusted_person_id = tp.id
        WHERE tp.invite_token = ? AND ag.revoked_at IS NULL
        """,
        (token,),
    ))
    if not invite:
        raise PermissionError("Invite unavailable.")
    user = current_user(request)
    if not user:
        email = str(form.get("email", "")).strip().lower()
        full_name = str(form.get("full_name", "")).strip()
        password = str(form.get("password", ""))
        if email != invite["email"]:
            set_flash(request, "Use the email address that received the invite.", "danger")
            return redirect(f"/accept-invite/{token}")
        existing = row_to_dict(db.query_one("SELECT * FROM users WHERE email = ?", (email,)))
        if existing:
            if not verify_password(password, existing["password_hash"]):
                set_flash(request, "That email already exists. Enter the correct password to accept the invite.", "danger")
                return redirect(f"/accept-invite/{token}")
            user = existing
        else:
            try:
                password_hash = hash_password(password)
            except ValueError as exc:
                set_flash(request, str(exc), "danger")
                return redirect(f"/accept-invite/{token}")
            db.execute("INSERT INTO users (email, full_name, password_hash) VALUES (?, ?, ?)", (email, full_name or invite["name"], password_hash))
            user_id = db.last_insert_id()
            user = row_to_dict(db.query_one("SELECT * FROM users WHERE id = ?", (user_id,)))
        request.session["user_id"] = user["id"]
    db.execute("UPDATE access_grants SET recipient_user_id = ? WHERE id = ?", (user["id"], invite["grant_id"]))
    db.execute("UPDATE trusted_people SET invite_status = 'accepted', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (invite["id"],))
    request.session["active_profile_id"] = invite["beneficiary_profile_id"]
    audit(request, invite["beneficiary_profile_id"], "accepted family invite", "family_access", invite["grant_id"])
    set_flash(request, "Invite accepted. You can now see the sections authorized for you.", "success")
    return redirect("/dashboard")


# ---------------------------------------------------------------------------
# Emergency card, audit log, mark reviewed
# ---------------------------------------------------------------------------

@app.get("/emergency-card", response_class=HTMLResponse)
async def emergency_card(request: Request):
    ctx = get_profile_context(request)
    require_section(ctx, "emergency_contacts", "view")
    profile_id = ctx["profile"]["id"]
    contacts = [dict(r) for r in db.query("SELECT * FROM trusted_people WHERE beneficiary_profile_id = ? AND is_emergency_contact = 1 ORDER BY priority_order ASC", (profile_id,))]
    meds = display_rows(SECTION_CONFIGS["medications"], profile_id) if has_access(ctx, "medications") else []
    allergies = display_rows(SECTION_CONFIGS["allergies"], profile_id) if has_access(ctx, "allergies") else []
    providers = display_rows(SECTION_CONFIGS["providers"], profile_id) if has_access(ctx, "providers") else []
    insurance = display_rows(SECTION_CONFIGS["insurance"], profile_id) if has_access(ctx, "insurance") else []
    notes = display_rows(SECTION_CONFIGS["important-notes"], profile_id) if has_access(ctx, "important_notes") else []
    audit(request, profile_id, "viewed emergency card", "emergency_card")
    return render(request, "emergency_card.html", {"contacts": contacts, "meds": meds, "allergies": allergies, "providers": providers, "insurance": insurance, "notes": notes}, ctx)


@app.get("/audit", response_class=HTMLResponse)
async def audit_log(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"]:
        raise PermissionError("Only the beneficiary/profile owner can view the audit log.")
    rows = db.query(
        """
        SELECT al.*, u.full_name AS actor_name
        FROM audit_logs al
        LEFT JOIN users u ON u.id = al.actor_user_id
        WHERE al.beneficiary_profile_id = ?
        ORDER BY al.created_at DESC
        LIMIT 250
        """,
        (ctx["profile"]["id"],),
    )
    return render(request, "audit.html", {"logs": [dict(r) for r in rows]}, ctx)


@app.post("/mark-reviewed")
async def mark_reviewed(request: Request):
    ctx = get_profile_context(request)
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/dashboard")
    if not ctx["is_owner"] and not ctx["can_edit"]:
        raise PermissionError("Only authorized editors can mark a profile reviewed.")
    db.execute("UPDATE beneficiary_profiles SET last_reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (ctx["profile"]["id"],))
    audit(request, ctx["profile"]["id"], "marked reviewed", "profile")
    set_flash(request, "Profile marked reviewed.", "success")
    return redirect("/dashboard")


# ---------------------------------------------------------------------------
# Medicare card route
# ---------------------------------------------------------------------------

@app.get("/medicare-card-data")
async def medicare_card_data(request: Request):
    """Helper: returns medicare card for a profile as dict, or None."""
    ctx = get_profile_context(request)
    row = db.query_one("SELECT * FROM medicare_cards WHERE beneficiary_profile_id = ?", (ctx["profile"]["id"],))
    if not row:
        return None
    item = dict(row)
    item["mbi"] = decrypt_text(item.get("mbi_encrypted"))
    return item


@app.post("/medicare-card")
async def medicare_card_post(request: Request):
    ctx = get_profile_context(request)
    if not ctx["is_owner"] and not ctx["can_edit"]:
        raise PermissionError("Only authorized editors can update Medicare card information.")
    form = await request.form()
    if not validate_csrf(request.session, form.get("_csrf")):
        set_flash(request, "Security check failed. Try again.", "danger")
        return redirect("/medicare-review")
    mbi_raw = str(form.get("mbi", "")).strip()
    name_on_card = str(form.get("name_on_card", "")).strip()
    part_a_date = str(form.get("part_a_date", "")).strip() or None
    part_b_date = str(form.get("part_b_date", "")).strip() or None
    mbi_encrypted = encrypt_text(mbi_raw) if mbi_raw else None
    existing = db.query_one("SELECT id FROM medicare_cards WHERE beneficiary_profile_id = ?", (ctx["profile"]["id"],))
    if existing:
        db.execute(
            "UPDATE medicare_cards SET mbi_encrypted = ?, name_on_card = ?, part_a_date = ?, part_b_date = ?, updated_at = CURRENT_TIMESTAMP WHERE beneficiary_profile_id = ?",
            (mbi_encrypted, name_on_card, part_a_date, part_b_date, ctx["profile"]["id"]),
        )
    else:
        db.execute(
            "INSERT INTO medicare_cards (beneficiary_profile_id, mbi_encrypted, name_on_card, part_a_date, part_b_date) VALUES (?, ?, ?, ?, ?)",
            (ctx["profile"]["id"], mbi_encrypted, name_on_card, part_a_date, part_b_date),
        )
    audit(request, ctx["profile"]["id"], "updated Medicare card", "medicare_card")
    set_flash(request, "Medicare card information saved.", "success")
    return redirect("/medicare-review")


# ---------------------------------------------------------------------------
# One-time demo seed route — disabled after first use
# ---------------------------------------------------------------------------

@app.get("/seed-demo/{token}")
async def seed_demo(token: str, request: Request):
    from fastapi.responses import HTMLResponse
    seed_token = os.getenv("SEED_TOKEN", "")
    if not seed_token or token != seed_token:
        raise HTTPException(status_code=404)

    existing = db.query_one("SELECT id FROM users WHERE email = ?", ("demo@northstar-demo.com",))
    if existing:
        return HTMLResponse("<h2 style=\"font-family:Georgia,serif;padding:2rem;color:#0B1E38\">Already seeded.<br><br>Email: demo@northstar-demo.com<br>Password: NorthStarDemo2026!<br><br><a href=\"/\">Sign in →</a></h2>")

    from app.security import hash_password
    from app.crypto import encrypt_text

    # ── User ──
    uid = db.execute("INSERT INTO users (email, phone, full_name, password_hash, role, status) VALUES (?,?,?,?,?,?)",
        ("demo@northstar-demo.com","702-555-0100","Mary Johnson", hash_password("NorthStarDemo2026!"), "user","active"))

    # ── Profile — every field ──
    pid = db.execute("""INSERT INTO beneficiary_profiles
        (owner_user_id, full_name, preferred_name, date_of_birth,
         address_line_1, address_line_2, city, state, zip,
         phone, email, preferred_language, last_reviewed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid,"Mary Johnson","Mary","1945-03-15",
         "1234 Desert Sage Drive","Unit 1","Las Vegas","NV","89117",
         "702-555-0100","mary.johnson@example.com","English","2026-07-01"))

    # ── Medicare Card — every field ──
    db.execute("""INSERT INTO medicare_cards
        (beneficiary_profile_id, mbi_encrypted, name_on_card, part_a_date, part_b_date)
        VALUES (?,?,?,?,?)""",
        (pid, encrypt_text("1EG4-TE5-MK72"), "MARY L JOHNSON", "2010-03-01", "2010-03-01"))

    # ── Emergency contacts / trusted people — every field ──
    for name,rel,phone,email,addr,pri in [
        ("David Johnson","Spouse","702-555-0101","david.johnson@example.com","1234 Desert Sage Drive, Las Vegas NV 89117",1),
        ("Sarah Johnson","Daughter","702-555-0155","sarah.johnson@example.com","5678 Sunrise Blvd, Henderson NV 89002",2),
        ("Michael Torres","Son","702-555-0188","michael.torres@example.com","900 Lake Mead Pkwy, Las Vegas NV 89015",3),
    ]:
        db.execute("""INSERT INTO trusted_people
            (beneficiary_profile_id, name, relationship, phone, email, address,
             is_emergency_contact, priority_order, invite_status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (pid,name,rel,phone,email,addr,1,pri,"created"))

    # ── Medications — every field ──
    for mn,dose,freq,ph,phph,doc,rsn,start,notes in [
        ("Metformin","500 mg","Twice daily with meals","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Type 2 diabetes — blood sugar management","2018-01-15","Take with food to reduce stomach upset"),
        ("Lisinopril","10 mg","Once daily in the morning","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","High blood pressure","2018-03-01","Monitor for dry cough; avoid potassium supplements"),
        ("Atorvastatin","20 mg","Once daily at bedtime","Walgreens — Summerlin","702-555-0210","Dr. Kevin Park","High cholesterol management","2020-07-15","Avoid grapefruit juice"),
        ("Aspirin","81 mg","Once daily","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Cardiac prevention — heart health","2018-01-15","Take with water; do not crush"),
        ("Amlodipine","5 mg","Once daily","Walgreens — Summerlin","702-555-0210","Dr. Kevin Park","Chest pain / angina management","2021-04-10","May cause ankle swelling"),
        ("Vitamin D3","2000 IU","Once daily with breakfast","","","Dr. Elena Ramirez","Bone health / deficiency","2019-06-01","OTC supplement"),
    ]:
        db.execute("""INSERT INTO medications
            (beneficiary_profile_id, medication_name, dosage, frequency,
             pharmacy_name, pharmacy_phone, prescribing_doctor, reason, start_date, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pid,mn,dose,freq,ph,phph,doc,rsn,start,notes))

    # ── Providers — every field ──
    for pn,pt,sp,prac,addr,ph,fx,net,portal,pcp,lv,na,notes in [
        ("Dr. Elena Ramirez","Primary care doctor / PCP","Family Medicine","Desert Springs Medical Group",
         "2075 E Flamingo Rd, Las Vegas NV 89119","702-555-0140","702-555-0141",
         "Humana Gold Plus PPO","https://mydesertsprings.com",1,"2026-05-12","2026-11-10",
         "Long-time PCP; Spanish spoken; fasting labs before annual visit"),
        ("Dr. Kevin Park","Specialist","Cardiology","Nevada Heart Associates",
         "3121 S Maryland Pkwy Ste 400, Las Vegas NV 89109","702-555-0188","702-555-0189",
         "Humana Gold Plus PPO","https://nevadaheart.com",0,"2026-03-20","2026-09-20",
         "Annual echo scheduled; wear comfortable clothing for stress test"),
        ("Desert Eye Associates","Eye Doctor","Ophthalmology","Desert Eye Associates",
         "8551 W Lake Mead Blvd, Las Vegas NV 89128","702-555-0210","702-555-0211",
         "","",0,"2026-01-15","2027-01-15","Dilation required; bring sunglasses"),
        ("Dr. Patricia Hill","Dentist","General Dentistry","Summerlin Dental Care",
         "1980 Village Center Cir, Las Vegas NV 89134","702-555-0230","702-555-0231",
         "","",0,"2026-04-08","2026-10-08","Cleaning every 6 months; X-rays annually"),
    ]:
        db.execute("""INSERT INTO providers
            (beneficiary_profile_id, name, provider_type, specialty, practice_name,
             address, phone, fax, doctor_network, patient_portal_url,
             last_visit_date, next_appointment_date, is_pcp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid,pn,pt,sp,prac,addr,ph,fx,net,portal,lv,na,pcp))

    # ── Allergies — every field ──
    for an,at,rx,sv,notes in [
        ("Penicillin","Medication","Hives, facial swelling, difficulty breathing — anaphylaxis risk","Severe","Listed on hospital wristband; carry epinephrine"),
        ("Shellfish (shrimp, crab, lobster)","Food","Anaphylaxis — throat swelling, vomiting","Severe","Epinephrine auto-injector prescribed; avoid cross-contamination"),
        ("Sulfa drugs","Medication","Rash, fever, joint pain","Moderate","No sulfonamide antibiotics"),
        ("Latex","Environmental","Skin irritation, hives","Mild","Alert surgical teams; use latex-free gloves"),
        ("Ragweed / Pollen","Environmental","Nasal congestion, sneezing, watery eyes","Mild","Seasonal — peaks Aug–Oct in Las Vegas"),
    ]:
        db.execute("""INSERT INTO allergies
            (beneficiary_profile_id, allergy_name, allergy_type, reaction, severity, notes)
            VALUES (?,?,?,?,?,?)""",
            (pid,an,at,rx,sv,notes))

    # ── Insurance — every field ──
    db.execute("""INSERT INTO insurance_policies
        (beneficiary_profile_id, policy_type, insurance_company, plan_name,
         plan_number, member_id_encrypted, rx_bin_encrypted, rx_pcn_encrypted,
         group_number_encrypted, effective_date, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (pid,"Medicare Advantage (Part C)","Humana","Gold Plus H5619-003",
         "H5619-003", encrypt_text("H5619-4821-00"), encrypt_text("610014"),
         encrypt_text("MEDDADV"), encrypt_text("N/A"), "2026-01-01",
         "OOP max $5,000 in-network; $0 copay PCP; $45 specialist; includes dental, vision, hearing"))

    db.execute("""INSERT INTO insurance_policies
        (beneficiary_profile_id, policy_type, insurance_company, plan_name,
         plan_number, member_id_encrypted, rx_bin_encrypted, rx_pcn_encrypted,
         effective_date, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pid,"Part D Prescription Drug","SilverScript Choice (CVS)","SilverScript Choice",
         "S5601-068", encrypt_text("SS-9234-7701"), encrypt_text("004336"),
         encrypt_text("ADV"), "2026-01-01",
         "Preferred pharmacy: CVS; Tier 1-2 generics $0-$10; mail order available"))

    db.execute("""INSERT INTO insurance_policies
        (beneficiary_profile_id, policy_type, insurance_company, plan_name,
         member_id_encrypted, effective_date, notes)
        VALUES (?,?,?,?,?,?,?)""",
        (pid,"Medicare Part A & B (Original Medicare)","CMS / Social Security",
         "Original Medicare", encrypt_text("1EG4-TE5-MK72"),
         "2010-03-01","Used as secondary when traveling; keep red-white-blue card in wallet"))

    # ── Medicare Advisor — every field ──
    db.execute("""INSERT INTO medicare_advisors
        (beneficiary_profile_id, advisor_name, agency_name, phone, email,
         npn, insurance_company, plan_name, last_helped_date, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pid,"Thabang Kesiilwe","Kesiilwe Insurance","702-555-0177",
         "kgosi.kesiilwe@gmail.com","12345678",
         "Humana","Gold Plus H5619","2025-10-15",
         "Annual review every Oct–Nov; call before AEP to discuss plan changes"))

    # ── Surgeries & Medical History — every field ──
    for sname,sdate,fac,doc,notes in [
        ("Right total knee replacement","2019-03-14","Sunrise Hospital Las Vegas","Dr. Marcus Webb",
         "Full recovery; physical therapy completed June 2019; follow-up annually"),
        ("Cataract surgery — left eye","2022-08-09","Desert Eye Surgery Center","Dr. Patricia Cole",
         "No complications; right eye cleared; vision improved to 20/30"),
        ("Appendectomy","1978-06-02","St. Rose Dominican Hospital","Unknown",
         "Emergency procedure; full recovery; no ongoing issues"),
        ("Hysterectomy (partial)","2001-11-20","Valley Hospital Medical Center","Dr. Sandra Reyes",
         "Benign fibroid; full recovery; hormone therapy considered but declined"),
    ]:
        db.execute("""INSERT INTO surgeries
            (beneficiary_profile_id, surgery_name, approximate_date, facility, doctor, notes)
            VALUES (?,?,?,?,?,?)""",
            (pid,sname,sdate,fac,doc,notes))

    # ── Important Notes — every field ──
    for cat,note in [
        ("Medical","Preferred hospital: Valley Hospital Medical Center (620 Shadow Ln, Las Vegas NV 89106)"),
        ("Medical","DNR (Do Not Resuscitate) order on file with Dr. Ramirez and Valley Hospital — updated Jan 2026"),
        ("Medical","Healthcare Power of Attorney: daughter Sarah Johnson (702-555-0155)"),
        ("Legal","Will and Revocable Living Trust on file with Henderson Law Group — 702-555-0900; attorney: James Whitfield Esq."),
        ("Legal","Safe deposit box at Wells Fargo Summerlin branch (1980 Village Center Cir) — key in bedroom dresser top drawer"),
        ("Home","Spare house key with neighbor Mrs. Rosa Torres at 1236 Desert Sage Drive"),
        ("Home","Security system code: given verbally to David and Sarah only — do not write here"),
        ("Insurance","Medicare supplement gap reviewed Oct 2025 with Thabang; plan adequate through 2026"),
        ("Financial","Social Security deposited 3rd Wednesday each month to Wells Fargo checking account"),
    ]:
        db.execute("""INSERT INTO important_notes
            (beneficiary_profile_id, category, note_text_encrypted, created_by)
            VALUES (?,?,?,?)""",
            (pid, cat, encrypt_text(note), uid))

    # ── Financial Locators — every field ──
    for cat,inst,phone,web,last4,docloc,trusted,notes in [
        ("Bank","Wells Fargo — Checking & Savings","1-800-869-3557","www.wellsfargo.com",
         "7821","Home fireproof safe (master bedroom closet)","David Johnson (spouse)",
         "Checking for bills; savings for medical emergencies"),
        ("Investment / Retirement","Fidelity — IRA","1-800-343-3548","www.fidelity.com",
         "4892","Fireproof safe — Fidelity brokerage statement folder","Sarah Johnson (daughter)",
         "RMDs started 2015; quarterly statements mailed"),
        ("Life Insurance","New York Life — Whole Life Policy","1-800-695-4331","www.newyorklife.com",
         "","Fireproof safe — insurance folder","Sarah Johnson (daughter)",
         "Policy #NYL-4471882; death benefit $50,000; David Johnson primary beneficiary"),
        ("Legal","Henderson Law Group — Estate Attorney","702-555-0900","",
         "","Will and trust on file at attorney office","James Whitfield Esq.",
         "Trust amended Jan 2024; successor trustee: Sarah Johnson"),
        ("Government","Social Security Administration","1-800-772-1213","www.ssa.gov",
         "","Social Security card in fireproof safe","",
         "Medicare Part A & B enrollment via SSA"),
    ]:
        db.execute("""INSERT INTO financial_locators
            (beneficiary_profile_id, category, institution_name, contact_phone,
             website, last_four_only_encrypted, document_location, trusted_contact, notes_encrypted)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (pid,cat,inst,phone,web,
             encrypt_text(last4) if last4 else "",
             docloc,trusted,encrypt_text(notes)))

    return HTMLResponse("""
        <h2 style="font-family:Georgia,serif;color:#0B1E38;padding:2rem;">
        ✅ Mary Johnson profile fully seeded!<br><br>
        <span style="font-size:1rem;font-weight:normal;">
        • 6 medications (all fields)<br>
        • 4 providers (PCP, cardiologist, eye, dentist)<br>
        • 5 allergies (medication, food, environmental)<br>
        • 3 insurance policies (MA, Part D, Original Medicare)<br>
        • 1 Medicare advisor (Thabang Kesiilwe)<br>
        • 4 surgeries / medical history<br>
        • 3 emergency contacts<br>
        • 9 important notes<br>
        • 5 financial locators<br>
        • Medicare card (MBI, Part A & B dates)<br><br>
        <strong>Email:</strong> demo@northstar-demo.com<br>
        <strong>Password:</strong> NorthStarDemo2026!<br><br>
        <a href="/">Sign in →</a>
        </span></h2>""")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        db.init_db()
        print(f"Initialized database at {db.db_path()}")
    else:
        print("Run with: uvicorn app.main:app --reload")


# ---------------------------------------------------------------------------
# Keep-alive ping endpoint (called by Render cron or external scheduler)
# ---------------------------------------------------------------------------

@app.get("/ping")
async def ping():
    """Health check — keeps Render free tier warm."""
    return {"status": "ok", "service": "NorthStar Medicare Family File"}
