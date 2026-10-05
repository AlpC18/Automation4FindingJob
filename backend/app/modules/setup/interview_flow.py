"""
Dynamic Interview Flow
Identifies missing high-impact CV data (quantifiable metrics, GitHub/portfolio links,
certifications, employment gaps) and generates conversational interview questions.
"""

from typing import List, Dict, Any

def audit_cv_completeness(cv_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Scans candidate profile data and identifies gaps that need dynamic interview clarification.
    """
    questions = []
    
    # 1. Check for quantifiable achievements (metrics like % increase, latency drop, revenue)
    exp = cv_data.get("experience", [])
    has_metrics = False
    for item in exp:
        bullets = " ".join(item.get("bullets", []))
        if any(char in bullets for char in ["%", "$", "€", "₺", "x", "ms", "K", "M"]):
            has_metrics = True
            break
            
    if not has_metrics:
        questions.append({
            "category": "metrics",
            "question": "Geçmiş iş deneyimlerinizde ölçülebilir bir başarı sağladınız mı? (Örn: 'Performansı %35 artırdım', 'Gecikmeyi 150ms'den 20ms'ye indirdim')"
        })
        
    # 2. Check for portfolio / GitHub link
    skills = [s.lower() for s in cv_data.get("skills", [])]
    summary = (cv_data.get("summary") or "").lower()
    raw_text = (cv_data.get("raw_cv_text") or "").lower()
    all_text = f"{summary} {raw_text}"
    
    if "github.com" not in all_text and "gitlab.com" not in all_text:
        questions.append({
            "category": "portfolio",
            "question": "İşverenlerin kodlama becerinizi incelemesi için GitHub veya canlı bir portfolyo / proje linkiniz var mı?"
        })
        
    # 3. Check for specific certifications
    if not cv_data.get("education") or len(cv_data.get("education", [])) == 0:
        questions.append({
            "category": "education",
            "question": "Eğitim veya son 2 yılda aldığınız teknik sertifikalar (AWS, GCP, CKA, Scrimba vb.) var mı?"
        })
        
    # 4. Check for remote work preference / availability
    if not cv_data.get("work_preference"):
        questions.append({
            "category": "preference",
            "question": "Çalışma tercihleriniz nelerdir? (Tamamen Remote, Hibrit, Türkiye içi veya Kosova/Balkanlar/Global uzaktan)"
        })
        
    # 5. Language proficiencies
    if not cv_data.get("languages"):
        questions.append({
            "category": "languages",
            "question": "İngilizce, Türkçe veya diğer dillerdeki (Arnavutça, Almanca vb.) yetkinlik seviyeniz nedir?"
        })
        
    return questions
