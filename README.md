# git-base-team3-test

간단한 Flask 기반 CTF/리서치 팀 모집/워게임 앱을 Docker로 바로 띄울 수 있도록 정리했습니다.

## 요구사항
- Docker Desktop (Compose 포함)
- 열린 포트: 웹 5000, MySQL 기본 3306 (이미 사용 중이면 Compose에서 포트만 조정)

## 빠른 시작 (Docker)
1. 환경파일 준비
   ```bash
   .env
   # SECRET_KEY, DB_PASSWORD, DB_ROOT_PASSWORD를 원하는 값으로 입력
   ```
2. 빌드 & 실행
   ```bash
   docker compose up -d --build
   ```
3. 접속: http://localhost:5000

## 환경변수 (.env)
- `SECRET_KEY` : 긴 랜덤 문자열 (세션/CSRF 키)
- `DB_ENGINE` : `mysql`(기본) 또는 `sqlite`
- `DB_HOST` : MySQL 컨테이너 이름 `db`
- `DB_PORT` : 3306 (컨테이너 내부용, 호스트 포트는 Compose `ports`에서 조정)
- `DB_USER` / `DB_PASSWORD` : 일반 계정
- `DB_NAME` : 생성할 DB 이름
- `DB_ROOT_PASSWORD` : 루트 계정 비밀번호
- `MAX_CONTENT_LENGTH` : 업로드 최대 크기(바이트)

## 관리 명령어
- 상태 확인: `docker compose ps`
- 로그 보기: `docker compose logs -f web`
- 중지: `docker compose down`
- 데이터까지 제거: `docker compose down -v` (기존 데이터 없을 때만)
- 다시 빌드: `docker compose up -d --build`

## 트러블슈팅
- **3306 포트 충돌**: 다른 MySQL이 점유 중.  
  - 중지하거나, `docker-compose.yml`의 `db` 서비스 `ports`를 `3307:3306`처럼 변경 (`.env`의 `DB_PORT`는 3306 유지).
- **db unhealthy**: 비번/계정 불일치 또는 이전 볼륨 충돌.  
  - `.env`의 `DB_USER/DB_PASSWORD/DB_ROOT_PASSWORD` 확인 후 `docker compose down -v` → `up -d --build`.
- **web이 localhost:3306에 대기**: `.env`의 `DB_HOST`를 `db`로 설정.

## 프로젝트 구조
- `app.py` : Flask 앱 팩토리
- `models/` : SQLAlchemy 모델
- `routes/` : 블루프린트 라우트
- `services/ctftime.py` : 외부 이벤트 조회
- `static/`, `templates/` : 정적/템플릿 자원
- `docker-entrypoint.sh` : 컨테이너 부팅 시 DB 대기 + 테이블 생성 + 서버 실행

## Docker로 완전 초기 설정하기
1. `.env.example`을 복사해 `.env`를 만든 뒤 값(특히 `SECRET_KEY`/DB 비밀번호)을 원하는 값으로 수정합니다.
2. `docker compose up --build`를 실행합니다. 처음 실행 시 MySQL 준비 → 테이블 생성까지 자동으로 진행됩니다.
3. 브라우저에서 `http://localhost:5000` 접속.

### 기본 구조
- `web`: Flask + Gunicorn 컨테이너 (`Dockerfile`).
- `db`: MySQL 8.0 컨테이너. `DB_*` 값을 `.env`로 전달하며, 데이터는 `mysql_data` 볼륨에 보존됩니다.
- 업로드 폴더는 호스트의 `static/uploads`, `static/wargame_attachments`와 볼륨으로 연결됩니다.

### 주요 환경 변수 (`.env`)
- `SECRET_KEY`: Flask 세션/CSRF 키.
- `DB_ENGINE`: 기본 `mysql` (sqlite를 쓰려면 `sqlite`로 변경하고 `DB_HOST` 등은 무시됨).
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: MySQL 연결 정보.
- `DB_ROOT_PASSWORD`: MySQL 루트 패스워드(컨테이너 초기화용).
- `MAX_CONTENT_LENGTH`: 업로드 최대 크기(바이트).

### 자주 쓰는 명령
- 빌드 및 실행: `docker compose up --build`
- 백그라운드 실행: `docker compose up -d`
- 정리: `docker compose down` (데이터까지 지우려면 `docker compose down -v`)

### 참고
- MySQL 없이 빠르게 띄우려면 `.env`에서 `DB_ENGINE=sqlite`로 설정하고 `docker compose up web`만 실행할 수 있습니다.
