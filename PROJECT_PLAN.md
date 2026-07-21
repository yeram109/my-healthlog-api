# 마이 헬스 로그 API — 개발 기획서

> 이 문서는 「헬스케어 미니프로젝트 과제명세서」를 기반으로, 구현 전 모호했던 부분을 모두 결정하여 작성한 상세 기획서입니다. Claude Code와 작업할 때 이 문서를 기준으로 진행합니다.

---

## 1. 프로젝트 개요

**한 줄 기획**: 매일 건강 수치를 기록하는 사람이, 몸무게·혈압·혈당을 입력하기만 하면 BMI 계산·건강 상태 분류·경고를 자동으로 받고, 사용자별로 기록을 분리해서 통계와 히스토리를 확인할 수 있는 API.

**미션**: 건강 수치(몸무게·키·혈압·혈당 등)를 기록하면 서버가 BMI를 자동 계산하고 건강 상태를 분류하며, 쌓인 기록으로 통계를 제공하는 API를 Docker로 실행 가능하게 만든다.

**학습용 프로젝트 안내**: 이 프로젝트의 건강 분류 기준은 학습을 위해 단순화된 값이며, 실제 의학적 진단이 아닙니다.

**과제 형태**: 개인 프로젝트 (1인 1API) · 4일, 하루 4시간
**제출물**: GitHub 저장소 URL (Public, 마지막 코드까지 push 완료) + README

---

## 2. 기술 스택 & 개발 환경

| 항목 | 선택 |
|---|---|
| 언어 | Python **3.12** (버전 고정, README에 명시) |
| 프레임워크 | FastAPI + Uvicorn |
| 데이터 검증 | Pydantic |
| 데이터 저장 | JSON 파일 (`data.json`) |
| 가상환경 | venv |
| 테스트 | pytest + httpx (FastAPI TestClient) |
| 배포 | Docker (Dockerfile + .dockerignore) |
| 프론트엔드 | 순수 HTML + JS (프레임워크·빌드 도구 없음, fetch로 API 호출) |

**로컬 셋업 예시**
```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install fastapi uvicorn pytest httpx
uvicorn main:app --reload
# http://127.0.0.1:8000/docs 에서 API 테스트
# http://127.0.0.1:8000/ 에서 화면 확인
```

---

## 3. 프로젝트 폴더 구조

```
health-log-api/
├── main.py             # FastAPI 앱 생성, 라우터 정의, 정적 파일 마운트
├── models.py            # Pydantic 모델 (RecordIn, RecordOut 등)
├── logic.py              # BMI 계산 · 분류 · 경고 생성 함수
├── storage.py             # data.json 읽기/쓰기, next_id 관리, 소유권 체크
├── static/
│   └── index.html          # 간단 화면 (입력 폼 + 목록 조회 + 수정/삭제)
├── scripts/
│   └── seed_data.py         # 개발용 테스트 데이터 자동 생성 스크립트 (15장 참고)
├── tests/
│   └── test_records.py      # pytest 자동 테스트
├── data.json                 # 런타임 생성 (.gitignore 처리)
├── requirements.txt
├── requirements-dev.txt        # 개발 도구 전용 의존성 (예: requests/httpx for seed_data.py)
├── Dockerfile
├── .dockerignore               # scripts/ 포함, 이미지에서 제외
├── .gitignore
└── README.md
```

**역할 분리 원칙**: `main.py`는 라우팅만 담당하고, 계산 로직(`logic.py`)과 저장 로직(`storage.py`)은 분리하여 각각 독립적으로 테스트·수정 가능하게 한다.

---

## 4. 데이터 모델

### 4.1 기록 필드

| 필드 | 타입 | 설명 | 필수 여부 |
|---|---|---|---|
| date | str | 측정일, `YYYY-MM-DD` 형식 검증 | 필수 |
| weight | float | 몸무게(kg) | 필수 |
| height | float | 키(cm) | 필수 |
| systolic | int | 수축기 혈압 | 필수 |
| diastolic | int | 이완기 혈압 | 필수 |
| blood_sugar | int | 공복 혈당(mg/dL) | 필수 |
| steps | int | 걸음 수 | 선택, 기본 0 |
| sleep_hours | float | 수면 시간 | 선택, 기본 0.0 |
| memo | str | 메모 | 선택, 기본 "" |
| user | str | 소유자 태그 | 응답에 자동 포함 (`X-User-Id` 헤더에서 가져옴) |

