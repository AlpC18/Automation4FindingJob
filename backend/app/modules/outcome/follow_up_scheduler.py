"""
Follow-up Automation Engine
Schedules professional, polite follow-up messages for Day 7 and Day 14 post-application.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from backend.app.core.database import get_db_connection

def generate_follow_up_email(company: str, title: str, day: int) -> str:
    if day <= 4:
        return f"""Hi {company} Hiring Team,

I hope you're having a productive week.

I submitted my application for the {title} position and wanted to reiterate my interest in {company}. I would appreciate any update when convenient.

Thank you very much for your time and consideration.

Best regards,"""
    elif day <= 9:
        return f"""Hi {company} Hiring Team,

I am following up on my application for the {title} position. I would be glad to provide any additional information that would be useful to your review.

Thank you for your time.

Best regards,"""
    else:
        return f"""Hi {company} Team,

I wanted to quickly check in regarding the status of the {title} opening. 

I understand hiring cycles can be demanding. Please let me know if you need any further information from me.

Wishing you all the best,"""

def schedule_follow_ups_for_job(job_data: Dict[str, Any]):
    job_id = job_data.get("id")
    company = job_data.get("company", "Company")
    title = job_data.get("title", "Role")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc)
    day4_date = (now + timedelta(days=4)).strftime("%Y-%m-%d")
    day9_date = (now + timedelta(days=9)).strftime("%Y-%m-%d")
    day14_date = (now + timedelta(days=14)).strftime("%Y-%m-%d")
    
    email_4 = generate_follow_up_email(company, title, 4)
    email_9 = generate_follow_up_email(company, title, 9)
    email_14 = generate_follow_up_email(company, title, 14)
    
    for due_day, due_date, draft in ((4, day4_date, email_4), (9, day9_date, email_9), (14, day14_date, email_14)):
        cursor.execute(
            """INSERT INTO follow_up_queue (job_id, due_day, scheduled_date, draft_email, status)
               SELECT ?, ?, ?, ?, 'PENDING'
               WHERE NOT EXISTS (
                   SELECT 1 FROM follow_up_queue WHERE job_id = ? AND due_day = ? AND status = 'PENDING'
               )""",
            (job_id, due_day, due_date, draft, job_id, due_day),
        )
    
    conn.commit()
    conn.close()

def get_pending_follow_ups() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, j.title, j.company, j.platform
        FROM follow_up_queue f
        JOIN scraped_jobs j ON f.job_id = j.id
        WHERE f.status = 'PENDING' AND f.scheduled_date <= ?
          AND j.status = 'Applied' AND COALESCE(j.submission_confirmed, 0) = 1
        ORDER BY f.scheduled_date ASC
    """, (datetime.now(timezone.utc).date().isoformat(),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
