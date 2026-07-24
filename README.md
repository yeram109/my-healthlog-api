# 마이 헬스 로그 API

매일 몸무게·혈압·혈당을 기록하면 BMI 계산, 건강 상태 분류, 경고 메시지를 자동으로 받고, 사용자별로 기록을 분리해서 통계와 히스토리를 확인할 수 있는 API입니다.

> ⚠️ 이 프로젝트의 건강 분류 기준은 학습을 위해 단순화된 값이며, 실제 의학적 진단이 아닙니다.

## 기능 목록

- 건강 기록 CRUD (`POST`/`GET`/`PUT`/`DELETE /records`)
- 기록 시 BMI·걸음 수 등급·수면 분류 자동 계산 및 BMI·혈압·혈당 상태 분류
- 위험 수치 감지 시 조언형 경고 메시지 생성
- JWT 기반 회원가입/로그인/회원탈퇴, 로그인한 사용자별 기록 분리 (`is_admin` 계정은 전체 조회/수정/삭제 가능)
- 기간 검색 (`GET /search`)
- 통계 조회: 평균값, 카테고리별 카운트 (`GET /stats`)
- 목표 관리: 목표 체중/혈압 설정 및 달성률 조회 (`PUT`/`GET /goal`)
- 주간 리포트: 이번주 vs 지난주 평균 비교, 평균 걸음 수/수면 포함 (`GET /reports/weekly`)
- 탭 기반 대시보드 화면 (대시보드/기록/목표/리포트), Chart.js로 체중·혈압·걸음 수 추이 시각화, 분류 결과 색상 배지
- 관리자 전용 대시보드: 전체 사용자 집계 지표, 사용자 관리 화면(가입일/기록 수/건강 상태), 다른 사용자 데이터 조회(`target_user`), 보라색 테마로 시각적 구분
- 개발용 테스트 데이터 자동 생성 스크립트 (`scripts/seed_data.py`)

## 기술 스택

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.12 |
| 프레임워크 | FastAPI + Uvicorn |
| ORM / 데이터 검증 | SQLModel (Pydantic + SQLAlchemy) |
| 데이터 저장 | SQLite (`health_log.db`) |
| 인증 | JWT (python-jose) + bcrypt 해싱(passlib), `OAuth2PasswordBearer` |
| 테스트 | pytest + httpx (FastAPI TestClient, 인메모리 SQLite) |
| 배포 | Docker |
| 프론트엔드 | 순수 HTML + CSS + JS (빌드 도구 없음), Chart.js(CDN) |

## 실행 방법

### 로컬 실행

```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY=<임의의 긴 랜덤 문자열>   # .env.example 참고, 없으면 서버가 시작 시점에 바로 실패한다
uvicorn app.main:app --reload
```

- API 문서: http://127.0.0.1:8000/docs (우측 상단 **Authorize** 버튼으로 토큰 인증)
- 화면: http://127.0.0.1:8000/ (첫 화면은 로그인/회원가입)

### 관리자 계정 생성

일반 회원가입(`/auth/signup`)으로는 `is_admin` 계정을 만들 수 없다. 최초 관리자는 CLI로 생성한다.

```bash
python scripts/create_admin.py --username admin --password <비밀번호>
```

### Docker 실행

```bash
docker build -t my-healthlog-api .
docker run -d -p 8000:8000 -e SECRET_KEY=<임의의 긴 랜덤 문자열> my-healthlog-api
```

컨테이너를 재생성해도 데이터를 유지하려면 `health_log.db`를 호스트에 볼륨으로 마운트한다.

```bash
docker run -d -p 8000:8000 -e SECRET_KEY=<값> -v $(pwd)/health_log.db:/app/health_log.db my-healthlog-api
```

### 테스트 실행

```bash
pytest tests/ -v
```

### 테스트 데이터 자동 생성 (선택)