응답에는 위 필드 + 서버가 **동적 계산**한 `id`, `bmi`, `bmi_category`, `bp_category`, `sugar_category`, `warnings`가 포함된다.

### 4.2 Pydantic 모델 (개념 정의)

```python
class RecordIn(BaseModel):
    date: str          # YYYY-MM-DD 형식 검증 (validator 또는 date 타입 활용)
    weight: float
    height: float
    systolic: int
    diastolic: int
    blood_sugar: int
    steps: int = 0
    sleep_hours: float = 0.0
    memo: str = ""

class RecordOut(RecordIn):
    id: int
    user: str
    bmi: float
    bmi_category: str
    bp_category: str
    sugar_category: str
    warnings: list[str]
```

### 4.3 data.json 저장 구조

```json
{
  "next_id": 4,
  "records": [
    {
      "id": 1,
      "user": "guest",
      "date": "2026-07-20",
      "weight": 70.5,
      "height": 175,
      "systolic": 118,
      "diastolic": 76,
      "blood_sugar": 95,
      "steps": 8000,
      "sleep_hours": 7.5,
      "memo": ""
    }
  ]
}
```

**중요 원칙**:
- `next_id`를 별도로 관리해 삭제 후에도 id가 재사용되지 않게 한다.
- `bmi` / `bmi_category` / `bp_category` / `sugar_category` / `warnings`는 **파일에 저장하지 않는다.** 매 요청마다 원본 값(weight, height, systolic, diastolic, blood_sugar)으로부터 `logic.py`에서 동적으로 계산해 응답에 포함한다. (분류 기준이 바뀌어도 기존 데이터가 낡은 값으로 남지 않도록)

---

## 5. 비즈니스 로직 — 계산 & 분류 규칙

### 5.1 BMI 계산
```
BMI = 몸무게(kg) ÷ (키(m) × 키(m))
```
- 키는 cm로 입력받으므로 100으로 나눠 m로 변환
- 결과는 **소수점 1자리**로 반올림

### 5.2 분류 기준

**BMI**
| 구간 | 분류 |
|---|---|
| 18.5 미만 | 저체중 |
| 18.5 ~ 22.9 | 정상 |
| 23 ~ 24.9 | 과체중 |
| 25 이상 | 비만 |

**혈압**
| 구간 | 분류 |
|---|---|
| 수축기 <120 그리고 이완기 <80 | 정상 |
| 120~139 또는 80~89 | 주의 |
| 수축기 ≥140 또는 이완기 ≥90 | 고혈압 |

**공복혈당**
| 구간 | 분류 |
|---|---|
| 100 미만 | 정상 |
| 100 ~ 125 | 공복혈당장애 |
| 126 이상 | 당뇨 의심 |

### 5.3 경고(warnings) 규칙

- **톤**: 친근한 조언형 (딱딱한 사실 나열이 아니라 조언하듯이)
- BMI가 비만이면 → 예: `"BMI가 비만 범위예요, 관리가 필요해요!"`
- 혈압이 고혈압이면 → 예: `"혈압이 고혈압 범위예요, 병원 상담을 권장해요!"`
- 혈당이 당뇨 의심이면 → 예: `"공복 혈당이 높아요, 당뇨 의심 범위이니 확인이 필요해요!"`
- 해당 없으면 → 빈 배열 `[]`

---

## 6. 사용자 구분 & 권한 정책

- **식별 방법**: 모든 요청에 `X-User-Id` 헤더 사용 (인증 없는 단순 태그 방식)
- **기본값**: 헤더가 없으면 `guest`로 처리
- **조회 범위**:
  - `GET /records`, `GET /search`, `GET /stats` → 기본적으로 **본인(`X-User-Id`) 기록만** 대상
  - `X-User-Id: admin`으로 요청하면 → **전체 사용자의 기록**을 대상으로 조회
