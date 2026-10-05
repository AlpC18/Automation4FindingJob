"""
Multilingual Cultural Tone Engine (PRD 1.4)
Adapts cover letters, cold outreach, and correspondence to localized workplace cultures:
- Kosovo / Balkan: Albanian (Shqip) respectful, formal business tone.
- Turkey: Turkish respectful corporate tone.
- Global: English concise, high-burstiness, outcome-driven tone.
"""

from typing import Dict, Any, List

class MultilingualCulturalEngine:
    SUPPORTED_CULTURES = ["global_en", "kosovo_sq", "turkey_tr"]

    def adapt_application_materials(
        self,
        culture_code: str,
        job_title: str,
        company: str,
        candidate_name: str,
        top_skills: List[str],
        rag_metrics: str = ""
    ) -> Dict[str, str]:
        code = culture_code.lower()
        skills_str = ", ".join(top_skills[:3])

        if code in ["kosovo_sq", "sq", "albanian", "kosovo"]:
            # Shqip / Albanian for Kosovo and regional Balkan companies
            greeting = f"I nderuar ekipi i rekrutimit në {company},"
            body = (
                f"Po ju shkruaj me interes të veçantë për pozitën {job_title}. "
                f"Duke pasur një përvojë të konsoliduar në {skills_str}, fokusohem në ndërtimin e sistemeve të qëndrueshme dhe me performancë të lartë."
            )
            val_prop = (
                f"Në projektet e mia të fundit kam arritur {rag_metrics or 'rezultate konkrete në optimizimin e sistemeve'}. "
                f"Vlerësoj lart qasjen bashkëpunuese dhe jam i gatshëm të kontribuoj menjëherë në objektivat tuaja teknike."
            )
            closing = "Me respekt,\n" + candidate_name
            culture_label = "Kosova / Shqip (Profesional & Respektues)"

            cold_dm = (
                f"Përshëndetje! Kam përcjellë me interes zhvillimet e {company} dhe pashë njoftimin për pozitën {job_title}. "
                f"Me përvojë në {skills_str}, ndërtoj zgjidhje teknike që ulin shpenzimet operative. "
                f"A keni kohë për një bisedë të shkurtër 5-minutëshe këtë javë?"
            )

        elif code in ["turkey_tr", "tr", "turkish", "turkey"]:
            # Türkçe / Turkish for Turkish tech market
            greeting = f"Merhaba {company} İşe Alım Ekibi,"
            body = (
                f"{job_title} pozisyonunuz için başvurumu iletmekten memnuniyet duyuyorum. "
                f"{skills_str} odaklı modern mimariler ve dağıtık sistemler üzerinde hands-on deneyime sahibim."
            )
            val_prop = (
                f"Son projelerimde {rag_metrics or 'ölçülebilir performans ve maliyet optimizasyonları'} sağladım. "
                f"Gereksiz karmaşıklıktan uzak, sürdürülebilir ve temiz kod prensiplerini benimsiyorum."
            )
            closing = "İyi çalışmalar dilerim,\n" + candidate_name
            culture_label = "Türkiye / Türkçe (Kurumsal & Sonuç Odaklı)"

            cold_dm = (
                f"Merhabalar, {company}'nin teknik projelerini ilgiyle takip ediyorum ve açık olan {job_title} ilanınızı gördüm. "
                f"{skills_str} alanındaki uzmanlığımla yüksek dayanımlı sistemler kuruyorum. "
                f"Müsait olduğunuzda yol haritanız üzerine 5 dakikalık kısa bir görüşme gerçekleştirebilir miyiz?"
            )

        else:
            # Global English / US-EU Remote
            greeting = f"Hi {company} team,"
            body = (
                f"I am writing regarding the {job_title} role. "
                f"With deep experience in {skills_str}, I specialize in building resilient architectures and autonomous workflows."
            )
            val_prop = (
                f"Recently, I delivered {rag_metrics or 'measurable performance improvements'} across production microservices. "
                f"My engineering approach emphasizes maintainable systems, thorough testing, and zero unnecessary operational friction."
            )
            closing = "Best regards,\n" + candidate_name
            culture_label = "Global / US-EU (Direct, Punchy & Technical)"

            cold_dm = (
                f"I've been following {company}'s recent technical initiatives and noticed your open {job_title} position. "
                f"With a strong background in {skills_str}, I build reliable architectures that reduce operational overhead. "
                f"Open to a brief 5-minute chat this week to compare notes on your current tech stack?"
            )

        full_letter = f"{greeting}\n\n{body}\n\n{val_prop}\n\n{closing}"

        return {
            "culture_code": code,
            "culture_label": culture_label,
            "cover_letter": full_letter,
            "cold_outreach_dm": cold_dm
        }

cultural_engine = MultilingualCulturalEngine()
