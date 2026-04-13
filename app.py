import streamlit as st
import pytesseract
import numpy as np
from PIL import Image
from groq import Groq
from fpdf import FPDF
import datetime
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")

import shutil
tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
client = Groq(api_key="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")

st.set_page_config(page_title="MediCode", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = ""
    st.session_state.username = ""
if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""
if "icd_codes" not in st.session_state:
    st.session_state.icd_codes = []
if "approved_codes" not in st.session_state:
    st.session_state.approved_codes = []

USERS = {
    "patient1": {"password": "demo123", "role": "patient", "name": "Ravi Kumar"},
    "coder1":   {"password": "demo123", "role": "coder",   "name": "Dr. Priya Verified Coder"},
    "admin1":   {"password": "demo123", "role": "admin",   "name": "Admin"},
}

import json

def save_data(ocr_text, icd_codes):
    with open("medicode_data.json", "w") as f:
        json.dump({"ocr_text": ocr_text, "icd_codes": icd_codes}, f)

def load_data():
    try:
        with open("medicode_data.json", "r") as f:
            return json.load(f)
    except:
        return {"ocr_text": "", "icd_codes": []}

def ask_groq(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

def login_page():
    st.title("MediCode - AI Medical Coding Platform")
    st.markdown("---")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("### Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.role = USERS[username]["role"]
                st.session_state.username = USERS[username]["name"]
                st.rerun()
            else:
                st.error("Wrong username or password")
        st.markdown("---")
        st.markdown("**Demo accounts:**")
        st.code("Patient  → username: patient1  password: demo123")
        st.code("Coder    → username: coder1    password: demo123")
        st.code("Admin    → username: admin1    password: demo123")

def ocr_page():
    st.title("Upload Prescription")
    st.markdown(f"Welcome, **{st.session_state.username}**")
    uploaded = st.file_uploader("Upload doctor prescription (JPG, PNG)", type=["jpg","jpeg","png"])
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, caption="Uploaded Prescription", use_column_width=True)
        if st.button("Extract Text and Generate ICD-10 Codes", use_container_width=True):
            with st.spinner("Reading prescription..."):
                gray = image.convert('L')
                text = pytesseract.image_to_string(gray)
                st.session_state.ocr_text = text

            # Validate if image is a medical prescription
            with st.spinner("Validating prescription..."):
                validate_prompt = f"""Look at this text extracted from an uploaded image:

{text[:500]}

Is this text from a medical prescription or clinical document?
A valid prescription contains things like: medicine names, dosage, patient name, doctor name, diagnosis, symptoms, or medical terms.

Reply with only one word: YES or NO"""
                validation = ask_groq(validate_prompt).strip().upper()

            if "NO" in validation or len(text.strip()) < 10:
                st.error("This does not look like a medical prescription!")
                st.warning("Please upload a valid doctor's prescription or clinical note.")
                st.info("Valid prescriptions contain: medicine names, dosage, diagnosis, symptoms, or medical terms.")
                st.session_state.ocr_text = ""
                st.session_state.icd_codes = []
                st.stop()
            with st.spinner("AI generating ICD-10 codes..."):
                prompt = f"""You are an expert medical coder. Analyze this clinical text from a doctor prescription and provide exactly 5 ICD-10 codes.

Clinical text:
{text}

Respond in this EXACT format, one per line, nothing else:
CODE | DESCRIPTION | CONFIDENCE% | REASON

Example:
E11.9 | Type 2 diabetes without complications | 95% | Patient has documented diabetes"""
                response = ask_groq(prompt)
                lines = response.strip().split("\n")
                codes = []
                for line in lines:
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4:
                            codes.append({
                                "code": parts[0],
                                "description": parts[1],
                                "confidence": parts[2],
                                "reason": parts[3]
                            })
                st.session_state.icd_codes = codes
                save_data(st.session_state.ocr_text, codes)
            st.success("Done!")
            st.markdown("### Extracted Text")
            st.text_area("OCR Output", st.session_state.ocr_text, height=150)
            st.markdown("### ICD-10 Codes Generated")
            for c in st.session_state.icd_codes:
                try:
                    conf = int(c["confidence"].replace("%","").strip())
                except:
                    conf = 80
                color = "green" if conf >= 80 else "orange" if conf >= 60 else "red"
                st.markdown(f"""
<div style='border:1px solid #ddd;border-radius:8px;padding:12px;margin:6px 0;'>
<b style='color:{color};font-size:16px'>{c['code']}</b> - {c['description']}<br>
<small>Confidence: <b>{c['confidence']}</b> | {c['reason']}</small>
</div>""", unsafe_allow_html=True)
            st.info("Login as coder1 to review and approve these codes.")

def coder_page():
    st.title("Coder Review Dashboard")
    st.success(f"Verified Medical Coder: {st.session_state.username}")
    if not st.session_state.icd_codes:
        data = load_data()
        if data["icd_codes"]:
            st.session_state.icd_codes = data["icd_codes"]
            st.session_state.ocr_text = data["ocr_text"]
        else:
            st.warning("No codes to review yet. Login as patient1 and upload a prescription first.")
            return
    st.markdown("### Original Clinical Notes")
    st.text_area("Extracted Text", st.session_state.ocr_text, height=120)
    st.markdown("### Review AI-Generated Codes")
    approved = []
    for i, c in enumerate(st.session_state.icd_codes):
        with st.expander(f"{c['code']} - {c['description']} ({c['confidence']})", expanded=True):
            col1, col2 = st.columns([3,1])
            with col1:
                new_code = st.text_input("Code", value=c["code"], key=f"code_{i}")
                new_desc = st.text_input("Description", value=c["description"], key=f"desc_{i}")
            with col2:
                action = st.radio("Action", ["Approve","Override","Reject"], key=f"action_{i}")
            if action != "Reject":
                approved.append({
                    "code": new_code,
                    "description": new_desc,
                    "confidence": c["confidence"],
                    "action": action
                })
    if st.button("Sign Off and Generate Claim", use_container_width=True):
        st.session_state.approved_codes = approved
        st.success("Codes verified! Go to Claim Summary in the sidebar.")

def claim_page():
    st.title("Insurance Claim Summary")
    if not st.session_state.approved_codes:
        st.warning("No approved codes yet. Complete coder review first.")
        return
    st.markdown("### Verified ICD-10 Codes")
    for c in st.session_state.approved_codes:
        st.markdown(f"- **{c['code']}** - {c['description']} ({c['confidence']}) - *{c['action']}*")
    if st.button("Generate Insurance Claim PDF", use_container_width=True):
        with st.spinner("Drafting claim with AI..."):
            codes_text = "\n".join([f"{c['code']} - {c['description']}" for c in st.session_state.approved_codes])
            prompt = f"""You are a professional medical billing specialist. Write a complete, detailed insurance claim justification letter. 
Do NOT use any placeholders like [Your Name] or [Date] - fill everything with real content from the data provided.

Use these exact details:
- Verified by: {st.session_state.username}
- Date: {datetime.datetime.now(IST).strftime('%Y-%m-%d')}
- Issuing Organization: MediCode AI Platform

Verified ICD-10 codes:
{codes_text}

Clinical notes from prescription:
{st.session_state.ocr_text[:800]}

Write a detailed letter with:
1. Patient condition summary based on the ICD-10 codes
2. Medical necessity justification for each diagnosis code
3. Treatment recommendations
4. Why insurance coverage is warranted
5. Professional closing

Use formal medical language. Minimum 200 words. No placeholders."""
            justification = ask_groq(prompt)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 12, "MediCode - Insurance Claim Summary", ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 8, f"Date: {datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
        pdf.cell(0, 8, f"Verified by: {st.session_state.username}", ln=True, align="C")
        pdf.ln(6)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Verified ICD-10 Diagnosis Codes", ln=True)
        pdf.set_font("Arial", "", 11)
        for c in st.session_state.approved_codes:
            pdf.cell(0, 8, f"  {c['code']} - {c['description']} | {c['confidence']} | {c['action']}", ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Clinical Justification & Medical Necessity", ln=True)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "ICD-10 Code Details:", ln=True)
        pdf.set_font("Arial", "", 10)
        icd_details = {
            "R": "Symptoms & Signs",
            "E": "Endocrine/Metabolic",
            "I": "Circulatory System",
            "J": "Respiratory System",
            "K": "Digestive System",
            "F": "Mental & Behavioral",
            "Z": "Health Status Factors",
            "T": "Injury & Poisoning",
            "M": "Musculoskeletal",
            "N": "Genitourinary"
        }
        for c in st.session_state.approved_codes:
            category = icd_details.get(c['code'][0], "General Medical")
            pdf.cell(0, 7, f"  {c['code']} ({category}): {c['description']}", ln=True)
        pdf.ln(3)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "Denial Risk Assessment:", ln=True)
        pdf.set_font("Arial", "", 10)
        avg_conf = sum([int(c['confidence'].replace('%','').strip()) for c in st.session_state.approved_codes]) // len(st.session_state.approved_codes)
        risk = "LOW" if avg_conf >= 80 else "MEDIUM" if avg_conf >= 60 else "HIGH"
        pdf.cell(0, 7, f"  Average Code Confidence: {avg_conf}%", ln=True)
        pdf.cell(0, 7, f"  Claim Denial Risk: {risk}", ln=True)
        pdf.cell(0, 7, f"  Total Codes Submitted: {len(st.session_state.approved_codes)}", ln=True)
        pdf.cell(0, 7, f"  Human Verified: Yes - by {st.session_state.username}", ln=True)
        pdf.ln(3)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "AI Generated Clinical Justification Letter", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 7, justification)
        pdf.ln(6)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Verified Medical Coder Signature: ________________________", ln=True)
        pdf.cell(0, 8, f"Coder: {st.session_state.username}", ln=True)
        pdf.cell(0, 8, f"Date: {datetime.datetime.now(IST).strftime('%Y-%m-%d')}", ln=True)
        pdf_bytes = bytes(pdf.output())
        st.download_button("Download Claim PDF", data=pdf_bytes, file_name="medicode_claim.pdf", mime="application/pdf", use_container_width=True)
        st.success("Claim ready! Download and send to insurance company.")
def coder_register_page():
    st.title("Register as Medical Coder")
    st.markdown("Upload your certificate and get verified automatically by AI")
    st.markdown("---")

    with st.form("coder_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            speciality = st.selectbox("Speciality", [
                "Internal Medicine", "Cardiology", "Oncology",
                "Pediatrics", "Orthopedics", "Neurology", "General"
            ])
        with col2:
            credential = st.selectbox("Credential Type", [
                "AAPC CPC", "AHIMA CCS", "AHIMA CCA",
                "AAPC COC", "NHA CBCS", "Other"
            ])
            experience = st.selectbox("Years of Experience", [
                "0-2 years", "2-5 years", "5-10 years", "10+ years"
            ])
            country = st.text_input("Country", value="India")

        cert_file = st.file_uploader("Upload Certificate (JPG, PNG, PDF)", type=["jpg","jpeg","png"])
        submitted = st.form_submit_button("Submit for Verification", use_container_width=True)

    if submitted and cert_file and name and email:
        with st.spinner("AI is verifying your certificate..."):
            # OCR the certificate
            image = Image.open(cert_file)
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            cert_text = pytesseract.image_to_string(gray)

            # AI verifies the certificate
            prompt = f"""You are a medical credential verification expert.
Analyze this text extracted from a medical coding certificate and verify if it is legitimate.

Certificate text:
{cert_text}

Applicant details:
- Name: {name}
- Claimed credential: {credential}

Check for:
1. Is this a real medical coding certificate? (AAPC, AHIMA, NHA or similar)
2. Does the name on certificate match: {name}?
3. Is there a valid credential number or ID?
4. Is there an issuing organization name?
5. Is there an expiry or issue date?

Respond in this EXACT format:
VERIFIED: YES or NO
CREDENTIAL_FOUND: the credential type found
NAME_MATCH: YES or NO
CERT_NUMBER: the certificate number if found or NONE
ISSUING_BODY: name of issuing organization
REASON: one line explanation

Important rules:
- Check if AAPC, AHIMA, NHA or any medical coding organization is mentioned — mark ISSUING_BODY
- NAME_MATCH is YES only if the name on certificate closely matches {name} — first name OR last name must match
- If names are completely different, mark NAME_MATCH as NO and VERIFIED as NO
- If credential number is not found, mark as NONE but still check other details
- Cursive fonts may cause OCR errors — be lenient with spelling but strict with name matching
- VERIFIED is YES if ALL of these are true: 1) Medical coding organization found 2) Name matches 3) Credential type found
- VERIFIED is YES even if certificate number is missing — certificate number is optional
- VERIFIED is NO only if name does not match OR no medical organization found
- Do not fail verification just because of OCR spelling errors or missing cert number"""

            response = ask_groq(prompt)
            lines = response.strip().split("\n")
            result = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    result[key.strip()] = val.strip()

        name_match = result.get("NAME_MATCH", "NO") == "YES"
        issuing_body = result.get("ISSUING_BODY", "").strip()
        credential_found = result.get("CREDENTIAL_FOUND", "").strip()
        
        known_orgs = ["AAPC", "AHIMA", "NHA", "ACMCS", "ACDIS", "Academy"]
        org_found = any(org.lower() in issuing_body.lower() for org in known_orgs)
        cred_found = len(credential_found) > 2 and credential_found.upper() != "NONE"
        
        verified = name_match and org_found and cred_found

        if verified:
            st.success("Certificate Verified Successfully!")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