- **소유권 검사** (`PUT`/`DELETE /records/{id}`):
  - 기록이 없으면 → 404
  - 기록은 있지만 요청자의 것이 아니고, 요청자가 `admin`도 아니면 → **403 Forbidden**
  - `admin`은 항상 모든 기록에 대해 수정/삭제 가능
- **단건 조회** (`GET /records/{id}`)에서 타인의 기록을 조회하면 → 목록 조회와 일관되게 **404**로 처리 (존재 자체를 숨김)

이 로직은 `storage.py`에 `check_ownership(record, user)` 같은 헬퍼 함수로 구현하고, `main.py`의 각 라우터에서 재사용한다.

---

## 7. API 상세 명세

**공통 헤더**: `X-User-Id` (선택, 기본값 `guest`, 값이 `admin`이면 조회 시 전체 사용자 대상)
**공통 에러 포맷**: FastAPI 기본 형식 사용 — `{"detail": "에러 메시지"}`

### 7.1 `GET /`
간단 화면(HTML) 반환. `static/index.html`을 서빙.

### 7.2 `GET /api`
```json
{ "message": "마이 헬스 로그 API" }
```

### 7.3 `POST /records`
기록 추가. 저장 후 BMI·분류·경고 계산해 응답. **201 Created**

요청 예시:
```json
{
  "date": "2026-07-20",
  "weight": 70.5,
  "height": 175,
  "systolic": 118,
  "diastolic": 76,
  "blood_sugar": 95,
  "steps": 8000,
  "sleep_hours": 7.5,
  "memo": ""
}
```

응답 예시:
```json
{
  "id": 1,
  "user": "guest",
  "date": "2026-07-20",
  "weight": 70.5, "height": 175, "systolic": 118, "diastolic": 76, "blood_sugar": 95,
  "steps": 8000, "sleep_hours": 7.5, "memo": "",
  "bmi": 23.0,
  "bmi_category": "과체중",
  "bp_category": "정상",
  "sugar_category": "정상",
  "warnings": []
}
```

### 7.4 `GET /records`
전체 기록 조회 (본인 것만, `admin`은 전체)
```json
{ "count": 3, "records": [ { "...RecordOut": "..." } ] }
```

### 7.5 `GET /records/{id}`
단건 조회. 없거나 타인 기록이면 **404**.

### 7.6 `PUT /records/{id}`
전체 필드 필수 (POST와 동일 바디). 없으면 404, 타인 기록이면 403(`admin` 예외). 응답은 갱신된 `RecordOut`.

### 7.7 `DELETE /records/{id}`
없으면 404, 타인 기록이면 403(`admin` 예외).
```json
{ "message": "삭제되었습니다", "deleted_id": 3 }
```

### 7.8 `GET /search?start=&end=`
- `start`, `end` 둘 다 선택
- 둘 다 없으면 전체, 하나만 있으면 편도 범위, `start > end`면 **422**
- 본인 기록만 대상 (`admin`은 전체)
```json
{ "count": 2, "records": [ { "...RecordOut": "..." } ] }
```

### 7.9 `GET /stats`
본인 기록만 대상 (`admin`은 전체). **기록이 0건이면 에러 대신 `0`/`null`로 응답.**
```json
{
  "count": 5,
  "avg_weight": 69.8, "avg_bmi": 22.9,
  "avg_systolic": 119.2, "avg_diastolic": 77.4, "avg_blood_sugar": 94.6,
  "bmi_category_counts": { "저체중": 0, "정상": 3, "과체중": 1, "비만": 1 },
  "bp_category_counts": { "정상": 4, "주의": 1, "고혈압": 0 },
  "sugar_category_counts": { "정상": 4, "공복혈당장애": 1, "당뇨 의심": 0 }
}
```
0건일 때: `"count": 0, "avg_weight": null, ...` 형태로 반환.

---

