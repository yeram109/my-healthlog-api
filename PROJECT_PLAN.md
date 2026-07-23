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
| ORM / 데이터 검증 | SQLModel (Pydantic + SQLAlchemy 통합) — 17장 참고 |
| 데이터 저장 | SQLite (`health_log.db`) |
| 인증 | JWT(`python-jose`) + bcrypt 해싱(`passlib`), `OAuth2PasswordBearer` — 18장 참고 |
| 가상환경 | venv |
| 테스트 | pytest + httpx (FastAPI TestClient, 인메모리 SQLite) |
| 배포 | Docker (Dockerfile + .dockerignore) |
| 프론트엔드 | 순수 HTML + JS (프레임워크·빌드 도구 없음, fetch로 API 호출) |

**로컬 셋업 예시**
```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install fastapi uvicorn sqlmodel passlib[bcrypt] python-jose[cryptography] python-multipart pytest httpx
export SECRET_KEY=<임의의 긴 랜덤 문자열>   # 없으면 서버가 시작 시점에 바로 실패한다 (18장 참고)
uvicorn main:app --reload
# http://127.0.0.1:8000/docs 에서 API 테스트 (Authorize 버튼으로 토큰 인증)
# http://127.0.0.1:8000/ 에서 화면 확인 (첫 화면은 로그인/회원가입)
```

---

## 3. 프로젝트 폴더 구조

```
health-log-api/
├── main.py             # FastAPI 앱 생성, 라우터 정의, 정적 파일 마운트
├── auth.py              # 비밀번호 해싱, JWT 발급/검증, get_current_user 의존성 (18장 참고)
├── models.py              # SQLModel (User/Record/Goal 테이블 + Create/Read 스키마) — 17·18장 참고
├── db.py                   # SQLite 엔진, init_db(), get_session() 의존성 (17장 참고)
├── logic.py                  # BMI 계산 · 분류 · 경고 생성 함수
├── storage.py                  # 세션 기반 CRUD, 소유권 체크, 목표 저장
├── static/
│   └── index.html                # 화면 (로그인/회원가입 + 입력 폼 + 목록 조회 + 수정/삭제)
├── scripts/
│   ├── seed_data.py                 # 개발용 테스트 데이터 자동 생성 스크립트 (15·18장 참고)
│   ├── create_admin.py                # 최초 관리자 계정 생성 CLI (18장 참고)
│   └── migrate_json_to_db.py            # (레거시) data.json -> SQLite 1회 이관 스크립트 (17장 참고)
├── tests/
│   ├── conftest.py                       # 인메모리 SQLite + client/auth_headers fixture
│   └── test_records.py                     # pytest 자동 테스트
├── health_log.db                            # 런타임 생성 (.gitignore 처리)
├── requirements.txt
├── requirements-dev.txt                       # 개발 도구 전용 의존성 (예: requests/httpx for seed_data.py)
├── .env.example                                # SECRET_KEY 환경변수 이름 안내
├── Dockerfile
├── .dockerignore                                 # scripts/ 포함, 이미지에서 제외
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
| user_id | int | 소유자 FK (`user.id`) | 응답에 자동 포함 (로그인한 사용자의 id, 18장 참고) |

응답에는 위 필드 + 서버가 **동적 계산**한 `id`, `bmi`, `bmi_category`, `bp_category`, `sugar_category`, `warnings`, `steps_grade`, `sleep_category`가 포함된다.

### 4.2 SQLModel 정의 (개념 정의, 17·18장 전환 이후 기준)

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = False

class RecordBase(SQLModel):
    date: str          # YYYY-MM-DD 형식 검증 (validator 또는 date 타입 활용)
    weight: float
    height: float
    systolic: int
    diastolic: int
    blood_sugar: int
    steps: int = 0
    sleep_hours: float = 0.0
    memo: str = ""

class Record(RecordBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

class RecordRead(RecordBase):
    id: int
    user_id: int
    bmi: float
    bmi_category: str
    bp_category: str
    sugar_category: str
    warnings: list[str]
    steps_grade: str
    sleep_category: str
```

### 4.3 SQLite 저장 구조

`data.json` 단일 파일 대신 SQLite(`health_log.db`)에 `user`, `record`, `goal` 세 테이블로 저장한다. 전환 배경과 절차는 17장(저장소), 18장(인증) 참고.

