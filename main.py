from __future__ import annotations
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import pandas as pd
from fhir_io import (
    fetch_observations_for_subject,
    fetch_medication_administrations_for_subject,
    observations_to_df,
    medications_to_df,
)
from scoring import (
    score_resp,
    score_coag,
    score_liver,
    score_cardio,
    score_cns,
    score_renal,
)
from utils import round_times_to_observation_ticks, latest_within, norm_fio2

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
SUBJECTS = list("abcdefghi")
STRICT = True  # True = 6h per spec; False = relaxed 24h for demo
WINDOW_HOURS = 6 if STRICT else 24
DEFAULT_FIO2 = 0.21


# ---------------------------------------------------------------------
# Core Computation
# ---------------------------------------------------------------------
def compute_patient_sofa(subject: str) -> pd.DataFrame:
    print(f"→ Computing SOFA for patient '{subject}' ...")

    obs = fetch_observations_for_subject(subject)
    meds = fetch_medication_administrations_for_subject(subject)
    obs_df = observations_to_df(obs, subject)
    meds_df = medications_to_df(meds, subject)

    print(f"   Observations: {len(obs_df)} | Meds: {len(meds_df)}")

    if obs_df.empty:
        print("   ⚠️  No observations found. Skipping.")
        return pd.DataFrame(columns=["patient_id", "sofa_score_datetime", "sofa_score"])

    # Organize data by metric for fast lookup
    metrics = {}
    for m in [
        "PaO2",
        "SpO2",
        "FiO2",
        "MAP",
        "Platelets",
        "Bilirubin",
        "Creatinine",
        "GCS",
    ]:
        sub = obs_df[obs_df["metric"] == m][["effective", "value", "unit"]]
        metrics[m] = list(zip(sub["effective"], sub["value"]))

    # Build pressor dictionary (if applicable)
    pressor_times = {}
    if not meds_df.empty:
        for _, r in meds_df.iterrows():
            rate = r["rate"]
            unit = (r["unit"] or "").lower() if pd.notna(r["unit"]) else ""
            if pd.notna(rate) and ("ug/kg/min" in unit or "mcg/kg/min" in unit):
                val = float(rate)
                pressor_times.setdefault(r["effective"], {})[r["pressor"]] = val

    times = round_times_to_observation_ticks(obs_df["effective"].tolist())

    rows = []
    for t in times:
        pao2 = latest_within(metrics.get("PaO2", []), t, WINDOW_HOURS)
        spo2 = latest_within(metrics.get("SpO2", []), t, WINDOW_HOURS)
        fio2_raw = latest_within(metrics.get("FiO2", []), t, WINDOW_HOURS)
        fio2 = norm_fio2(fio2_raw, "%") if fio2_raw is not None else DEFAULT_FIO2

        map_v = latest_within(metrics.get("MAP", []), t, WINDOW_HOURS)
        plate = latest_within(metrics.get("Platelets", []), t, WINDOW_HOURS)
        bili = latest_within(metrics.get("Bilirubin", []), t, WINDOW_HOURS)
        creat = latest_within(metrics.get("Creatinine", []), t, WINDOW_HOURS)
        gcs = latest_within(metrics.get("GCS", []), t, WINDOW_HOURS)
        if gcs is None:
            gcs = 15  # assume alert if not charted

        pf = (pao2 / fio2) if (pao2 is not None and fio2) else None
        sf = (spo2 / fio2) if (spo2 is not None and fio2) else None
        pressor = pressor_times.get(t, None)

        s_resp = score_resp(pf, sf, False)
        s_coag = score_coag(plate)
        s_liver = score_liver(bili)
        s_card = score_cardio(map_v, pressor)
        s_cns = score_cns(gcs)
        s_renal = score_renal(creat)

        components = {
            "Resp": s_resp,
            "Coag": s_coag,
            "Liver": s_liver,
            "Cardio": s_card,
            "CNS": s_cns,
            "Renal": s_renal,
        }

        # Check completeness
        if any(v is None for v in components.values()):
            missing = [k for k, v in components.items() if v is None]
            if len(missing) >= 3:  # only print larger gaps
                print(f"      Missing for t={t:%Y-%m-%d %H:%M}: {', '.join(missing)}")
            continue

        sofa_total = sum(v for v in components.values() if v is not None)
        rows.append(
            {
                "patient_id": subject,
                "sofa_score_datetime": t,
                "sofa_score": int(sofa_total),
            }
        )

    print(f"   ✔️  Calculated {len(rows)} valid SOFA rows for patient '{subject}'.")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------
def main():
    print("Fetching data for all patients...\n")

    all_rows = []
    for sub in SUBJECTS:
        df = compute_patient_sofa(sub)
        if not df.empty:
            all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True)
    else:
        out = pd.DataFrame(
            columns=["patient_id", "sofa_score_datetime", "sofa_score"]
        )

    # Ensure datetime formatting
    out["sofa_score_datetime"] = pd.to_datetime(out["sofa_score_datetime"], errors="coerce")
    out["sofa_score_datetime"] = out["sofa_score_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    out.to_csv("submission.csv", index=False)
    print(
        f"\n✅ submission.csv written with {len(out)} rows. "
        f"({'STRICT 6h rule' if STRICT else 'DEMO 24h window'})"
    )


if __name__ == "__main__":
    main()
