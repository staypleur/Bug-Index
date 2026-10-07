# Mac mini 운영 가이드

## 준비

- Mac mini에서 Git, Docker Desktop, Docker Compose를 준비합니다.
- 외부 공개에 사용할 도메인과 HTTPS 연결을 준비합니다.
- GitHub OAuth App을 생성합니다. 홈페이지 URL은 실제 서비스 주소,
  callback URL은 `https://실제서비스주소/auth/github/callback`입니다.
- Client secret은 채팅이나 저장소에 올리지 않고 Mac mini의 `.env`에만 저장합니다.

참고: [GitHub OAuth App 생성](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app),
[Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/).

## 설치와 시작

```bash
git clone https://github.com/staypleur/Bug-Index.git
cd Bug-Index
cp .env.example .env
chmod 600 .env
```

`.env`의 `PUBLIC_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`을 설정합니다.
`DEV_LOGIN=0`을 유지합니다. 기본 `BUG_INDEX_DB=/app/data/bug-index.sqlite3`도 유지합니다.

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

응답이 `{"status":"ok"}`인지 확인합니다. 앱 포트는 Mac mini의 localhost에만 바인딩됩니다.
SQLite 파일은 Docker 이름 있는 볼륨에 저장됩니다. **`docker compose down -v`는 데이터 볼륨을 삭제하므로 사용하지 마세요.**

## 외부 공개

Cloudflare에 등록한 도메인이 있다면 Cloudflare Tunnel을 생성합니다.
Mac mini에서 공식 `cloudflared`를 설치하고, 관리 화면에서 제공한 터널 실행 명령을 사용합니다.
터널 토큰은 외부에 공개하지 않습니다. 시스템 서비스 설치에는 Mac mini 관리자 권한이 필요할 수 있습니다.

Public hostname의 연결 대상을 `http://localhost:8000`으로 설정합니다.
이 연결 대상은 Mac mini 호스트에서 실행하는 `cloudflared` 기준입니다.
터널 프로세스를 Docker 컨테이너에서 실행한다면 localhost가 다른 컨테이너를 가리키므로 별도의 네트워크 설정이 필요합니다.

운영 주소를 바꾸면 `.env`의 `PUBLIC_URL`과 GitHub OAuth callback URL을 함께 바꾸고 앱을 재생성합니다.
무료 임시 터널 주소는 변경될 수 있어 지속적인 GitHub 로그인 운영에는 고정 도메인을 권장합니다.
Cloudflare Tunnel 대신 HTTPS를 처리하는 리버스 프록시를 사용할 수도 있습니다.

## 24시간 운영

- macOS 전원 설정에서 전원 연결 시 자동 잠자기를 막습니다.
- Docker Desktop이 로그인 시 시작되도록 설정합니다. Compose의 `restart: unless-stopped`는 Docker 엔진이 켜진 이후에 적용됩니다.
- 정전 후 자동 재시작 여부, macOS 로그인, FileVault 잠금 해제를 실제 재부팅으로 점검합니다.
  로그인 전 Docker Desktop이 켜지지 않는 구성에서는 앱도 시작되지 않습니다.
- `cloudflared`를 시스템 서비스로 등록하고 재부팅 후 터널과 앱이 모두 살아나는지 확인합니다.
- 데이터 백업은 Mac mini 외부의 저장소에도 복사합니다.

## 백업

앱 실행 중에도 SQLite Backup API를 이용해 일관된 스냅샷을 만들 수 있습니다.

```bash
docker compose exec app python -m scripts.manage backup /app/data/backup-2026-10-06.sqlite3
```

아래 명령으로 호스트에 복사합니다. 날짜는 백업일에 맞게 바꾸세요.

```bash
mkdir -p backups
docker compose cp app:/app/data/backup-2026-10-06.sqlite3 backups/
```

백업에는 사용자 기록이 포함되므로 공개 저장소나 공개 URL에 올리지 않습니다.
스크립트는 기존 백업 파일을 덮어쓰지 않습니다. 매일 서로 다른 파일명으로 예약 실행할 수 있습니다.

## 복구 및 다른 서버로 이전

1. 새 서버에 같은 코드와 Docker Compose를 준비합니다.
2. `.env`에 새 운영 주소와 GitHub OAuth 설정을 넣습니다.
3. 데이터베이스가 없는 새 볼륨으로 `docker compose create app`을 실행합니다.
4. `docker compose cp backups/백업파일.sqlite3 app:/app/data/bug-index.sqlite3`으로 복사합니다.
5. 파일 소유권을 앱 계정 UID 10001에 맞춥니다:
   `docker compose run --rm --user root app chown 10001:10001 /app/data/bug-index.sqlite3`.
6. `docker compose up -d`로 시작하고 로그인·도감·수집을 확인합니다.

기존 데이터베이스 위에 복구할 때는 앱을 중지하고 기존 데이터와 WAL/SHM 파일을 함께 별도로 보관한 뒤 진행해야 합니다.
호스트 이전 후 이전 서버로 수집되지 않도록 터널 대상과 확장의 서버 주소를 확인합니다.

## Pro 기능 시험 운영

결제 연동 전에는 서버 관리자만 플랜을 설정할 수 있습니다. 대상 사용자는 먼저 GitHub로 로그인해야 합니다.

```bash
docker compose exec app python -m scripts.manage plan GITHUB_USERNAME pro
docker compose exec app python -m scripts.manage plan GITHUB_USERNAME free
```

플랜 변경 후 사용자는 웹을 새로고침합니다. 사용자용 API로는 Pro 권한을 올릴 수 없습니다.

## 업데이트

먼저 DB를 백업합니다. 그다음:

```bash
git pull --ff-only
docker compose up -d --build
docker compose logs --tail=100 app
```

업데이트 후 health 응답, GitHub 로그인, 오류 수집과 해결 저장을 확인합니다.
v0.2는 기존 버그 레코드에 오류 계열 ID를 추가하는 마이그레이션을 앱 시작 시 실행합니다.
기존 번호·경험치·메모를 유지합니다. 업데이트 전 백업은 계속 필요합니다.