**중요 원칙**:
- `id`는 DB의 autoincrement 기본키로 관리한다 (파일 기반 시절의 `next_id` 카운터는 더 이상 불필요).
- `bmi` / `bmi_category` / `bp_category` / `sugar_category` / `warnings` / `steps_grade` / `sleep_category`는 **DB에 저장하지 않는다.** 매 요청마다 원본 값(weight, height, systolic, diastolic, blood_sugar, steps, sleep_hours)으로부터 `logic.py`에서 동적으로 계산해 응답에 포함한다. (분류 기준이 바뀌어도 기존 데이터가 낡은 값으로 남지 않도록)

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

> 최초에는 `X-User-Id` 헤더 자기신고 방식이었으나, JWT 로그인 기반으로 전환했다. 인증 자체의 구현 상세(토큰 발급/검증, 비밀번호 해싱)는 18장 참고.

- **식별 방법**: 회원가입(`/auth/signup`) 후 로그인(`/auth/login`)해 JWT를 발급받고, 이후 모든 요청에 `Authorization: Bearer <token>` 헤더를 사용한다. 토큰이 없거나 유효하지 않으면 **401**.
- **관리자 권한**: 문자열 매직값(`admin`)이 아니라 `User.is_admin` 필드로 관리한다. 회원가입으로는 `is_admin`을 설정할 수 없고, `scripts/create_admin.py` CLI로만 부여한다.
- **조회 범위**:
  - `GET /records`, `GET /search`, `GET /stats` → 기본적으로 **본인 기록만** 대상
  - `is_admin` 계정으로 요청하면 → **전체 사용자의 기록**을 대상으로 조회
- **소유권 검사** (`PUT`/`DELETE /records/{id}`):
  - 기록이 없으면 → 404
  - 기록은 있지만 요청자의 것이 아니고, 요청자가 `is_admin`도 아니면 → **403 Forbidden**
  - `is_admin` 계정은 항상 모든 기록에 대해 수정/삭제 가능
- **단건 조회** (`GET /records/{id}`)에서 타인의 기록을 조회하면 → 목록 조회와 일관되게 **404**로 처리 (존재 자체를 숨김)

이 로직은 `storage.py`에 `check_ownership(record, user)` 같은 헬퍼 함수로 구현하고, `main.py`의 각 라우터에서 재사용한다. `user`는 이제 문자열이 아니라 `auth.get_current_user` 의존성이 반환하는 `User` 객체다.

---

## 7. API 상세 명세

**공통 헤더**: `Authorization: Bearer <token>` (`/`, `/api`, `/auth/signup`, `/auth/login` 제외 전부 필수, 없거나 유효하지 않으면 401). `is_admin` 계정이면 조회 시 전체 사용자 대상.
**공통 에러 포맷**: FastAPI 기본 형식 사용 — `{"detail": "에러 메시지"}`

### 7.1 `GET /`
간단 화면(HTML) 반환. `static/index.html`을 서빙.

### 7.2 `GET /api`
```json
{ "message": "마이 헬스 로그 API" }
```

### 7.2a `POST /auth/signup`, `POST /auth/login`

인증 관련 엔드포인트 상세는 18장 참고.

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
  "user_id": 1,
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
전체 기록 조회 (본인 것만, `is_admin` 계정은 전체)
```json
{ "count": 3, "records": [ { "...RecordOut": "..." } ] }
```

### 7.5 `GET /records/{id}`
단건 조회. 없거나 타인 기록이면 **404**.

### 7.6 `PUT /records/{id}`
전체 필드 필수 (POST와 동일 바디). 없으면 404, 타인 기록이면 403(`is_admin` 예외). 응답은 갱신된 `RecordRead`.

### 7.7 `DELETE /records/{id}`
없으면 404, 타인 기록이면 403(`is_admin` 예외).
```json
{ "message": "삭제되었습니다", "deleted_id": 3 }
```

### 7.8 `GET /search?start=&end=`
- `start`, `end` 둘 다 선택
- 둘 다 없으면 전체, 하나만 있으면 편도 범위, `start > end`면 **422**
- 본인 기록만 대상 (`is_admin` 계정은 전체)
```json
{ "count": 2, "records": [ { "...RecordOut": "..." } ] }
```