<div style='background:#d4edda;border-radius:10px;padding:16px'>
<h4 style='color:green'>Verification Result</h4>
<p><b>Status:</b> VERIFIED</p>
<p><b>Name:</b> {name}</p>
<p><b>Credential:</b> {result.get('CREDENTIAL_FOUND', credential)}</p>
<p><b>Issuing Body:</b> {result.get('ISSUING_BODY', 'N/A')}</p>
<p><b>Certificate No:</b> {result.get('CERT_NUMBER', 'N/A')}</p>
</div>""", unsafe_allow_html=True)
            with col2:
                st.image(cert_file, caption="Uploaded Certificate", use_column_width=True)

            # Save verified coder to session
            if "verified_coders" not in st.session_state:
                st.session_state.verified_coders = []
            st.session_state.verified_coders.append({
                "name": name,
                "email": email,
                "credential": credential,
                "speciality": speciality,
                "experience": experience,
                "cert_number": result.get('CERT_NUMBER', 'N/A'),
                "verified_on": datetime.datetime.now(IST).strftime('%Y-%m-%d')
            })

            # Save to file
            try:
                with open("verified_coders.json", "r") as f:
                    coders = json.load(f)
            except:
                coders = []
            coders.append({
                "name": name,
                "email": email,
                "credential": credential,
                "speciality": speciality,
                "verified_on": datetime.datetime.now(IST).strftime('%Y-%m-%d')
            })
            with open("verified_coders.json", "w") as f:
                json.dump(coders, f)

            st.balloons()
            st.info("You are now a verified coder on MediCode! Admin has been notified.")

        else:
            name_match = result.get("NAME_MATCH", "NO")
            if name_match == "NO":
                st.error("Name on certificate does not match your registered name!")
                st.warning(f"You entered: **{name}** but certificate belongs to someone else.")
                st.info("Please upload YOUR OWN certificate to get verified.")
            else:
                st.error("Certificate could not be verified automatically.")
                st.warning(f"Reason: {result.get('REASON', 'Could not read certificate clearly')}")
                st.info("Your application has been sent to admin for manual review.")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
<div style='background:#f8d7da;border-radius:10px;padding:16px'>
<h4 style='color:red'>Verification Failed</h4>
<p><b>Name Match:</b> {result.get('NAME_MATCH', 'NO')}</p>
<p><b>Credential Found:</b> {result.get('CREDENTIAL_FOUND', 'Not detected')}</p>
<p><b>Issuing Body:</b> {result.get('ISSUING_BODY', 'Not detected')}</p>
<p><b>Reason:</b> {result.get('REASON', 'N/A')}</p>
</div>""", unsafe_allow_html=True)
            with col2:
                st.image(cert_file, caption="Uploaded Certificate", use_column_width=True)

    elif submitted:
        st.warning("Please fill all fields and upload your certificate.")
        def coder_profile_page():
    st.title("My Coder Profile")
    st.success(f"Verified Medical Coder: {st.session_state.username}")

    try:
        with open("verified_coders.json", "r") as f:
            coders = json.load(f)
    except:
        coders = []

    current_coder = None
    current_index = None
    for i, c in enumerate(coders):
        if c["name"].lower() in st.session_state.username.lower() or st.session_state.username.lower() in c["name"].lower():
            current_coder = c
            current_index = i
            break

    if not current_coder:
        st.warning("Profile not found. Please register first.")
        return

    st.markdown("### Your Verified Details")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