서버가 실행 중인 상태에서, 사용자 4명(alice/bob/carol/dave)을 자동으로 회원가입·로그인시킨 뒤 실제 API를 호출해 기록을 채워준다(비밀번호는 스크립트 내 `SEED_PASSWORD` 고정값).

```bash
pip install -r requirements-dev.txt
python scripts/seed_data.py --host http://127.0.0.1:8000 --days 30 --seed 42
```

### 기존 data.json 이관 (일회성)

과거 JSON 파일 저장 방식을 쓰던 프로젝트를 SQLite로 옮길 때만 필요하다. 서버가 꺼진 상태에서 실행한다.

```bash
python scripts/migrate_json_to_db.py
```

## API 엔드포인트

**인증**: `/auth/signup`, `/auth/login`, `/`, `/api`를 제외한 모든 엔드포인트는 `Authorization: Bearer <token>` 헤더가 필요하다(없거나 유효하지 않으면 401). `is_admin` 계정은 조회/수정/삭제 시 전체 사용자 대상.

| Method | Path | 설명 |
|---|---|---|
| GET | `/` | 화면(HTML) 반환 |
| GET | `/api` | API 상태 메시지 |
| POST | `/auth/signup` | 회원가입 (username 중복이면 400) |
| POST | `/auth/login` | 로그인 (`x-www-form-urlencoded`), 성공 시 `{access_token, token_type}`. 탈퇴 계정이면 403 |
| DELETE | `/auth/me` | 회원탈퇴 (계정 비활성화, 기록/목표는 보존). 기존 토큰은 즉시 무효화됨 |
| GET | `/auth/me` | 현재 로그인한 사용자 정보(`username`/`id`/`is_admin`) 조회 |
| POST | `/records` | 기록 추가 (201) |
| GET | `/records?target_user=` | 기록 목록 조회 (본인 것만, `is_admin`은 전체. `target_user`로 특정 사용자만 조회 가능 — 일반 사용자가 보내면 무시) |
| GET | `/records/{id}` | 기록 단건 조회 (없거나 타인 기록이면 404) |
| PUT | `/records/{id}` | 기록 수정 (없으면 404, 타인 기록이면 403) |
| DELETE | `/records/{id}` | 기록 삭제 (없으면 404, 타인 기록이면 403) |
| GET | `/search?start=&end=&target_user=` | 기간별 검색 (`start > end`면 422) |
| GET | `/stats?target_user=` | 통계 (평균, 카테고리별 카운트, 0건이면 null) |
| PUT | `/goal` | 목표 체중/혈압 설정 |
| GET | `/goal?target_user=` | 목표 + 달성률 조회 (목표 없으면 `{"goal": null}`) |
| GET | `/reports/weekly?target_user=` | 이번주/지난주 평균과 증감 (데이터 부족 시 null) |
| GET | `/admin/users` | (관리자 전용, 비관리자 403) 전체 사용자 목록 + 가입일/기록 수/건강 상태 요약 |
| GET | `/admin/stats` | (관리자 전용, 비관리자 403) 총 사용자 수/오늘 등록된 기록 수/위험군 사용자 수/전체 평균 BMI |
| GET | `/admin/goals/overview` | (관리자 전용, 비관리자 403) 목표 설정한 사용자만 대상, 체중 달성률 오름차순 |
| GET | `/admin/reports/overview` | (관리자 전용, 비관리자 403) 전체 평균 체중 변화/걸음 수, 개선·악화·변화없음 인원수 |
| GET | `/admin/stats/timeseries?days=` | (관리자 전용, 비관리자 403) 최근 N일(기본 14일) 누적 가입자 수 추이 + 일별 기록 등록 건수 |

## 건강 분류 기준

**BMI**: 18.5 미만 저체중 · 18.5~22.9 정상 · 23~24.9 과체중 · 25 이상 비만

**혈압**: 수축기 <120 & 이완기 <80 정상 · 120~139 또는 80~89 주의 · 수축기 ≥140 또는 이완기 ≥90 고혈압

