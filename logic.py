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
    }