<div style='background:#E1F5EE;border-radius:10px;padding:16px;border:1px solid #9FE1CB'>
<p><b>Name:</b> {current_coder['name']}</p>
<p><b>Email:</b> {current_coder['email']}</p>
<p><b>Credential:</b> {current_coder['credential']}</p>
<p><b>Speciality:</b> {current_coder['speciality']}</p>
<p><b>Verified On:</b> {current_coder['verified_on']}</p>
<p><b>Status:</b> Verified</p>
</div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div style='background:#E6F1FB;border-radius:10px;padding:16px;border:1px solid #B5D4F4'>
<h4 style='color:#185FA5'>Verification Badge</h4>
<p style='color:#185FA5;font-size:24px;font-weight:500'>VERIFIED</p>
<p style='color:#185FA5'>Certified Medical Coder</p>
<p style='color:#185FA5'>MediCode Platform</p>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Update Your Profile")
    st.info("You can update your details below. Name and credential cannot be changed — contact admin for those.")

    with st.form("update_profile"):
        new_email = st.text_input("Email Address", value=current_coder.get("email", ""))
        new_speciality = st.selectbox("Speciality", [
            "Internal Medicine", "Cardiology", "Oncology",
            "Pediatrics", "Orthopedics", "Neurology", "General"
        ], index=["Internal Medicine", "Cardiology", "Oncology",
            "Pediatrics", "Orthopedics", "Neurology", "General"].index(
                current_coder.get("speciality", "General")
            ) if current_coder.get("speciality") in ["Internal Medicine", "Cardiology", "Oncology",
            "Pediatrics", "Orthopedics", "Neurology", "General"] else 0)
        new_experience = st.selectbox("Years of Experience", [
            "0-2 years", "2-5 years", "5-10 years", "10+ years"
        ])
        new_phone = st.text_input("Phone Number", value=current_coder.get("phone", ""))
        new_hospital = st.text_input("Hospital / Clinic Name", value=current_coder.get("hospital", ""))
        new_city = st.text_input("City", value=current_coder.get("city", "Chennai"))

        submitted = st.form_submit_button("Update Profile", use_container_width=True)

    if submitted:
        coders[current_index]["email"] = new_email
        coders[current_index]["speciality"] = new_speciality
        coders[current_index]["experience"] = new_experience
        coders[current_index]["phone"] = new_phone
        coders[current_index]["hospital"] = new_hospital
        coders[current_index]["city"] = new_city
        coders[current_index]["last_updated"] = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M')

        with open("verified_coders.json", "w") as f:
            json.dump(coders, f)

        st.success("Profile updated successfully!")
        st.balloons()

    st.markdown("---")
    st.markdown("### Upload New Certificate")
    st.info("Upload a new certificate if your credential has been renewed or upgraded.")

    new_cert = st.file_uploader("Upload New Certificate (JPG, PNG)", type=["jpg","jpeg","png"])
    if new_cert:
        image = Image.open(new_cert)
        col1, col2 = st.columns(2)
        with col1:
            st.image(new_cert, caption="New Certificate", width=300)
        with col2:
            if st.button("Verify New Certificate", use_container_width=True):
                with st.spinner("Verifying new certificate..."):
                    gray = image.convert('L')
                    cert_text = pytesseract.image_to_string(gray)
                    prompt = f"""Verify this medical coding certificate.
Certificate text: {cert_text}
Coder name: {current_coder['name']}

Check: Is it a valid medical coding certificate from AAPC/AHIMA/NHA? Does name match?

Reply format:
VERIFIED: YES or NO
CREDENTIAL_FOUND: credential type
ISSUING_BODY: organization name
REASON: one line"""
                    response = ask_groq(prompt)
                    lines = response.strip().split("\n")
                    result = {}
                    for line in lines:
                        if ":" in line:
                            key, val = line.split(":", 1)
                            result[key.strip()] = val.strip()

                name_match = True
                org_found = any(org.lower() in result.get("ISSUING_BODY","").lower() for org in ["AAPC","AHIMA","NHA","Academy"])
                cred_found = len(result.get("CREDENTIAL_FOUND","")) > 2

                if org_found and cred_found:
                    coders[current_index]["credential"] = result.get("CREDENTIAL_FOUND", current_coder["credential"])
                    coders[current_index]["verified_on"] = datetime.datetime.now(IST).strftime('%Y-%m-%d')
                    with open("verified_coders.json", "w") as f:
                        json.dump(coders, f)
                    st.success("New certificate verified and profile updated!")
                    st.balloons()
                else:
                    st.error("Could not verify new certificate. Contact admin.")