### 7.9 `GET /stats`
본인 기록만 대상 (`is_admin` 계정은 전체). **기록이 0건이면 에러 대신 `0`/`null`로 응답.**
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

- **파일**: `static/index.html` + `static/css/style.css` + `static/js/app.js` (19장 전환 이후, 프레임워크 없이 순수 HTML/CSS/JS + Chart.js CDN)
- **API 호출**: `fetch()`로 백엔드 API 호출 (같은 출처이므로 CORS 설정 불필요)
- **라우팅**: `GET /`가 `index.html`을 반환하도록 `main.py`에서 처리. 기존 API 상태 메시지는 `/api`로 이동.
- **기능 범위**:
  - 로그인/회원가입 (JWT 토큰을 `localStorage`에 저장, 이후 모든 요청에 `Authorization: Bearer` 부착) — 18장 참고
  - 대시보드/기록/목표/리포트 4개 탭 — 19장 참고
  - 기록 입력 폼 (date, weight, height, systolic, diastolic, blood_sugar, steps, sleep_hours, memo)
  - 기록 수정/삭제 (목록의 각 행에 [수정]/[삭제] 버튼, 입력 폼을 수정 모드로 재사용) — 더 이상 선택 항목이 아닌 필수 범위. 기본 상호작용 설계는 16장, 최신 마크업은 19장 참고.

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
- [ ] 다른 사용자로 로그인해 요청 시 본인 기록만 보이는지 확인
- [ ] `is_admin` 계정으로 전체 조회되는지 확인
- [ ] 타인 기록 PUT/DELETE 시도 → 403 확인
- [ ] date 형식 오류 → 422 확인
- [ ] 회원가입 중복 username → 400, 로그인 실패 → 401, 토큰 없이/잘못된 토큰으로 접근 → 401 확인 (18장 참고)

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
| 1 | 목표 관리 | 목표 체중/혈압을 저장하고 달성률 반환 — 12.1 참고 |
| 2 | 주간 리포트 | 최근 7일 평균과 지난주 대비 변화 — `GET /reports/weekly` 별도 엔드포인트로 구현, 12.2 참고 |
| 3 | 걸음 수 등급 | 하루 걸음 수로 활동량 등급(부족/적정/우수) 분류 — 12.3 참고 |
| 4 | 수면 분석 | 평균 수면 시간과 권장 수면 비교 — 12.4 참고 |

(사용자 구분·간단 화면은 구조적 이유로 이미 필수 범위에 포함되어 위 목록에서 제외됨)

### 12.1 목표 관리

**데이터**: `data.json`에 `goals` 섹션을 신설해 사용자당 목표 1개만 유지한다. 예: `{"alice": {"target_weight": 65, "target_systolic": 120, "target_diastolic": 80}}`. `storage.py`에 `get_goal(user)` / `set_goal(user, goal)` 헬퍼를 추가한다.

**엔드포인트**: `PUT /goal`(목표 설정/수정), `GET /goal`(목표 + 달성률 조회). 목표가 없는 상태에서 `GET /goal`을 호출하면 `{"goal": null}`로 응답한다(9장 정책과 통일, 에러 대신 null).

**달성률 계산**(`logic.py`): 목표 설정 시점 이후 첫 기록을 시작값으로 삼아 `(시작값 - 현재값) / (시작값 - 목표값) * 100`을 0~100%로 clamp한다. 시작값과 목표값이 같으면(이미 목표 달성 상태) 100%로 처리해 0으로 나누는 경우를 방지한다.

### 12.2 주간 리포트

**엔드포인트**: `GET /reports/weekly` 신설.