## 8. 프론트엔드(간단 화면) 명세

- **파일**: `static/index.html` 단일 파일, 프레임워크 없이 순수 HTML + JS
- **API 호출**: `fetch()`로 백엔드 API 호출 (같은 출처이므로 CORS 설정 불필요)
- **라우팅**: `GET /`가 이 파일을 반환하도록 `main.py`에서 처리. 기존 API 상태 메시지는 `/api`로 이동.
- **기능 범위**:
  - 기록 입력 폼 (date, weight, height, systolic, diastolic, blood_sugar, steps, sleep_hours, memo)
  - 목록 조회 (제출 시 `X-User-Id` 헤더 포함 — 간단한 입력창으로 사용자 전환 가능하게)
  - 기록 수정/삭제 (목록의 각 행에 [수정]/[삭제] 버튼, 입력 폼을 수정 모드로 재사용) — 더 이상 선택 항목이 아닌 필수 범위. 상세 설계는 16장 참고.

---

## 9. 에러 처리 정책

| 상황 | 상태 코드 | 비고 |
|---|---|---|
| 요청 바디 검증 실패 (Pydantic) | 422 | FastAPI 기본 처리 |
| date 형식 오류 | 422 | 커스텀 validator |
| `/search` start > end | 422 | 커스텀 체크 |
| 존재하지 않는 id 조회/수정/삭제 | 404 | |
| 타인 기록 조회 (`GET /records/{id}`) | 404 | 존재 자체를 숨김 |
| 타인 기록 수정/삭제 (`PUT`/`DELETE`) | 403 | 존재는 알되 권한 없음 명시 |
| 서버 내부 오류 | 500 | 발생하지 않도록 방어적 코딩 (전역 예외 처리 고려) |

에러 응답은 모두 FastAPI 기본 포맷을 따른다: `{"detail": "..."}`

---

## 10. 테스트 전략

pytest + httpx(TestClient)로 `tests/test_records.py`에 아래 시나리오를 커버한다.

- [ ] POST /records → 201, 응답에 bmi/분류/warnings 포함 확인
- [ ] GET /records → 목록 및 count 확인
- [ ] GET /records/{id} → 정상 조회 / 없는 id → 404
- [ ] PUT /records/{id} → 정상 수정 / 없는 id → 404
- [ ] DELETE /records/{id} → 정상 삭제 및 메시지 확인
- [ ] GET /search → start/end 조합별 동작 확인 (없음/편도/양쪽/start>end)
- [ ] GET /stats → 정상 케이스 및 0건 케이스(null 응답) 확인
- [ ] 다른 `X-User-Id`로 요청 시 본인 기록만 보이는지 확인
- [ ] `admin` 헤더로 전체 조회되는지 확인
- [ ] 타인 기록 PUT/DELETE 시도 → 403 확인
- [ ] date 형식 오류 → 422 확인

---

## 11. Day별 개발 로드맵 (4일 × 4시간)

### Day 1 — 세팅 + 데이터 계층 + 기본 CRUD
- venv 생성, FastAPI/uvicorn/pytest/httpx 설치
- 폴더 구조(`models.py`/`logic.py`/`storage.py`/`main.py`/`static/`/`tests/`) 뼈대 작성
- Pydantic 모델 정의 (`RecordIn`, `RecordOut`)
- `storage.py`: `data.json` 읽기/쓰기, `next_id` 관리 함수
- `X-User-Id` 헤더 파싱 의존성 함수 (FastAPI `Depends`)
- `POST /records`, `GET /records`, `GET /records/{id}` 구현 (계산 로직 없이 저장·조회 + user 필터링 + 404 처리)
- GitHub 저장소 생성(Public), 첫 커밋 push

### Day 2 — 헬스케어 로직 + PUT/DELETE + 권한
- `logic.py`: BMI 계산, BMI/혈압/혈당 분류, warnings 생성 함수 (동적 계산)
- POST/GET 응답에 계산 결과 연결
- `PUT /records/{id}` (전체 필드), `DELETE /records/{id}` (메시지 응답) 구현
- 타인 기록 접근 시 403 처리 로직 추가
- pytest 기본 테스트 작성 시작 (CRUD 기본 케이스)
- 커밋