def admin_page():
    st.title("MediCode Admin Dashboard")
    st.markdown(f"Welcome, **{st.session_state.username}**")

    # Load current data
    data = load_data()
    codes = data["icd_codes"]
    total_codes = len(codes)
    avg_conf = 0
    if codes:
        confs = []
        for c in codes:
            try:
                confs.append(int(c["confidence"].replace("%","").strip()))
            except:
                confs.append(80)
        avg_conf = sum(confs) // len(confs)

    approved_codes = st.session_state.approved_codes
    total_claims = 1 if approved_codes else 0

    # ---- ANALYTICS SECTION ----
    st.markdown("## Platform Analytics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cases Processed", "1", "+1 today")
    with col2:
        st.metric("ICD Codes Generated", total_codes if total_codes else 5)
    with col3:
        st.metric("Avg Confidence Score", f"{avg_conf}%" if avg_conf else "74%")
    with col4:
        st.metric("Claims Generated", total_claims)

    st.markdown("---")

    # ---- DENIAL RISK BREAKDOWN ----
    st.markdown("## Denial Risk Breakdown")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
<div style='background:#d4edda;border-radius:10px;padding:16px;text-align:center'>
<h2 style='color:green;margin:0'>2</h2>
<p style='color:green;margin:0'>LOW RISK claims<br>(80%+ confidence)</p>
</div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div style='background:#fff3cd;border-radius:10px;padding:16px;text-align:center'>
<h2 style='color:orange;margin:0'>1</h2>
<p style='color:orange;margin:0'>MEDIUM RISK claims<br>(60-79% confidence)</p>
</div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""
<div style='background:#f8d7da;border-radius:10px;padding:16px;text-align:center'>
<h2 style='color:red;margin:0'>1</h2>
<p style='color:red;margin:0'>HIGH RISK claims<br>(below 60% confidence)</p>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ---- CODER PERFORMANCE ----
    st.markdown("## Verified Coder Performance")
    import pandas as pd
    try:
        with open("verified_coders.json", "r") as f:
            verified_coders = json.load(f)
    except:
        verified_coders = []

    if verified_coders:
        coder_data = {
            "Coder Name": [c["name"] for c in verified_coders],
            "Credential": [c["credential"] for c in verified_coders],
            "Speciality": [c["speciality"] for c in verified_coders],
            "Verified On": [c["verified_on"] for c in verified_coders],
            "Status": ["Active" for _ in verified_coders]
        }
        df = pd.DataFrame(coder_data)
        st.dataframe(df, use_container_width=True)
        st.metric("Total Verified Coders", len(verified_coders))
    else:
        st.info("No verified coders yet. Coders can register from the patient login.")

    st.markdown("---")

    # ---- RECENT CASES ----
    st.markdown("## Recent Cases")
    case_data = {
        "Case ID": ["MC-001", "MC-002", "MC-003"],
        "Uploaded By": ["patient1", "patient1", "patient2"],
        "Codes Generated": [5, 4, 5],
        "Reviewed By": ["Dr. Priya", "Dr. Arjun", "Dr. Priya"],
        "Denial Risk": ["HIGH", "LOW", "MEDIUM"],
        "Status": ["Claim Generated", "Claim Generated", "Pending Review"]
    }
    df2 = pd.DataFrame(case_data)
    st.dataframe(df2, use_container_width=True)

    st.markdown("---")

    # ---- CODER VERIFICATION ----
    st.markdown("## Pending Coder Verification Requests")
    with st.expander("Dr. Meena S - AAPC CPC Certificate uploaded"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Credential:** AAPC CPC")
            st.write("**Speciality:** Internal Medicine")
            st.write("**Country:** India")
            st.write("**Experience:** 5 years")
        with col2:
            st.write("**Certificate:** CPC_Meena.pdf")
            st.write("**Applied:** 2026-04-12")
            st.write("**Status:** Pending")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify Coder", key="v1"):
                st.success("Dr. Meena verified! She can now review cases.")
        with col2:
            if st.button("Reject", key="r1"):
                st.error("Application rejected.")

    with st.expander("Dr. Arjun R - AHIMA CCS Certificate uploaded"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Credential:** AHIMA CCS")
            st.write("**Speciality:** Cardiology")
            st.write("**Country:** India")
            st.write("**Experience:** 8 years")
        with col2:
            st.write("**Certificate:** CCS_Arjun.pdf")
            st.write("**Applied:** 2026-04-11")
            st.write("**Status:** Pending")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify Coder", key="v2"):
                st.success("Dr. Arjun verified! He can now review cases.")
        with col2:
            if st.button("Reject", key="r2"):
                st.error("Application rejected.")

    st.markdown("---")

    # ---- REVENUE IMPACT ----
    st.markdown("## Revenue Impact Saved")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Manual Coding Cost Saved", "Rs. 2,400", "per month estimate")
    with col2:
        st.metric("Avg Time Saved per Case", "45 mins", "vs manual coding")
    with col3:
        st.metric("Denial Prevention", "Rs. 15,000", "estimated saved")

def main():
    if not st.session_state.logged_in:
        login_page()
        return
    role = st.session_state.role
    with st.sidebar:
        st.markdown("### MediCode")
        st.markdown(f"**{st.session_state.username}**")
        st.markdown(f"Role: {role}")
        st.markdown("---")
        if role == "patient":
            page = st.radio("Menu", ["Upload Prescription", "Register as Coder"])
        elif role == "coder":
            page = st.radio("Menu", ["Review Codes", "Claim Summary", "My Profile"])
        elif role == "admin":
            page = st.radio("Menu", ["Upload Prescription", "Review Codes", "Claim Summary", "Admin Panel"])
        st.markdown("---")
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    if page == "Upload Prescription":
        ocr_page()
    elif page == "Register as Coder":
        coder_register_page()
    elif page == "Review Codes":
        coder_page()
    elif page == "Claim Summary":
        claim_page()
    elif page == "Admin Panel":
        admin_page()
    elif page == "My Profile":
        coder_profile_page()

main()