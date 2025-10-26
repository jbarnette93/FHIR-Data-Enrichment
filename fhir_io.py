from __future__ import annotations
import requests
import pandas as pd
from typing import Optional
from utils import parse_time, safe_float

BASE_URL = 'https://synthea-proxy-389841612478.us-central1.run.app/'


# ----------------------------
#  FHIR Fetch Helpers
# ----------------------------
def _get(url: str) -> list[dict]:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_observations_for_subject(subject: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    url = f"{BASE_URL}Observation?subject={subject}"
    if start_date:
        url += f"&date=ge{start_date}"
    if end_date:
        url += f"&date=le{end_date}"
    return _get(url)


def fetch_medication_administrations_for_subject(subject: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    url = f"{BASE_URL}MedicationAdministration?subject={subject}"
    if start_date:
        url += f"&effective-time=ge{start_date}"
    if end_date:
        url += f"&effective-time=le{end_date}"
    return _get(url)


# ----------------------------
#  Observation Parsing
# ----------------------------
# Mapping of known LOINC codes
LOINC_MAP = {
    '2703-7': ('PaO2', 'mmHg'),         # Arterial O2 partial pressure
    '3150-0': ('FiO2', ''),             # Inhaled O2 concentration
    '59408-5': ('SpO2', '%'),           # O2 saturation (pulse oximetry)
    '2708-6': ('SpO2', '%'),
    '8478-0': ('MAP', 'mmHg'),
    '777-3': ('Platelets', '10^3/uL'),
    '1975-2': ('Bilirubin', 'mg/dL'),
    '2160-0': ('Creatinine', 'mg/dL'),
    '9269-2': ('GCS', ''),
}

# Display keyword fallback (for robustness)
DISPLAY_KEYWORDS = {
    'PaO2': ['pao2', 'partial pressure oxygen', 'arterial oxygen'],
    'FiO2': ['fio2', 'inspired oxygen', 'fraction of inspired oxygen', 'inhaled oxygen'],
    'SpO2': ['spo2', 'oxygen saturation', 'pulse oximetry'],
    'MAP': ['map', 'mean arterial pressure'],
    'Platelets': ['platelet'],
    'Bilirubin': ['bilirubin'],
    'Creatinine': ['creatinine'],
    'GCS': ['glasgow coma', 'gcs total', 'gcs score'],
}


def _obs_entry_to_row(o: dict) -> Optional[dict]:
    """Extract key metrics from an Observation resource."""
    code = None
    display = None
    codings = (o.get('code') or {}).get('coding') or []
    if codings:
        code = codings[0].get('code')
        display = codings[0].get('display') or o.get('code', {}).get('text')

    metric = None
    if code and code in LOINC_MAP:
        metric = LOINC_MAP[code][0]
    else:
        # Fallback match by text keyword
        text = ((display or '') + ' ' + (o.get('code', {}).get('text') or '')).lower()
        for m, kws in DISPLAY_KEYWORDS.items():
            if any(k in text for k in kws):
                metric = m
                break

    if not metric:
        return None

    vq = o.get('valueQuantity') or {}
    val = safe_float(vq.get('value'))
    unit = vq.get('unit') or vq.get('code')
    t = o.get('effectiveDateTime') or o.get('issued')
    if val is None or not t:
        return None

    return {
        'metric': metric,
        'value': val,
        'unit': unit,
        'effective': parse_time(t),
    }


def observations_to_df(observations: list[dict], subject: str) -> pd.DataFrame:
    """Flatten Observations into a tidy DataFrame."""
    rows = []
    for o in observations:
        r = _obs_entry_to_row(o)
        if r:
            r['patient_id'] = subject
            rows.append(r)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df.sort_values(['patient_id', 'effective'], inplace=True)

    # --- Derive MAP from Systolic/Diastolic if not provided ---
    if set(df['metric'].unique()).intersection({'8480-6', '8462-4'}):
        # 8480-6 = Systolic BP, 8462-4 = Diastolic BP
        sys_df = df[df['metric'] == '8480-6'][['effective', 'value']].rename(columns={'value': 'sys'})
        dia_df = df[df['metric'] == '8462-4'][['effective', 'value']].rename(columns={'value': 'dia'})
        merged = pd.merge_asof(
            sys_df.sort_values('effective'),
            dia_df.sort_values('effective'),
            on='effective',
            direction='nearest',
            tolerance=pd.Timedelta(minutes=5)
        )
        if not merged.empty:
            merged['value'] = (merged['sys'] + 2 * merged['dia']) / 3
            merged['metric'] = 'MAP'
            merged['unit'] = 'mmHg'
            merged['patient_id'] = subject
            df = pd.concat(
                [df, merged[['patient_id', 'metric', 'value', 'unit', 'effective']]],
                ignore_index=True
            )

    return df


# ----------------------------
#  Medication Parsing
# ----------------------------
PRESSOR_KEYWORDS = {
    'norepinephrine': ['norepinephrine', 'levophed'],
    'epinephrine': ['epinephrine', 'adrenaline'],
    'dopamine': ['dopamine'],
    'dobutamine': ['dobutamine'],
}


def med_to_pressor(m: dict):
    """Extract pressor name and dose rate if present."""
    coding = ((m.get('medicationCodeableConcept') or {}).get('coding') or [{}])[0]
    text = (coding.get('display') or coding.get('code') or '').lower()
    which = None
    for k, kws in PRESSOR_KEYWORDS.items():
        if any(kw in text for kw in kws):
            which = k
            break
    if not which:
        return None

    dosage = m.get('dosage') or {}
    rate = None
    unit = None
    for key in ['doseRateQuantity', 'rateQuantity', 'rate']:
        q = dosage.get(key) or {}
        if isinstance(q, dict) and 'value' in q:
            rate = q.get('value')
            unit = q.get('unit') or q.get('code')
            break

    t = m.get('effectiveDateTime')
    if not t:
        return None

    return {
        'pressor': which,
        'rate': rate,
        'unit': unit,
        'effective': parse_time(t),
    }


def medications_to_df(meds: list[dict], subject: str) -> pd.DataFrame:
    """Flatten MedicationAdministration records into tidy DataFrame."""
    rows = []
    for m in meds:
        pr = med_to_pressor(m)
        if pr:
            pr['patient_id'] = subject
            rows.append(pr)

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(['patient_id', 'effective'], inplace=True)
    return df
