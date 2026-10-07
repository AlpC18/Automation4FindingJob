from typing import Optional, Tuple
import re
"""
Salary Benchmark & Market Compensation Engine
Calculates market compensation percentiles (25th, 50th median, 75th, 90th)
based on role type, seniority, and geographic region.
"""

from typing import Dict, Any

BENCHMARK_TABLE = {
    "kosovo": {
        "junior": {"min": 1000, "median": 1400, "max": 1800, "currency": "EUR", "period": "month"},
        "mid": {"min": 1600, "median": 2300, "max": 3000, "currency": "EUR", "period": "month"},
        "senior": {"min": 2800, "median": 3800, "max": 5200, "currency": "EUR", "period": "month"},
        "lead": {"min": 4000, "median": 5500, "max": 7500, "currency": "EUR", "period": "month"},
    },
    "turkey": {
        "junior": {"min": 45000, "median": 65000, "max": 85000, "currency": "TRY", "period": "month"},
        "mid": {"min": 75000, "median": 110000, "max": 150000, "currency": "TRY", "period": "month"},
        "senior": {"min": 140000, "median": 190000, "max": 260000, "currency": "TRY", "period": "month"},
        "lead": {"min": 220000, "median": 300000, "max": 420000, "currency": "TRY", "period": "month"},
    },
    "global_remote": {
        "junior": {"min": 50000, "median": 70000, "max": 90000, "currency": "USD", "period": "year"},
        "mid": {"min": 85000, "median": 115000, "max": 140000, "currency": "USD", "period": "year"},
        "senior": {"min": 130000, "median": 165000, "max": 210000, "currency": "USD", "period": "year"},
        "lead": {"min": 180000, "median": 230000, "max": 290000, "currency": "USD", "period": "year"},
    }
}

def calculate_salary_benchmark(title: str, location: str, years_exp: int | None) -> Dict[str, Any]:
    # Determine seniority
    title_lower = title.lower()
    if "lead" in title_lower or "staff" in title_lower or "principal" in title_lower or (years_exp is not None and years_exp >= 8):
        seniority = "lead"
    elif "senior" in title_lower or (years_exp is not None and years_exp >= 5):
        seniority = "senior"
    elif "junior" in title_lower or "intern" in title_lower or (years_exp is not None and years_exp <= 2):
        seniority = "junior"
    elif years_exp is None:
        loc_lower = location.lower()
        if any(k in loc_lower for k in ["kosovo", "prishtina", "prishtine", "prizren", "gjilan", "albania"]):
            region, region_label = "kosovo", "Kosova & Bölgesel Piyasa"
        elif any(k in loc_lower for k in ["turkey", "türkiye", "istanbul", "ankara", "izmir"]):
            region, region_label = "turkey", "Türkiye Bilişim Sektörü"
        else:
            region, region_label = "global_remote", "Global / US-EU Remote Piyasa"
        return {
            "region": region, "region_label": region_label, "seniority_level": None,
            "min_expected": None, "median_expected": None, "max_expected": None,
            "currency": None, "period": None, "source_type": "modeled_estimate",
            "is_company_reported": False, "evidence_level": "estimate_only",
            "formatted_display": "Deneyim bilgisi olmadan tahmin üretilemiyor",
            "disclaimer": "Deneyim yılı profilde belirtilmediği için piyasa aralığı hesaplanmadı.",
        }
    else:
        seniority = "mid"
        
    # Determine region
    loc_lower = location.lower()
    if any(k in loc_lower for k in ["kosovo", "prishtina", "prishtine", "prizren", "gjilan", "albania"]):
        region = "kosovo"
        region_label = "Kosova & Bölgesel Piyasa"
    elif any(k in loc_lower for k in ["turkey", "türkiye", "istanbul", "ankara", "izmir"]):
        region = "turkey"
        region_label = "Türkiye Bilişim Sektörü"
    else:
        region = "global_remote"
        region_label = "Global / US-EU Remote Piyasa"
        
    data = BENCHMARK_TABLE.get(region, BENCHMARK_TABLE["global_remote"])[seniority]
    
    return {
        "region": region,
        "region_label": region_label,
        "seniority_level": seniority.upper(),
        "min_expected": data["min"],
        "median_expected": data["median"],
        "max_expected": data["max"],
        "currency": data["currency"],
        "period": data["period"],
        "source_type": "modeled_estimate",
        "is_company_reported": False,
        "evidence_level": "estimate_only",
        "disclaimer": "Rule-based market estimate; not reported or verified by the employer.",
        "formatted_display": f"{data['min']:,} - {data['max']:,} {data['currency']} / {data['period']}",
        "counter_offer_target": f"{int(data['median'] * 1.12):,} {data['currency']}"
    }


_AMOUNT = re.compile(r"(\d[\d,.]*)\s*(k)?", re.IGNORECASE)
_OTHER_CURRENCY = re.compile(r"€|£|₺|\b(EUR|GBP|MXN|INR|TRY|CAD|AUD|PLN|BRL|CHF|SEK|JPY)\b", re.IGNORECASE)
HOURS_PER_YEAR = 2080
# Below this a yearly figure is implausible for the roles scanned, so the listing means per month.
MONTHLY_BELOW = 15000


def yearly_usd(salary_text: Any) -> Optional[Tuple[int, int]]:
    """The pay a listing states, as (low, high) US dollars per year; None when it is absent,
    in another currency, or not a number. Used only to sort and filter; the original text is what is shown."""
    text = str(salary_text or "")
    if not text.strip() or _OTHER_CURRENCY.search(text):
        return None
    amounts = []
    for number, thousand in _AMOUNT.findall(text):
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        amounts.append(value * 1000 if thousand else value)
    amounts = [value for value in amounts if value >= 10][:2]
    if not amounts or ("$" not in text and "usd" not in text.lower() and max(amounts) < 10000):
        return None
    if re.search(r"/\s*(hour|hr|saat)|per hour|hourly", text, re.IGNORECASE):
        amounts = [value * HOURS_PER_YEAR for value in amounts]
    elif max(amounts) < MONTHLY_BELOW:
        amounts = [value * 12 for value in amounts]
    return int(min(amounts)), int(max(amounts))
