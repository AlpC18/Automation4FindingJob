"""
Ghost Job & Company Health Detection Engine
Evaluates job postings against ghost-job markers (excessive age, repetitive reposts,
vague boilerplate descriptions, absence of actual hiring signals).
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from backend.app.core.config import settings

def evaluate_ghost_job(job_data: Dict[str, Any]) -> Tuple[float, List[str], str]:
    """
    Returns (ghost_score: float 0-100, reasons: List[str], recommendation: str)
    """
    score = 0.0
    reasons = []
    
    # 1. Job Age Factor
    posted_date_str = job_data.get("posted_date", "")
    age_days = 0
    if posted_date_str:
        # Check standard formats or relative phrases
        if "month" in posted_date_str.lower() or "30+" in posted_date_str:
            age_days = 45
        elif "week" in posted_date_str.lower():
            match = re.search(r'(\d+)', posted_date_str)
            weeks = int(match.group(1)) if match else 2
            age_days = weeks * 7
            
    if age_days >= settings.GHOST_JOB_DAYS_THRESHOLD:
        score += 35.0
        reasons.append(f"İlan {age_days}+ gündür açık (45 gün eşiği aşıldı). Şirket aktif alım yapmıyor olabilir.")
    elif age_days >= 30:
        score += 20.0
        reasons.append("İlan 30 gündür açık kalmış.")

    # 2. Check for Repetitive Repost indicator
    description = (job_data.get("description") or "").lower()
    title = (job_data.get("title") or "").lower()
    
    if "reposted" in description or "reposted" in (job_data.get("posted_date") or "").lower():
        score += 25.0
        reasons.append("İlan yakın zamanda yeniden yayınlanmış (Reposted). Pozisyonun doldurulamama veya havuz oluşturma riski var.")
        
    # 3. Vague Description & Buzzword Stacking (Sign of resume-harvesting ghost jobs)
    generic_cliches = ["fast-paced environment", "wear many hats", "rockstar", "ninja", "dynamic environment", "competitive compensation"]
    found_cliches = [c for c in generic_cliches if c in description]
    if len(found_cliches) >= 3:
        score += 15.0
        reasons.append(f"Aşırı jenerik metin ve belirsiz görev tanımı tespit edildi ({len(found_cliches)} klişe).")
        
    # 4. Salary Transparency Check
    salary = job_data.get("salary_range", "Not disclosed")
    if not salary or salary == "Not disclosed" or salary == "":
        score += 10.0
        reasons.append("Maaş aralığı veya bütçe şeffaf olarak belirtilmemiş.")
        
    # 5. Overwhelming applicant count
    applicants_count = job_data.get("applicants_count", 0)
    if applicants_count > 250:
        score += 15.0
        reasons.append(f"250'den fazla aday ({applicants_count}) başvurmuş; doymuş veya açık unutulmuş ilan riski.")

    # Bound score 0-100
    score = min(100.0, round(score, 1))
    
    if score >= 60:
        rec = "YÜKSEK RİSK (Hayalet İlan): Başvuruyu ertele veya sadece karar vericiye doğrudan mesaj at."
    elif score >= 35:
        rec = "ORTA DERECE RİSK: Standart başvuru yapılabilir ancak öncelik düşük tutulmalı."
    else:
        rec = "GÜVENLİ & AKTİF İLAN: İlan taze ve gerçek alım göstergelerine sahip."
        
    return score, reasons, rec
