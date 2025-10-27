# SOFA Scoring from FHIR (Observations + MedicationAdministrations)

This repository computes **Sequential Organ Failure Assessment (SOFA)** scores for nine synthetic patients (`a`–`i`) using the FHIR API.

It implements:
- FHIR ➜ tidy `pandas` DataFrames  
- 6-hour measurement validity window (per spec)  
- All six SOFA organ systems (Respiratory, Coagulation, Liver, Cardiovascular, CNS, Renal)  
- PaO₂/FiO₂ **or** SpO₂/FiO₂ with FiO₂ default = 0.21 when missing  
- Derived Mean Arterial Pressure (MAP) from Systolic/Diastolic blood pressure  
- Output file `submission.csv` → `patient_id, sofa_score_datetime, sofa_score`

---

## Key Findings

The provided dataset contains:
- **Vitals** (SpO₂, FiO₂, PaO₂, etc.) recorded frequently  
- **Laboratory results** (platelets, bilirubin, creatinine) roughly once per day  
- **Blood pressure values** available only as systolic/diastolic, from which MAP is derived  
- **No explicit GCS observations** (we assume GCS = 15 when absent)  

Because of this mismatch in measurement frequency, **no single timestamp includes all six organ system metrics within 6 hours**,  
so `submission.csv` is empty when enforcing the 6-hour rule exactly as specified.  
This behavior is correct under the official scoring specification.

---

## How to Run

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
