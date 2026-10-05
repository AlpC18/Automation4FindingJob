"""
Interactive Interview Simulation Engine
Generates scenario-based technical, behavioral (STAR method), and cross-examination questions
based on the job description and evaluates candidate answers.
"""

from typing import Dict, Any, List

class InterviewSimulator:
    def generate_interview_session(self, job_title: str, company: str, job_description: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": "q1",
                "type": "Technical Architecture",
                "question": f"{company} bünyesinde {job_title} olarak görev alırken; yüksek eşzamanlı istek alan bir mikroserviste gecikme (latency) aniden 5 katına çıksaydı, sorunu tespit etmek ve çözmek için ilk 15 dakikada hangi adımları izlerdiniz?",
                "key_points": ["APM / Log analizi", "Veritabanı connection pool ve lock kontrolü", "Rate limiting ve rollback mekanizmaları"]
            },
            {
                "id": "q2",
                "type": "Behavioral (STAR Method)",
                "question": "Geçmiş projelerinizde bir takım arkadaşınızla veya ürün yöneticisiyle mimari bir kararda (örneğin teknoloji seçimi veya teslim tarihi) ters düştüğünüz oldu mu? Bu durumu nasıl çözdünüz?",
                "key_points": ["Situation & Task", "Action & Saygılı müzakere", "Result & Veriye dayalı karar"]
            },
            {
                "id": "q3",
                "type": "Security & Failure Recovery",
                "question": "Web kazıma (scraping) ve otonom veri akışlarında platformlar IP engellemesi (ban) veya Cloudflare/hCaptcha koruması devreye aldığında sistemin kesintiye uğramaması için nasıl bir savunma ve bypass stratejisi kurarsınız?",
                "key_points": ["Residential proxy rotation", "Exponential backoff & jitter", "Session/cookie persistence"]
            }
        ]

    def evaluate_candidate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Grades candidate response, detects strengths, and offers constructive improvement advice.
        """
        word_count = len(answer.split())
        score = 70
        feedback = []
        
        if word_count < 25:
            score -= 20
            feedback.append("Yanıtınız çok kısa. Somut adımlar, teknik araçlar ve metrikler ekleyerek zenginleştirin.")
        elif word_count > 180:
            score -= 10
            feedback.append("Yanıtınız biraz uzun ve dağılmış. Mülakatçının dikkatini canlı tutmak için STAR formatında daha öz (concise) ifade edin.")
        else:
            score += 15
            feedback.append("Cümle uzunluğu ve odak dengeli.")

        # Check for technical specifics
        if any(tech in answer.lower() for tech in ["log", "metric", "cache", "redis", "test", "docker", "veri", "hata"]):
            score += 15
            feedback.append("Teknik terimler ve pratik problem çözme adımları başarılı bir şekilde aktarılmış.")
            
        final_score = max(30, min(98, score))
        
        return {
            "score": final_score,
            "grade": "EXCELLENT" if final_score >= 85 else ("GOOD" if final_score >= 70 else "NEEDS_IMPROVEMENT"),
            "feedback": feedback,
            "coaching_tip": "Bir sonraki soruda sonucu (Result) sayısal bir veriyle (% artış, ms düşüş) bağlamaya özen gösterin."
        }

interview_simulator = InterviewSimulator()
