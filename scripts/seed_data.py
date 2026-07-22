import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta

import httpx


@dataclass
class UserProfile:
    name: str
    weight_baseline: float
    height: float
    systolic_baseline: int
    diastolic_baseline: int
    sugar_baseline: int


USER_PROFILES = [
    UserProfile("alice", 60.0, 165, 115, 75, 90),
    UserProfile("bob", 85.0, 172, 128, 84, 105),
    UserProfile("carol", 68.0, 158, 145, 92, 98),
    UserProfile("dave", 72.0, 170, 118, 78, 132),
]

WEIGHT_DAILY_DELTA, WEIGHT_RANGE, WEIGHT_ABS = 0.3, 2.0, (40.0, 150.0)
SYSTOLIC_DAILY_DELTA, SYSTOLIC_RANGE, SYSTOLIC_ABS = 4, 15, (90, 180)
DIASTOLIC_DAILY_DELTA, DIASTOLIC_RANGE, DIASTOLIC_ABS = 3, 10, (50, 120)
SUGAR_DAILY_DELTA, SUGAR_RANGE, SUGAR_ABS = 5, 20, (70, 200)
STEPS_RANGE = (2000, 15000)
SLEEP_RANGE = (4.0, 9.5)
SAMPLE_MEMOS = ["운동 다녀옴", "야근해서 늦게 잠", "물 많이 마심", "컨디션 좋음", "짠 음식 많이 먹음", ""]
SEED_PASSWORD = "seed-pass-1234"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def generate_user_records(user: UserProfile, days: int, today: date) -> list[dict]:
    records = []
    weight = user.weight_baseline
    systolic = float(user.systolic_baseline)
    diastolic = float(user.diastolic_baseline)
    sugar = float(user.sugar_baseline)

    for day_offset in range(days, 0, -1):
        record_date = today - timedelta(days=day_offset)

        weight = clamp(
            weight + random.uniform(-WEIGHT_DAILY_DELTA, WEIGHT_DAILY_DELTA),
            user.weight_baseline - WEIGHT_RANGE, user.weight_baseline + WEIGHT_RANGE,
        )
        systolic = clamp(
            systolic + random.uniform(-SYSTOLIC_DAILY_DELTA, SYSTOLIC_DAILY_DELTA),
            user.systolic_baseline - SYSTOLIC_RANGE, user.systolic_baseline + SYSTOLIC_RANGE,
        )
        diastolic = clamp(
            diastolic + random.uniform(-DIASTOLIC_DAILY_DELTA, DIASTOLIC_DAILY_DELTA),
            user.diastolic_baseline - DIASTOLIC_RANGE, user.diastolic_baseline + DIASTOLIC_RANGE,
        )
        sugar = clamp(
            sugar + random.uniform(-SUGAR_DAILY_DELTA, SUGAR_DAILY_DELTA),
            user.sugar_baseline - SUGAR_RANGE, user.sugar_baseline + SUGAR_RANGE,
        )

        weight = clamp(weight, *WEIGHT_ABS)
        systolic = clamp(systolic, *SYSTOLIC_ABS)
        diastolic = clamp(diastolic, *DIASTOLIC_ABS)
        sugar = clamp(sugar, *SUGAR_ABS)

        records.append({
            "date": record_date.isoformat(),
            "weight": round(weight, 1),
            "height": user.height,
            "systolic": round(systolic),
            "diastolic": round(diastolic),
            "blood_sugar": round(sugar),
            "steps": random.randint(*STEPS_RANGE),
            "sleep_hours": round(random.uniform(*SLEEP_RANGE), 1),
            "memo": random.choice(SAMPLE_MEMOS),
        })

    return records


def get_token(client: httpx.Client, username: str, password: str) -> str:
    signup_res = client.post("/auth/signup", json={"username": username, "password": password})
    if signup_res.status_code not in (201, 400):
        signup_res.raise_for_status()

    login_res = client.post("/auth/login", data={"username": username, "password": password})
    login_res.raise_for_status()
    return login_res.json()["access_token"]


def seed(host: str, days: int) -> None:
    with httpx.Client(base_url=host, timeout=10.0) as client:
        for user in USER_PROFILES:
            token = get_token(client, user.name, SEED_PASSWORD)
            headers = {"Authorization": f"Bearer {token}"}
            records = generate_user_records(user, days, date.today())
            for record in records:
                response = client.post("/records", json=record, headers=headers)
                response.raise_for_status()
            print(f"{user.name}: {len(records)}건 생성")


def main() -> None:
    parser = argparse.ArgumentParser(description="헬스 로그 테스트 데이터 자동 생성")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    seed(args.host, args.days)


if __name__ == "__main__":
    main()
