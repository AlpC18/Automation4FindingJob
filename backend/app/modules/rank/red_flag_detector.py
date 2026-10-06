"""
Red Flag Detection Engine
Detects dealbreaker conflicts: location mismatch, remote/hybrid contradictions,
and excessive or mismatched seniority expectations.
"""

import re
from typing import Dict, Any, List

def detect_red_flags(job_data: Dict[str, Any], candidate_profile: Dict[str, Any]) -> List[str]:
    flags = []
    desc = (job_data.get("description") or "").lower()
    title = (job_data.get("title") or "").lower()
    location = (job_data.get("location") or "").lower()
    remote_type = (job_data.get("remote_type") or "").lower()
    cand_pref = candidate_profile.get("work_preference", "remote").lower()
    try:
        cand_exp = float(candidate_profile.get("years_of_experience")) if candidate_profile.get("years_of_experience") not in (None, "") else None
    except (TypeError, ValueError):
        cand_exp = None

    # 1. Remote / Hybrid Contradiction Check
    if "remote" in title or "remote" in remote_type:
        # Check if description contradicts with mandatory on-site
        contradiction_patterns = [
            r'must be located in',
            r'in-office (\d+) days',
            r'hybrid schedule (\d+) days in office',
            r'must relocate',
            r'relocation required',
            r'no remote'
        ]
        for pattern in contradiction_patterns:
            if re.search(pattern, desc):
                flags.append(f"Çelişkili Çalışma Modeli: Başlık 'Remote' ancak metinde zorunlu ofis/relocation şartı geçiyor ({pattern}).")
                break

    # 2. Location & Citizenship Red Flags
    if "only us citizens" in desc or "us citizenship required" in desc:
        flags.append("Vatandaşlık Engeli: Yalnızca ABD vatandaşlarına açık (ITAR/Clearance).")
    if "must have active security clearance" in desc:
        flags.append("Güvenlik Soruşturması Engeli: Aktif güvenlik izni (Security Clearance) talep ediliyor.")

    # 3. Seniority Mismatch
    req_years = None
    years_match = re.search(r'(\d+)\+?\s*years?\s+of\s+experience', desc)
    if years_match:
        req_years = int(years_match.group(1))
        if req_years >= 8 and cand_exp is not None and cand_exp < 4:
            flags.append(f"Kıdem Uyuşmazlığı: İlan {req_years}+ yıl deneyim isterken profilinizde {cand_exp} yıl kayıtlı.")
            
    # 4. Mandatory Unrealistic Stacks
    if "24/7 on-call" in desc or "on call rotation every weekend" in desc:
        flags.append("Aşırı Yük / Tükenmişlik Uyarısı: 24/7 zorunlu nöbet veya her hafta sonu mesai.")

    return flags