**로직**: `storage.get_records(user)`로 가져온 기록을 오늘 기준 최근 7일과 그 이전 7일(8~14일 전)로 나눠 각각 weight/bmi/systolic/diastolic/blood_sugar/**steps/sleep_hours**(19장 리포트 뷰를 위해 추가) 평균을 계산하고 두 구간의 증감(delta)을 함께 반환한다. 날짜 범위를 나누는 방식은 `/search`의 필터링 로직을 재사용한다. 평균 계산 로직은 `/stats`와 중복되므로 `logic.py`에 공용 함수로 뽑아 재사용한다.

**기록 부족 처리**: 두 구간 중 하나라도 기록이 0건이면 `/stats`처럼 해당 구간 값을 `null`로 응답한다.

### 12.3 걸음 수 등급

**분류 기준(기본값)**:

| 구간 | 등급 |
|---|---|
| 5,000 미만 | 부족 |
| 5,000 ~ 9,999 | 적정 |
| 10,000 이상 | 우수 |

**구현**: `logic.py`에 `classify_steps(steps)` 추가, `enrich_record()`가 반환하는 dict에 `steps_grade` 필드를 포함시킨다. `models.py`의 `RecordOut`에도 `steps_grade: str` 필드를 추가하고, 관련 pytest 케이스를 BMI/혈압/혈당 분류 테스트와 같은 패턴으로 추가한다.

### 12.4 수면 분석

**분류 기준(기본값, 성인 권장 수면시간 7~9시간 기준)**:

| 구간 | 분류 |
|---|---|
| 7시간 미만 | 부족 |
| 7 ~ 9시간 | 적정 |
| 9시간 초과 | 과다 |

**구현**: 걸음 수 등급과 대칭되도록 기록 단위로 처리한다. `logic.py`에 `classify_sleep(sleep_hours)` 추가, `enrich_record()`와 `RecordOut`에 `sleep_category` 필드를 추가한다.

---

## 13. 제출 체크리스트

- [ ] 서버가 오류 없이 실행되고 `/docs`가 열린다
- [ ] `/` 접속 시 간단 화면이 정상 렌더링된다
- [ ] 15개 엔드포인트(화면 포함, `/auth/signup`·`/auth/login`·`/auth/me`(DELETE)·`/goal`·`/reports/weekly` 포함)가 모두 동작한다
- [ ] BMI·분류·경고·통계 결과가 기준표대로 올바르다
- [ ] 로그인한 사용자별 데이터 분리 및 `is_admin` 전체조회가 정상 동작한다
- [ ] 토큰 없이/잘못된 토큰으로 접근 시 401이 반환된다
- [ ] 타인 기록 접근 시 404/403이 올바르게 반환된다
- [ ] 서버를 재시작해도 데이터가 유지된다 (`health_log.db`)
- [ ] `SECRET_KEY` 없이 실행하면 시작 시점에 바로 실패한다
- [ ] pytest 테스트가 모두 통과한다
- [ ] `docker build` · `docker run`이 성공한다 (`-e SECRET_KEY=...` 필요)
- [ ] 저장소에 `venv`·`health_log.db`·`.env`가 올라가지 않았다 (`.gitignore` 확인)
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

---

## 17. 저장소 전환 — JSON 파일 → SQLite + SQLModel

**목적**: `data.json` 파일 기반 저장은 동시 요청 시 read-modify-write 과정에서 데이터가 유실될 위험이 있고, 인증 기능을 위한 `users` 테이블 같은 확장 여지도 없다. SQLite + SQLModel로 전환해 두 문제를 해결한다.

**기술 선택**: ORM은 SQLModel(Pydantic + SQLAlchemy 통합, 기존 `models.py`와 중복을 최소화). DB는 SQLite(`health_log.db`, 프로젝트 루트, `.gitignore` 처리). 마이그레이션 도구(Alembic)는 쓰지 않고 `SQLModel.metadata.create_all()`로 스키마를 생성하며, 스키마가 바뀌면 DB를 재생성하는 것을 원칙으로 한다.

**변경된 파일**: `models.py`(SQLModel로 재작성 — 4.2 참고), `db.py`(신규, 엔진·`init_db()`·`get_session()`), `storage.py`(파일 I/O를 세션 기반 CRUD로 전면 교체, `next_id` 카운터 로직 삭제), `main.py`(각 라우터에 `Depends(get_session)` 주입, `lifespan`에서 `init_db()` 호출), `scripts/migrate_json_to_db.py`(신규, 기존 `data.json` 1회 이관), `tests/conftest.py`(신규, 인메모리 SQLite로 `get_session`을 오버라이드하는 `client` fixture).

**유지된 것**: `logic.py`의 BMI/걸음수/수면 계산·분류·경고 생성 로직은 그대로다. 계산값은 여전히 DB에 저장하지 않고 응답 시점에 동적으로 계산한다(4.3 참고). 소유권 검사(`check_ownership`)의 원리도 동일하며, 비교 대상만 dict에서 `Record` 객체 속성으로 바뀌었다.

**개선된 부분**: `/search`는 파이썬 필터링 대신 SQL `WHERE date BETWEEN` 쿼리(`storage.search_records`)로 대체했다. 동시 쓰기 요청은 SQLite 트랜잭션으로 직렬화되어 파일 기반 저장의 데이터 유실 위험이 사라졌다.

**이관 절차**: 서버를 끈 상태에서 `python scripts/migrate_json_to_db.py`를 1회 실행한다. `data.json`의 `records`뿐 아니라 `goals`도 함께 이관한다 — 같은 파일에 있던 데이터라 하나만 옮기면 목표만 파일에 남는 어중간한 상태가 되기 때문에, `Goal(table=True)` 모델을 추가해 함께 이관하도록 범위를 넓혔다.

**Docker**: 컨테이너를 재생성해도 데이터를 유지하려면 `health_log.db`를 호스트에 볼륨 마운트한다: `docker run -d -p 8000:8000 -v $(pwd)/health_log.db:/app/health_log.db my-healthlog-api`

---

## 18. JWT 인증 도입

**목적**: `X-User-Id` 헤더 자기신고 방식은 아무 값이나 넣으면 그 사용자로 행세할 수 있어 인증이 아니었다. 회원가입/로그인 기반 JWT로 전환하고, 관리자 권한도 문자열 매직값(`admin`) 대신 DB의 `is_admin` 필드로 관리한다.

**기술 선택**: 비밀번호 해싱은 `passlib[bcrypt]`, 토큰은 `python-jose[cryptography]`, 로그인 폼 파싱은 `python-multipart`. FastAPI의 `OAuth2PasswordBearer`를 사용해 `/docs`에 Authorize 버튼이 자동으로 생기게 한다. `bcrypt`는 `passlib 1.7.4`와의 호환성 문제(`bcrypt>=4.1`에서 버전 감지 오류) 때문에 `bcrypt==4.0.1`로 고정한다.

**변경된 파일**:
- `models.py` — `User`(id/username/hashed_password/is_admin/is_active) 테이블 추가, `UserCreate`(password만 받고 is_admin·is_active는 절대 받지 않음), `UserRead`. `Record.user`(str) → `Record.user_id`(FK), `Goal.user`(str, PK) → `Goal.user_id`(FK, PK)로 변경
- `auth.py`(신규) — `hash_password`/`verify_password`/`create_access_token`/`decode_access_token`, 토큰→username→DB 조회 후 `User`를 반환하는 `get_current_user` 의존성. `SECRET_KEY`는 환경변수에서만 읽고 하드코딩된 기본값을 두지 않는다 — 없으면 앱 시작 시점(`lifespan`)에 바로 실패한다.
- `main.py` — `POST /auth/signup`(중복 username 400), `POST /auth/login`(`OAuth2PasswordRequestForm`, 실패 시 401, 성공 시 `{access_token, token_type}`) 추가. 기존 모든 라우터의 `X-User-Id` 기반 의존성을 `Depends(auth.get_current_user)`로 교체, `guest` 기본값 로직 삭제
- `storage.py` — 소유권 검사·필터링을 `user.id`/`user.is_admin` 기준으로 수정 (매개변수가 문자열 `user`에서 `User` 객체로 바뀜)
- `scripts/create_admin.py`(신규) — 최초 관리자 계정 생성 CLI (`--username --password`, DB에 직접 `is_admin=True` row 생성). 회원가입 API로는 관리자를 만들 수 없어 이 스크립트가 유일한 경로다.
- `scripts/seed_data.py`(수정) — 사용자별로 `/auth/signup` → `/auth/login`을 먼저 호출해 토큰을 발급받고, 이후 `Authorization: Bearer` 헤더로 `/records`를 호출하도록 변경. 비밀번호는 스크립트 내 고정값(`SEED_PASSWORD`) 사용
- `tests/conftest.py` — 사용자 생성 + 토큰 발급을 한 번에 처리하는 `auth_headers(username, is_admin=False)` fixture 추가. 기존 38개 테스트를 전부 `X-User-Id` 헤더 방식에서 `auth_headers`로 전환하고, 회원가입/로그인/인증 실패/회원탈퇴 케이스 12건을 신규 추가(총 50건)
- `static/index.html` — 로그인/회원가입 폼, `localStorage`에 토큰 저장, 이후 모든 fetch에 `Authorization: Bearer` 부착. `/auth/login`만 `application/x-www-form-urlencoded`로 전송(`OAuth2PasswordRequestForm` 규격), 나머지는 기존처럼 JSON. 응답이 401이면 토큰을 지우고 로그인 화면으로 전환
- `requirements.txt` — `passlib[bcrypt]`, `bcrypt==4.0.1`, `python-jose[cryptography]`, `python-multipart` 추가
- `.env.example`(신규) — `SECRET_KEY=` 키 이름만 포함, 실제 값은 미포함

**유지된 것**: `logic.py`의 계산 로직과, 계산값을 저장하지 않고 응답 시점에 동적으로 계산하는 원칙은 그대로다(4.3 참고).

**기존 시드 데이터 처리**: 문자열 유저명(`user: str`) 기반이던 기존 `health_log.db`는 새 FK 스키마(`user_id: int`)와 호환되지 않아 보존 가치가 없다고 판단해, 마이그레이션 스크립트 없이 DB를 비우고 `create_admin.py` + 수정된 `seed_data.py`로 재시딩했다.

**주의사항**:
- `SECRET_KEY`가 없으면 서버가 첫 요청이 아니라 **시작 시점**에 바로 실패하도록 `lifespan`에서 확인한다 (운영 중 첫 로그인 시도에서야 500이 나는 상황을 방지).
- Docker로 실행할 때는 반드시 `-e SECRET_KEY=<값>`을 전달해야 한다.

### 18.1 로그아웃 / 회원탈퇴

**로그아웃**: JWT는 stateless라 서버가 세션을 들고 있지 않으므로, 별도 API 없이 화면에서 `localStorage`의 토큰을 지우는 것으로 처리한다(이미 구현됨). 서버 측에서 토큰을 강제로 무효화하려면 블랙리스트 테이블과 매 요청마다 조회하는 오버헤드가 필요해, 현재 규모에서는 채택하지 않는다.

**회원탈퇴**: `User`에 `is_active: bool = True` 필드를 추가하고, `DELETE /auth/me`는 계정을 **비활성화**만 한다(하드 삭제 아님) — 본인 기록/목표는 보존한다.

- `auth.get_current_user`가 `user.is_active`를 함께 확인해서, 탈퇴 직후 아직 만료되지 않은 기존 토큰도 다음 요청부터 즉시 401 처리되게 한다.
- `POST /auth/login`도 비밀번호가 맞아도 `is_active=False`면 403(`"탈퇴한 계정입니다"`)으로 막는다.
- `static/index.html`에 "회원탈퇴" 버튼 추가, `confirm()` 확인 후 `DELETE /auth/me` 호출하고 로그아웃과 동일하게 처리한다.

**스키마 변경 주의**: `is_active` 컬럼 추가는 기존 `health_log.db`의 `user` 테이블에는 반영되지 않는다(`SQLModel.metadata.create_all()`은 없는 테이블만 생성하고 기존 테이블의 컬럼은 바꾸지 않음). 17장의 "스키마가 바뀌면 DB를 재생성" 원칙에 따라 DB를 비우고 `create_admin.py` + `seed_data.py`로 재시딩했다.

---

## 19. 프론트엔드 고도화 — 대시보드/차트/다중 화면

**목적**: 단일 입력 폼 + 목록이던 화면을 대시보드/기록/목표/리포트 4개 탭으로 확장하고, Chart.js로 추이를 시각화하며, 분류 결과를 색상 배지로 표현한다.

**파일 분리**: 규모가 커져 유지보수를 위해 단일 `index.html`을 3개 파일로 분리했다.
```
static/
├── index.html   (헤더 + 탭 네비 + 4개 뷰 컨테이너 마크업)
├── css/style.css (색상 변수 + 탭/배지/카드/차트/반응형 스타일)
└── js/app.js     (인증 + 탭 전환 + CRUD + Chart.js 렌더링)
```

**차트**: Chart.js CDN(`4.4.1`), `responsive:true`/`maintainAspectRatio:false` + `position:relative`·고정 `height`인 `.chart-wrapper`로 감싼다. 각 `<canvas>`에 `role="img"` + `aria-label`을 붙인다. 2계열(혈압) 차트는 Chart.js 기본 범례를 끄고 커스텀 HTML 범례를 쓴다.

**색상**: 상태 배지(정상=success/주의·과체중·공복혈당장애=warning/고혈압·비만·당뇨의심=danger)는 지정된 팔레트를 그대로 쓴다. 혈압 차트의 수축기/이완기 2계열 색상(`#2a78d6`, `#d97706`)은 `validate_palette.js`로 CVD(색각이상) 구분 가능성을 검증했다(ΔE 27~33, 전부 PASS). 걸음수/수면 등급(부족/적정/우수/과다)의 배지 색은 명세에 없어 BMI/혈압 배지와 같은 규칙(부족·과다=warning, 적정·우수=success)으로 자체적으로 맞춰 확장했다.

**뷰별 구현 요약**:
- **대시보드**: `GET /search?start=<14일전>`으로 최근 14일 조회. KPI 카드는 "최신 기록 vs 그 이전 기록"으로 계산한다(모든 날짜에 기록이 있다는 보장이 없어 "오늘/전일"을 달력 날짜가 아니라 최근 두 기록으로 해석). 체중 라인차트(area fill), 혈압 라인차트(2계열).
- **기록**: 기존 목록/수정/삭제를 bordered row 리스트로 재구성, "새 기록 추가" 버튼으로 폼을 토글. CRUD 후 대시보드·목표·리포트 탭의 lazy-load 캐시를 무효화해 다음 방문 시 재조회한다.
- **목표**: 기존 `PUT`/`GET /goal` 그대로 사용, 응답의 달성률(`*_percent`)을 progress bar 폭으로 직접 매핑.
- **리포트**: `GET /reports/weekly`에 걸음수/수면 평균이 없어서 `logic.calculate_averages()`와 `/stats`·`/reports/weekly` 응답에 `avg_steps`/`avg_sleep_hours`(및 `delta.steps`/`delta.sleep_hours`)를 추가했다(계획엔 없었지만 리포트 뷰 요구사항을 만족하려면 필요했음). 일별 걸음 수 막대그래프는 `GET /search?start=<7일전>`으로 이번 주 데이터만 별도 조회한다.

**탭 전환/lazy load**: `data-tab` 버튼 클릭 시 `.active` 클래스를 토글하고, 탭별 최초 진입 시점에만 API를 호출한다(`tabLoaded` 플래그). 로그인 시 플래그를 초기화하고 대시보드부터 로드한다.

**인증**: 모든 fetch에 기존과 동일하게 `Authorization: Bearer` 헤더를 붙이고, 401이면 로그인 화면으로 돌아간다(기존 로직 그대로 유지, 4개 탭에 공통 적용).

**검증 한계**: 이 세션의 브라우저 자동화 도구가 스크린샷/뷰포트 측정을 정상적으로 수행하지 못해(패널이 컴포지팅되지 않는 도구 자체의 문제), 반응형 레이아웃과 차트의 실제 렌더링 모습은 시각적으로 확인하지 못했다. 데이터 바인딩·탭 전환·CRUD·콘솔 에러 없음은 DOM/네트워크 응답 기준으로 검증했다.

---

## 20. 백엔드 라우터 분리

**목적**: 파일 수가 늘면서 `main.py` 하나가 인증/기록/목표/리포트 4개 도메인의 라우트를 모두 담당하게 되어, 도메인별로 `routers/` 패키지로 분리했다. (파일 개수 자체보다, `main.py`가 여러 관심사를 섞고 있는 것이 실제 유지보수 병목이라고 판단.)

**구조**:
```
routers/
├── auth.py     (APIRouter prefix="/auth")  — /auth/signup, /auth/login, /auth/me
├── records.py  (APIRouter, prefix 없음)     — /records, /records/{id}, /search, /stats
├── goal.py     (APIRouter prefix="/goal")  — PUT/GET /goal
└── reports.py  (APIRouter prefix="/reports") — /reports/weekly
```
`records.py`는 `/search`, `/stats`가 `/records` 하위 경로가 아니라서 공통 prefix 없이 각 라우트에 전체 경로를 직접 지정했다. `main.py`는 `lifespan`(SECRET_KEY 체크 + `init_db`), `FastAPI` 앱 생성, 정적 파일 마운트, 4개 라우터 등록, `GET /`·`GET /api`만 남겼다.

**같이 이동한 것**: `/stats`가 쓰던 `BMI_CATEGORIES`/`BP_CATEGORIES`/`SUGAR_CATEGORIES` 상수와 `/search`가 쓰던 `_validate_date_param` 헬퍼는 둘 다 `routers/records.py`로 옮겼다.

**영향 없음 확인**: `tests/conftest.py`는 `from main import app`만 하고 있어 테스트 코드 변경이 필요 없었다(50개 전체 통과). `Dockerfile`은 `COPY . .` + `uvicorn main:app`이라 그대로 유효하다. `scripts/`도 `main`을 import하지 않아 영향 없다.

**순환 import 없음**: 라우터들은 `auth`/`storage`/`logic`/`db`/`models`만 import하고, 그 모듈들은 `main`이나 `routers`를 import하지 않는다. `routers/auth.py`가 최상위 `auth.py`를 `import auth`로 참조해도, 파이썬은 절대 경로 기준으로 임포트하므로 `routers.auth`(자기 자신)와 `auth`(최상위 모듈)가 이름이 겹치지 않는다.

**검증**: `pytest tests/ -v` 50개 전체 통과. 실제 서버 기동 후 `/openapi.json`으로 11개 경로(14개 라우트) 전부 등록 확인, `/auth/signup`→`/auth/login`→`/records`·`/goal`·`/reports/weekly` curl 호출로 실동작 확인.

**20.1 백엔드 패키지화 (`app/`)**: 라우터 분리에 이어, 루트에 흩어져 있던 6개 모듈(`main.py`/`auth.py`/`models.py`/`db.py`/`logic.py`/`storage.py`)과 `routers/`, `static/`을 `app/` 패키지 하나로 모았다.

```
app/
├── __init__.py
├── main.py / auth.py / models.py / db.py / logic.py / storage.py
├── routers/{auth,records,goal,reports}.py
└── static/{index.html, css/, js/}
```

- 모듈 간 참조는 상대 import(`from . import auth`, `from ..models import User` 등)로 전환.
- `db.py`의 `DB_FILE`은 `Path(__file__).parent`가 `app/`로 바뀌었으므로 `.parent.parent`로 한 단계 더 올려 기존과 동일하게 **프로젝트 루트의 `health_log.db`**를 계속 가리키게 했다(DB 파일은 런타임 데이터라 패키지 안에 두지 않음). 기존 DB 재생성 없이 그대로 재사용 가능함을 확인.
- `main.py`의 `STATIC_DIR = BASE_DIR / "static"`는 `BASE_DIR`이 이제 `app/`이라 `app/static`을 자동으로 가리켜 별도 경로 수정이 필요 없었다.
- `tests/conftest.py`·`tests/test_records.py`, `scripts/create_admin.py`, `scripts/migrate_json_to_db.py`의 import를 `app.xxx` 절대 경로로 갱신(`scripts/seed_data.py`는 HTTP 클라이언트로만 동작해 변경 불필요).
- `Dockerfile`의 `CMD`를 `uvicorn main:app` → `uvicorn app.main:app`으로 변경. `WORKDIR /app`(컨테이너 경로)과 패키지명 `app`이 같은 문자열이라 헷갈리기 쉽지만 서로 다른 네임스페이스라 문제 없음.

**검증**: `pytest tests/ -v` 50개 전체 통과. `python -c "from app.db import DB_FILE"`로 기존 DB 파일 경로 유지 확인. 로컬 `uvicorn app.main:app`으로 `/`, `/static/css/style.css`, `/static/js/app.js`, 회원가입→로그인→`/records` 흐름 curl 검증. `docker build` + `docker run`으로 컨테이너 기동, `/api`·정적 파일 응답까지 확인 후 테스트 이미지/컨테이너는 정리.
