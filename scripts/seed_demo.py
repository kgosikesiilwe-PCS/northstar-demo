"""
Seed the demo database with a realistic Medicare profile.
Run: python scripts/seed_demo.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import db, security, crypto

db.init_db()

email = "demo@northstar-demo.com"
if db.query_one("SELECT id FROM users WHERE email = ?", (email,)):
    print("Demo user already exists — skipping.")
    sys.exit(0)

db.execute("INSERT INTO users (email, full_name, password_hash, role, status) VALUES (?,?,?,?,?)",
    (email, "Mary Johnson", security.hash_password("NorthStarDemo2026!"), "user", "active"))
uid = db.query_one("SELECT id FROM users WHERE email = ?", (email,))["id"]

db.execute("""INSERT INTO beneficiary_profiles
    (owner_user_id, full_name, preferred_name, date_of_birth,
     address_line_1, city, state, zip, phone, email, preferred_language, last_reviewed_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
    (uid,"Mary Johnson","Mary","1945-03-15","1234 Desert Sage Drive",
     "Las Vegas","NV","89117","702-555-0100","mary.johnson@example.com","English","2026-07-01"))
pid = db.query_one("SELECT id FROM beneficiary_profiles WHERE owner_user_id = ?", (uid,))["id"]

# Emergency contacts
for name,rel,phone,em,pri in [
    ("David Johnson","Spouse","702-555-0101","david.johnson@example.com",1),
    ("Sarah Johnson","Daughter","702-555-0155","sarah.johnson@example.com",2)]:
    db.execute("INSERT INTO emergency_contacts (beneficiary_profile_id,name,relationship,phone,email,priority_order) VALUES (?,?,?,?,?,?)",(pid,name,rel,phone,em,pri))

# Medications
for mn,dose,freq,ph,phph,doc,rsn,st in [
    ("Metformin","500 mg","Twice daily","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Blood sugar management","2018-01-15"),
    ("Lisinopril","10 mg","Once daily","CVS Pharmacy","702-555-0199","Dr. Elena Ramirez","Blood pressure","2018-03-01"),
    ("Atorvastatin","20 mg","Once daily at bedtime","Walgreens","702-555-0210","Dr. Kevin Park","Cholesterol management","2020-07-15"),
    ("Aspirin","81 mg","Once daily","","","Dr. Elena Ramirez","Heart health","2018-01-15")]:
    db.execute("INSERT INTO medications (beneficiary_profile_id,medication_name,dosage,frequency,pharmacy_name,pharmacy_phone,prescribing_doctor,reason,start_date) VALUES (?,?,?,?,?,?,?,?,?)",(pid,mn,dose,freq,ph,phph,doc,rsn,st))

# Providers
for pn,pt,sp,pr,ph,fx,net,pcp,lv,na in [
    ("Dr. Elena Ramirez","Primary care doctor / PCP","Family Medicine","Desert Springs Medical Group","702-555-0140","","Humana Gold Plus PPO",1,"2026-05-12","2026-08-15"),
    ("Dr. Kevin Park","Specialist","Cardiology","Nevada Heart Associates","702-555-0188","702-555-0189","",0,"",""),
    ("Desert Eye Associates","Eye Doctor","Ophthalmology","Desert Eye Associates","702-555-0210","","",0,"","")]:
    db.execute("INSERT INTO providers (beneficiary_profile_id,name,provider_type,specialty,practice_name,phone,fax,doctor_network,is_pcp,last_visit_date,next_appointment_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(pid,pn,pt,sp,pr,ph,fx,net,pcp,lv,na))

# Allergies
for an,at,rx,sv in [("Penicillin","Medication","Rash, hives, difficulty breathing","Severe"),("Shellfish","Food","Anaphylaxis","Severe")]:
    db.execute("INSERT INTO allergies (beneficiary_profile_id,allergy_name,allergy_type,reaction,severity) VALUES (?,?,?,?,?)",(pid,an,at,rx,sv))

# Insurance
db.execute("INSERT INTO insurance_policies (beneficiary_profile_id,policy_type,insurance_company,plan_name,member_id,plan_number,effective_date,rx_bin) VALUES (?,?,?,?,?,?,?,?)",
    (pid,"Medicare Advantage","Humana","Gold Plus H5619",crypto.encrypt_text("H5619-4821"),"H5619-003","2026-01-01","610014"))
db.execute("INSERT INTO insurance_policies (beneficiary_profile_id,policy_type,insurance_company,plan_name,member_id,effective_date) VALUES (?,?,?,?,?,?)",
    (pid,"Part D Prescription Drug Plan","SilverScript","SilverScript Choice",crypto.encrypt_text("SS-9234"),"2026-01-01"))

# Medicare advisor
db.execute("INSERT INTO medicare_advisors (beneficiary_profile_id,advisor_name,agency_name,phone,email,npn,insurance_company,plan_name,last_helped_date) VALUES (?,?,?,?,?,?,?,?,?)",
    (pid,"Thabang Kesiilwe","Kesiilwe Insurance","702-555-0177","kgosi.kesiilwe@gmail.com","12345678","Humana","Gold Plus H5619","2025-10-15"))

# Surgeries
db.execute("INSERT INTO surgeries (beneficiary_profile_id,surgery_name,surgery_date,facility_name,surgeon_name,notes) VALUES (?,?,?,?,?,?)",
    (pid,"Right knee replacement","2019-03-14","Sunrise Hospital","Dr. Marcus Webb","Full recovery. Follow-up annually."))

# Important notes
for cat,note in [
    ("Medical","Preferred hospital: Valley Hospital Medical Center, Las Vegas"),
    ("Home","Spare key with neighbor Mrs. Torres at 1236 Desert Sage Drive"),
    ("Legal","Will and trust on file with Henderson Law Group — 702-555-0900")]:
    db.execute("INSERT INTO important_notes (beneficiary_profile_id,category,note_text) VALUES (?,?,?)",(pid,cat,note))

# Financial locator
for inst,itype,phone,last4,loc in [
    ("Wells Fargo","Bank","1-800-869-3557","7821","Home fireproof safe, bedroom closet"),
    ("Henderson Law Group","Attorney","702-555-0900","","1 Main Street, Henderson, NV"),
    ("New York Life","Life Insurance","1-800-695-4331","4892","Home fireproof safe")]:
    db.execute("INSERT INTO financial_locators (beneficiary_profile_id,institution_name,account_type,phone,last_four_digits,document_location_text) VALUES (?,?,?,?,?,?)",(pid,inst,itype,phone,last4,loc))

print("""
✅ Demo seeded!
   Email:    demo@northstar-demo.com
   Password: NorthStarDemo2026!
   Profile:  Mary Johnson — Las Vegas, NV
""")
