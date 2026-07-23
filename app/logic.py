from typing import Any


def calculate_bmi(weight: float, height: float) -> float:
    height_m = height / 100
    return round(weight / (height_m * height_m), 1)


def classify_bmi(bmi: float) -> str:
    if bmi < 18.5:
        return "저체중"
    if bmi <= 22.9:
        return "정상"
    if bmi <= 24.9:
        return "과체중"
    return "비만"


def classify_bp(systolic: int, diastolic: int) -> str:
    if systolic >= 140 or diastolic >= 90:
        return "고혈압"
    if systolic < 120 and diastolic < 80:
        return "정상"
    return "주의"


def classify_sugar(blood_sugar: int) -> str:
    if blood_sugar < 100:
        return "정상"
    if blood_sugar <= 125:
        return "공복혈당장애"
    return "당뇨 의심"


def classify_steps(steps: int) -> str:
    if steps < 5000:
        return "부족"
    if steps <= 9999:
        return "적정"
    return "우수"


def classify_sleep(sleep_hours: float) -> str:
    if sleep_hours < 7:
        return "부족"
    if sleep_hours <= 9:
        return "적정"
    return "과다"


def generate_warnings(bmi_category: str, bp_category: str, sugar_category: str) -> list[str]:
    warnings = []
    if bmi_category == "비만":
        warnings.append("BMI가 비만 범위예요, 관리가 필요해요!")
    if bp_category == "고혈압":
        warnings.append("혈압이 고혈압 범위예요, 병원 상담을 권장해요!")
    if sugar_category == "당뇨 의심":
        warnings.append("공복 혈당이 높아요, 당뇨 의심 범위이니 확인이 필요해요!")
    return warnings


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    bmi = calculate_bmi(record["weight"], record["height"])
    bmi_category = classify_bmi(bmi)
    bp_category = classify_bp(record["systolic"], record["diastolic"])
    sugar_category = classify_sugar(record["blood_sugar"])
    warnings = generate_warnings(bmi_category, bp_category, sugar_category)
    return {
        **record,
        "bmi": bmi,
        "bmi_category": bmi_category,
        "bp_category": bp_category,
        "sugar_category": sugar_category,
        "warnings": warnings,
        "steps_grade": classify_steps(record["steps"]),
        "sleep_category": classify_sleep(record["sleep_hours"]),
    }


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def calculate_averages(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    enriched = [enrich_record(r) for r in records]
    count = len(enriched)
    return {
        "count": count,
        "avg_weight": round(sum(r["weight"] for r in enriched) / count, 1),
        "avg_bmi": round(sum(r["bmi"] for r in enriched) / count, 1),
        "avg_systolic": round(sum(r["systolic"] for r in enriched) / count, 1),
        "avg_diastolic": round(sum(r["diastolic"] for r in enriched) / count, 1),
        "avg_blood_sugar": round(sum(r["blood_sugar"] for r in enriched) / count, 1),
        "avg_steps": round(sum(r["steps"] for r in enriched) / count, 1),
        "avg_sleep_hours": round(sum(r["sleep_hours"] for r in enriched) / count, 1),
    }


def calculate_achievement_percent(start: float, current: float, target: float) -> float:
    if start == target:
        return 100.0
    percent = (start - current) / (start - target) * 100
    return round(clamp(percent, 0, 100), 1)


def calculate_goal_achievement(goal: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any] | None:
    relevant = sorted((r for r in records if r["date"] >= goal["set_date"]), key=lambda r: r["date"])
    if not relevant:
        return None
    start = relevant[0]
    current = relevant[-1]
    return {
        "weight_percent": calculate_achievement_percent(start["weight"], current["weight"], goal["target_weight"]),
        "systolic_percent": calculate_achievement_percent(start["systolic"], current["systolic"], goal["target_systolic"]),
        "diastolic_percent": calculate_achievement_percent(start["diastolic"], current["diastolic"], goal["target_diastolic"]),
    }