### Day 3 — 검색 · 통계 · 간단 화면
- `GET /search` (start/end 옵션 처리 + 422 검증)
- `GET /stats` (확장형 통계, 0건 시 null 처리)
- `static/index.html` (입력 폼 + 목록 조회) 작성
- 라우팅 정리: `GET /` → 화면, `GET /api` → 상태 메시지
- pytest 테스트 추가 (search/stats/권한 케이스)
- 커밋

### Day 4 — Docker · 문서화 · 마무리
- `requirements.txt`, `Dockerfile`, `.dockerignore`, `.gitignore` 작성
- `docker build` / `docker run` 테스트, `/docs` 접속 확인
- README.md 작성 (프로젝트 소개, 엔드포인트 표, 실행 방법, 기술 스택)
- 최종 체크리스트 점검 (아래 13장) 후 최종 push
- **시간이 남으면** → 12장 우선순위 1번(목표 관리)부터 착수

---

## 12. 추가 도전 과제 우선순위 (시간 남을 때)

| 순위 | 기능 | 개요 |
|---|---|---|
| 1 | 목표 관리 | 목표 체중/혈압을 저장하고 달성률 반환 |
| 2 | 주간 리포트 | 최근 7일 평균과 지난주 대비 변화 — `GET /reports/weekly` 별도 엔드포인트로 구현 |
| 3 | 걸음 수 등급 | 하루 걸음 수로 활동량 등급(부족/적정/우수) 분류 |
| 4 | 수면 분석 | 평균 수면 시간과 권장 수면 비교 |

(사용자 구분·간단 화면은 구조적 이유로 이미 필수 범위에 포함되어 위 목록에서 제외됨)

---

## 13. 제출 체크리스트

- [ ] 서버가 오류 없이 실행되고 `/docs`가 열린다
- [ ] `/` 접속 시 간단 화면이 정상 렌더링된다
- [ ] 9개 엔드포인트(화면 포함)가 모두 동작한다
- [ ] BMI·분류·경고·통계 결과가 기준표대로 올바르다
- [ ] `X-User-Id`별 데이터 분리 및 `admin` 전체조회가 정상 동작한다
- [ ] 타인 기록 접근 시 404/403이 올바르게 반환된다
- [ ] 서버를 재시작해도 데이터가 유지된다 (`data.json`)
- [ ] pytest 테스트가 모두 통과한다
- [ ] `docker build` · `docker run`이 성공한다
- [ ] 저장소에 `venv`·`data.json`이 올라가지 않았다 (`.gitignore` 확인)
- [ ] README가 필수 항목(소개/기능목록/실행법/기술스택)을 모두 포함한다
- [ ] 최종 코드가 push됐고, 저장소가 Public이다

---

## 14. Claude Code 작업 지침

Claude Code와 작업할 때 아래 원칙을 따른다.

1. **이 문서를 기준으로 작업한다.** 모호한 부분이 생기면 이 문서의 해당 섹션(예: "6장 권한 정책 참고")을 먼저 확인하고, 그래도 불명확하면 새로 결정하지 말고 사용자에게 질문한다.
2. **Day 단위 또는 기능 단위로 나눠서 진행한다.** 한 번에 전체를 요청하지 않고, 11장의 Day별 로드맵을 기준으로 "Day 1 작업만 구현해줘" 식으로 단계적으로 요청한다.
3. **커밋 단위**: 기능 하나(예: POST /records 구현, PUT 구현, 화면 구현)가 끝날 때마다 커밋 메시지를 남기고 커밋한다.
4. **코드 스타일**: 함수/변수에 타입 힌트 사용, 계산 로직(`logic.py`)과 저장 로직(`storage.py`)은 라우터(`main.py`)와 분리 유지.
5. **테스트 우선 확인**: 기능 구현 후 해당 pytest 케이스도 함께 작성/실행해서 통과 여부 확인.
6. **본인 작성 원칙**: 참고 자료를 활용했다면 README에 명시.
7. 이 문서를 프로젝트 루트에 `PROJECT_PLAN.md`로 두고, 필요 시 핵심 규칙(폴더 구조, 데이터 모델, 권한 정책)만 요약한 `CLAUDE.md`를 별도로 만들어 Claude Code가 매 세션 자동 참고하게 하는 것을 권장.