**공복혈당**: 100 미만 정상 · 100~125 공복혈당장애 · 126 이상 당뇨 의심

**걸음 수**: 5,000 미만 부족 · 5,000~9,999 적정 · 10,000 이상 우수

**수면 시간**: 7시간 미만 부족 · 7~9시간 적정 · 9시간 초과 과다

## 입력값 유효성 검증

`POST`/`PUT /records`에 물리적으로 불가능한 값이 들어오면 422로 거부한다. 범위는 넉넉하게 잡아 극단적이지만 실존 가능한 값은 통과시키고, 명백한 오타·불가능한 값만 걸러낸다.

| 필드 | 허용 범위 |
|---|---|
| weight | 20 ~ 300 (kg) |
| height | 100 ~ 250 (cm) |
| systolic | 60 ~ 250 (mmHg) |
| diastolic | 30 ~ 150 (mmHg) |
| blood_sugar | 20 ~ 600 (mg/dL) |
| steps | 0 ~ 100,000 |
| sleep_hours | 0 ~ 24 |
| date | 1900-01-01 ~ 오늘 (미래 날짜 불가) |

추가로 **이완기 혈압은 수축기 혈압보다 낮아야 한다**(같거나 크면 422) — 생리적으로 불가능한 조합이기 때문.

## 프로젝트 구조

```
health-log-api/
├── app/                          # 애플리케이션 패키지
│   ├── main.py                        # FastAPI 앱 생성, lifespan, 정적 파일 마운트, 라우터 등록
│   ├── auth.py                         # 비밀번호 해싱, JWT 발급/검증, get_current_user 의존성
│   ├── models.py                        # SQLModel (User/Record/Goal 테이블 + Create/Read 스키마)
│   ├── db.py                             # SQLite 엔진, init_db(), get_session() 의존성
│   ├── logic.py                           # BMI·걸음수·수면 계산/분류, 경고 생성, 목표 달성률
│   ├── storage.py                          # 세션 기반 CRUD, 소유권 체크, 목표 저장
│   ├── routers/
│   │   ├── auth.py                          # /auth/signup, /auth/login, /auth/me
│   │   ├── records.py                       # /records, /search, /stats
│   │   ├── goal.py                          # /goal
│   │   ├── reports.py                       # /reports/weekly
│   │   └── admin.py                         # /admin/users, /admin/stats (관리자 전용)
│   └── static/
│       ├── index.html                       # 로그인/회원가입 + 탭 네비 + 5개 뷰(대시보드/기록/목표/리포트/사용자 관리) 마크업
│       ├── css/style.css                      # 색상 변수, 탭/배지/카드/차트/반응형 스타일
│       └── js/app.js                           # 인증, 탭 전환(lazy load), CRUD, Chart.js 렌더링
├── health_log.db                # SQLite DB 파일 (프로젝트 루트, app 패키지 밖)
├── scripts/
│   ├── seed_data.py                     # 개발용 테스트 데이터 자동 생성 스크립트 (회원가입+로그인 포함)
│   ├── create_admin.py                    # 최초 관리자 계정 생성 CLI
│   └── migrate_json_to_db.py                # (레거시) data.json -> SQLite 1회 이관 스크립트
├── tests/
│   ├── conftest.py                         # 인메모리 SQLite + client/auth_headers fixture
│   └── test_records.py                      # pytest 테스트
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt                       # seed 스크립트 전용 의존성
├── .env.example                                # SECRET_KEY 환경변수 이름 안내
└── PROJECT_PLAN.md                              # 상세 기획서
```

## 참고 자료

본 프로젝트는 「헬스케어 미니프로젝트 과제명세서」를 기반으로 작성한 [PROJECT_PLAN.md](PROJECT_PLAN.md) 기획서에 따라 Claude Code와 함께 구현했습니다.
