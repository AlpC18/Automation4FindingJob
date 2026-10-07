"""
Red Flag Detection Engine
Detects dealbreaker conflicts: location mismatch, remote/hybrid contradictions,
and excessive or mismatched seniority expectations.
"""

import re
from typing import Dict, Any, Iterable, List

from backend.app.core.config import settings

# A posting with one of these in its location is open to someone in Europe or anywhere.
OPEN_LOCATION_WORDS = ("worldwide", "anywhere", "global", "unspecified", "europe", "emea")
# ponytail: a short city list so "Berlin" counts as Germany; use a gazetteer if more countries get added.
CITY_COUNTRY = {
    "berlin": "germany", "munich": "germany", "hamburg": "germany", "stuttgart": "germany", "frankfurt": "germany",
    "cologne": "germany", "düsseldorf": "germany", "pristina": "kosovo", "prishtina": "kosovo",
}
_BASED_IN = re.compile(r"must be (?:based|located|residing) in ([^.;\n]{2,80})")


def location_excludes(posting_location: str, candidate_location: str, extra_places: Iterable[str] = ()) -> bool:
    """True when the posting names places and none of them is where the candidate is or can work."""
    # "Remote" alone is open; "Remote, USA" is still limited to the USA.
    posting = re.sub(r"[^\w ,/]", " ", (posting_location or "").lower().replace("remote", " ")).strip(" ,/")
    places = [part.strip().lower() for part in [*(candidate_location or "").split(","), *extra_places] if part.strip()]
    if not posting or not (candidate_location or "").strip() or any(word in posting for word in OPEN_LOCATION_WORDS):
        return False
    named = posting + " " + " ".join(country for city, country in CITY_COUNTRY.items() if city in posting)
    return not any(place in named for place in places)


def _extra_work_places() -> List[str]:
    return [place.strip() for place in settings.EXTRA_WORK_LOCATIONS.split(",") if place.strip()]


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

    # 2. Location the candidate is outside of, from the location field or a "must be based in" sentence
    candidate_location = candidate_profile.get("location") or ""
    restricted_to = job_data.get("location") or ""
    if not location_excludes(restricted_to, candidate_location, _extra_work_places()):
        stated = _BASED_IN.search(desc)
        restricted_to = stated.group(1).strip() if stated and location_excludes(stated.group(1), candidate_location, _extra_work_places()) else ""
    if restricted_to:
        flags.append(f"Konum Uyuşmazlığı: İlan '{restricted_to}' ile sınırlı; konumun ({candidate_location}) bunun dışında.")

    # 3. Citizenship Red Flags
    if "only us citizens" in desc or "us citizenship required" in desc:
        flags.append("Vatandaşlık Engeli: Yalnızca ABD vatandaşlarına açık (ITAR/Clearance).")
    if "must have active security clearance" in desc:
        flags.append("Güvenlik Soruşturması Engeli: Aktif güvenlik izni (Security Clearance) talep ediliyor.")

    # 4. Seniority Mismatch
    req_years = None
    years_match = re.search(r'(\d+)\+?\s*years?\s+of\s+experience', desc)
    if years_match:
        req_years = int(years_match.group(1))
        if req_years >= 8 and cand_exp is not None and cand_exp < 4:
            flags.append(f"Kıdem Uyuşmazlığı: İlan {req_years}+ yıl deneyim isterken profilinizde {cand_exp} yıl kayıtlı.")
            
    # 5. Mandatory Unrealistic Stacks
    if "24/7 on-call" in desc or "on call rotation every weekend" in desc:
        flags.append("Aşırı Yük / Tükenmişlik Uyarısı: 24/7 zorunlu nöbet veya her hafta sonu mesai.")

    return flags