---

> **추가 기능 (2026-07-21 추가)**: Day 1~4 완료 후 아래 두 기능을 추가로 확정했다. 15장은 개발 편의 도구, 16장은 8장 화면 명세의 필수 확장 기능이다.

## 15. 개발 편의 도구 — 테스트 데이터 자동 생성 (`seed_data.py`)

**목적**: 화면·통계·분류 기능 확인용 기록을 실행 중인 서버에 실제 API 요청(`POST /records`)으로 자동 생성한다. `data.json`에 직접 쓰지 않고 API를 호출해 Pydantic 검증·BMI 계산·권한 로직까지 실제 플로우로 검증한다.

**파일 위치**: `scripts/seed_data.py` (운영 코드·Docker 이미지와 무관하므로 `.dockerignore`에 `scripts/` 추가)

**핵심 원칙**: 완전 랜덤이 아닌 **사용자별 기준값(baseline) + 하루 단위 소폭 랜덤워크 + 전체 구간 상한(cap)** 방식으로 값을 생성해 "일주일 새 20kg 증가" 같은 비현실적인 급변을 막는다. weight/systolic/diastolic/blood_sugar는 baseline 대비 허용 범위와 절대 물리 한계(예: weight 40~150kg)를 함께 둔다. steps/sleep_hours는 매일 정해진 범위(2,000~15,000 / 4.0~9.5) 내 랜덤, height는 고정값이다.

**사용자 프로필**: 분류 기준(정상/주의/위험군)을 골고루 테스트하도록 baseline이 다른 4명(alice=정상, bob=과체중·주의혈압, carol=고혈압 위험군, dave=당뇨 의심 위험군)을 미리 정의한다. `admin`은 데이터를 소유하지 않고 전체 조회 검증용으로만 쓴다.

**실행**: `python scripts/seed_data.py --host <서버 주소> --days <사용자당 생성 일수> --seed <재현용 랜덤 시드>`

**주의사항**:
- 서버(uvicorn)가 실행 중이어야 동작 (실제 API 호출 방식)
- 실행 전 `data.json` 초기화 권장 (중복 누적 방지)
- `requests`/`httpx`는 `requirements-dev.txt`에만 추가하고, 운영용 `requirements.txt`에는 넣지 않는다

---

## 16. 프론트엔드 — 수정/삭제 기능

8장 화면에 기록 수정·삭제를 추가한다(필수 범위). 새 폼을 따로 만들지 않고 **기존 입력 폼을 수정 모드로 재사용**한다.

- 목록의 각 행에 [수정]/[삭제] 버튼 추가
- 폼 상단에 현재 모드 표시("새 기록 추가" ↔ "기록 수정 중 (#id)"), 수정 모드에서는 제출 버튼 라벨을 "저장"으로 바꾸고 [취소] 버튼 노출
- 수정 모드 진입 시 폼에 기존 값을 채우고, 제출 시 `PUT /records/{id}` 호출 (생성 모드는 기존대로 `POST /records`)
- 삭제는 `confirm()`으로 실수 방지 후 `DELETE /records/{id}` 호출

**에러 처리** (9장 정책과 동일하게 화면에 반영):

| 상황 | 상태코드 | 화면 처리 |
|---|---|---|
| 없는 기록 수정/삭제 | 404 | "기록을 찾을 수 없어요" |
| 타인 기록 수정/삭제 | 403 | "본인 기록만 수정/삭제할 수 있어요" |
| 입력값 검증 실패 | 422 | 문제 필드를 폼 위에 표시 |

에러는 폼 위 고정 배너로 표시하고, 성공 시 자동으로 사라지게 처리한다.
