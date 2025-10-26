from __future__ import annotations
from typing import Optional, Dict
from math import isfinite

def score_resp(pao2_fio2: Optional[float], spo2_fio2: Optional[float], on_resp_support: bool) -> Optional[int]:
    if pao2_fio2 is not None and isfinite(pao2_fio2):
        pf = pao2_fio2
        if pf >= 400: return 0
        if pf < 400 and pf >= 300: return 1
        if pf < 300 and pf >= 200: return 2
        if pf < 200 and pf >= 100: return 3
        if pf < 100: return 4
        return None
    if spo2_fio2 is None or not isfinite(spo2_fio2):
        return None
    sf = spo2_fio2
    if sf > 302: return 0
    if sf < 302 and sf >= 221: return 1
    if sf < 221 and sf >= 142: return 2
    if sf < 142:
        return 3 if on_resp_support else 2
    if sf < 67:
        return 4 if on_resp_support else 3
    return None

def score_coag(platelets_x10e3_per_uL: Optional[float]) -> Optional[int]:
    v = platelets_x10e3_per_uL
    if v is None: return None
    if v >= 150: return 0
    if v < 150 and v >= 100: return 1
    if v < 100 and v >= 50:  return 2
    if v < 50  and v >= 20:  return 3
    if v < 20:  return 4
    return None

def score_liver(bili_mg_dl: Optional[float]) -> Optional[int]:
    v = bili_mg_dl
    if v is None: return None
    if v < 1.2: return 0
    if 1.2 <= v <= 1.9: return 1
    if 2.0 <= v <= 5.9: return 2
    if 6.0 <= v <= 11.9: return 3
    if v >= 12.0: return 4
    return None

def score_cardio(map_mmHg: Optional[float], pressor: Optional[Dict[str, float]] = None) -> Optional[int]:
    if pressor:
        dob = pressor.get('dobutamine')
        if dob is not None:
            return 2
        dop = pressor.get('dopamine')
        ne = pressor.get('norepinephrine')
        epi = pressor.get('epinephrine')
        if (dop is not None and dop > 15) or (ne is not None and ne > 0.1) or (epi is not None and epi > 0.1):
            return 4
        if (dop is not None and 5.1 <= dop <= 15) or (ne is not None and 0.0 < ne <= 0.1) or (epi is not None and 0.0 < epi <= 0.1):
            return 3
        if dop is not None and dop < 5:
            return 2
    if map_mmHg is None:
        return None
    return 0 if map_mmHg >= 70 else 1

def score_cns(gcs_total: Optional[float]) -> Optional[int]:
    v = gcs_total
    if v is None: return None
    if v == 15: return 0
    if 13 <= v <= 14: return 1
    if 10 <= v <= 12: return 2
    if 6 <= v <= 9:   return 3
    if v < 6: return 4
    return None

def score_renal(creatinine_mg_dl: Optional[float]) -> Optional[int]:
    v = creatinine_mg_dl
    if v is None: return None
    if v < 1.2: return 0
    if 1.2 <= v <= 1.9: return 1
    if 2.0 <= v <= 3.4: return 2
    if 3.5 <= v <= 4.9: return 3
    if v >= 5.0: return 4
    return None
