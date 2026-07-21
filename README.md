# 마이 헬스 로그 API

매일 몸무게·혈압·혈당을 기록하면 BMI 계산, 건강 상태 분류, 경고 메시지를 자동으로 받고, 사용자별로 기록을 분리해서 통계와 히스토리를 확인할 수 있는 API입니다.

> ⚠️ 이 프로젝트의 건강 분류 기준은 학습을 위해 단순화된 값이며, 실제 의학적 진단이 아닙니다.

## 기능 목록

- 건강 기록 CRUD (`POST`/`GET`/`PUT`/`DELETE /records`)
- 기록 시 BMI 자동 계산 및 BMI·혈압·혈당 상태 분류
- 위험 수치 감지 시 조언형 경고 메시지 생성
- `X-User-Id` 헤더 기반 사용자별 기록 분리 (`admin`은 전체 조회/수정/삭제 가능)
- 기간 검색 (`GET /search`)
- 통계 조회: 평균값, 카테고리별 카운트 (`GET /stats`)
- 순수 HTML/JS 화면 (입력 폼 + 목록 조회)

## 기술 스택

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.12 |
| 프레임워크 | FastAPI + Uvicorn |
| 데이터 검증 | Pydantic |
| 데이터 저장 | JSON 파일 (`data.json`) |
| 테스트 | pytest + httpx (FastAPI TestClient) |
| 배포 | Docker |
| 프론트엔드 | 순수 HTML + JS |

## 실행 방법

### 로컬 실행

```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

- API 문서: http://127.0.0.1:8000/docs
- 화면: http://127.0.0.1:8000/

### Docker 실행

```bash
docker build -t my-healthlog-api .
docker run -d -p 8000:8000 my-healthlog-api
```

### 테스트 실행

```bash
pytest tests/ -v
```

## API 엔드포인트

**공통 헤더**: `X-User-Id` (선택, 기본값 `guest`, `admin`이면 조회 시 전체 사용자 대상)

| Method | Path | 설명 |
|---|---|---|
| GET | `/` | 화면(HTML) 반환 |
| GET | `/api` | API 상태 메시지 |
| POST | `/records` | 기록 추가 (201) |
| GET | `/records` | 기록 목록 조회 (본인 것만, `admin`은 전체) |
| GET | `/records/{id}` | 기록 단건 조회 (없거나 타인 기록이면 404) |
| PUT | `/records/{id}` | 기록 수정 (없으면 404, 타인 기록이면 403) |
| DELETE | `/records/{id}` | 기록 삭제 (없으면 404, 타인 기록이면 403) |
| GET | `/search?start=&end=` | 기간별 검색 (`start > end`면 422) |
| GET | `/stats` | 통계 (평균, 카테고리별 카운트, 0건이면 null) |

## 건강 분류 기준

**BMI**: 18.5 미만 저체중 · 18.5~22.9 정상 · 23~24.9 과체중 · 25 이상 비만

**혈압**: 수축기 <120 & 이완기 <80 정상 · 120~139 또는 80~89 주의 · 수축기 ≥140 또는 이완기 ≥90 고혈압

**공복혈당**: 100 미만 정상 · 100~125 공복혈당장애 · 126 이상 당뇨 의심

## 프로젝트 구조

```
health-log-api/
├── main.py          # FastAPI 앱, 라우터, 정적 파일 마운트
├── models.py         # Pydantic 모델 (RecordIn, RecordOut)
├── logic.py           # BMI 계산·분류·경고 생성
├── storage.py          # data.json 읽기/쓰기, 소유권 체크
├── static/index.html    # 화면 (입력 폼 + 목록 조회)
├── tests/test_records.py # pytest 테스트
├── Dockerfile
├── requirements.txt
└── PROJECT_PLAN.md      # 상세 기획서
```

## 참고 자료

본 프로젝트는 「헬스케어 미니프로젝트 과제명세서」를 기반으로 작성한 [PROJECT_PLAN.md](PROJECT_PLAN.md) 기획서에 따라 Claude Code와 함께 구현했습니다.
