# Bug Index

개발 중 만난 오류를 수집하고 해결 경험을 쌓는 개발자용 버그 도감 서비스입니다.
C · Python · Java 오류를 VS Code 터미널에서 수집합니다.

## 첫 버전 기능

- GitHub 로그인과 사용자별 독립된 수집 기록
- VS Code 셸 통합 기반 자동 수집, 작업 공간별 수집 켜기/끄기
- 9,819개의 오류 분류 항목(C 54 / Python 9,671 / Java 94), 수동 로그 등록, 검색·언어·라이브러리·계열 필터·정렬
- NumPy·pandas·SciPy·scikit-learn·SymPy·Django·SQLAlchemy·Flask·requests·FastAPI 소스 기반 메시지 분류와 Spring·Maven·Gradle 예외 분류
- 도감에 없는 오류의 **미분류 발견** 저장, 해결 메모와 업데이트 후 재분류 (정식 종류 수·XP·랭킹과 별도)
- 프로젝트·소스 위치·함수 기반 SHA-256 fingerprint와 재발 기록
- 세부종류별 수집과 오류 계열별 공유 경험치·레벨, 개별 버그별 원인·해결 방법·학습 메모
- 마스터 조건: 해당 오류 종류 조우 5회 이상 + 서로 다른 버그 3건 해결
- Pro: 언어·프로젝트·일별 통계, 상위 오류, 공개 동의한 헌터 랭킹
- 토큰 발급/폐기, 로그 마스킹, 오프라인 수집 재시도, 개인 데이터 내보내기

실제 결제는 연결하지 않았습니다. 구독 가격은 추후 결정합니다.
현재 코드는 첫 구현 버전이며, 실제 GitHub OAuth 및 Mac mini 공개 배포는 운영 설정 후 검증해야 합니다.

## 기술 구성

Python 3.12 / FastAPI / SQLite(WAL) / HTML·CSS·JavaScript / VS Code JavaScript extension.
Mac mini 한 대에서 운영하기 위한 구성입니다. SQLite 백업과 환경 변수 설정으로 다른 서버로 이전할 수 있습니다.
규모가 커지면 PostgreSQL과 작업 큐 도입을 검토합니다.

```text
VS Code terminal → local detection & masking → HTTPS capture API
                                                   ↓
GitHub OAuth → authenticated dashboard ← SQLite occurrences & solutions
```

## 로컬 실행

Python 3.12 이상이 필요합니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
DEV_LOGIN=1 PUBLIC_URL=http://localhost:8000 python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
$env:DEV_LOGIN='1'
$env:PUBLIC_URL='http://localhost:8000'
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

`http://localhost:8000`에서 **로컬 개발 로그인**을 선택하세요.
처음에는 빈 도감으로 시작합니다. 샘플 데이터는 자동 생성하지 않습니다.
`DEV_LOGIN=1`은 localhost에서만 허용되며, 운영 환경에서는 반드시 `0`으로 설정합니다.

## VS Code 확장

Node.js 22 이상과 npm이 필요합니다.

```bash
cd extension
npx @vscode/vsce package
code --install-extension bug-index-0.3.0.vsix
```

1. 웹의 **VS Code 연결** 화면에서 수집 토큰을 발급합니다.
2. VS Code 명령 팔레트에서 **Bug Index: Connect**를 실행하고 서비스 URL과 토큰을 입력합니다.
3. 수집할 프로젝트를 연 뒤 **Bug Index: Enable Collection**을 실행합니다.
4. 통합 터미널에서 C, Python 또는 Java 프로그램을 실행합니다.
5. 지원되는 오류가 출력되면 전송되고, 도감은 최대 20초 내 갱신됩니다.

확장 개발 시에는 `extension` 폴더를 VS Code로 열고 F5를 누릅니다.
수집을 끄려면 **Disable Collection**, 연결과 대기 기록을 지우려면 **Disconnect**를 사용합니다.

### 수집 범위와 한계

- VS Code 1.93 이상과 [터미널 셸 통합](https://code.visualstudio.com/docs/terminal/shell-integration)이 필요합니다.
- 현재 터미널에서 시작한 명령의 출력을 감지합니다. Debug Console, Output 패널, Visual Studio는 아직 지원하지 않습니다.
- 알려진 영어 진단을 분류하고, traceback/stack trace 등 오류 증거가 있는 미지원 진단은 미분류 기록으로 보관합니다. 정상 로그에 실제 진단 형식의 문자열을 출력하는 경우도 감지될 수 있습니다.
- Python 라이브러리 세부 분류에는 해당 라이브러리의 traceback 경로가 필요합니다. 마지막 예외 한 줄만 붙여 넣으면 기본 계열로 분류될 수 있습니다.
- C의 메모리 누수·버퍼 오버플로는 AddressSanitizer/LeakSanitizer 진단 출력이 있어야 수집됩니다.
- 한 실행의 오류 문맥을 한 건으로 수집합니다. 복수 오류를 완전히 분리하는 파서는 후속 작업입니다.
- 서버 연결 실패 시 최대 50건을 VS Code SecretStorage에 보관하고 30초마다 재시도합니다.
- 토큰과 마스킹한 대기 기록은 SecretStorage에 저장됩니다. 프로젝트 설정 파일에는 토큰을 쓰지 않습니다.
- 알려진 키/토큰/비밀번호/이메일/홈 경로를 마스킹하지만, 모든 형태의 개인정보나 기밀을 식별하지는 못합니다.
- 로그 전체 터미널 이력 대신 최대 80줄·32KiB의 오류 문맥을 전송합니다. 명령 출력은 최대 64KiB 버퍼에서 분석합니다.

## 성장과 랭킹

- 같은 오류 계열의 XP를 합산합니다. 예를 들어 TypeError의 피연산자 타입 불일치와 호출 불가 객체는 서로 다른 카드로 수집되지만 TypeError 계열의 레벨을 공유합니다.
- 레벨 L 진입에 필요한 누적 XP는 `5 × (L−1)²`입니다. Lv.2: 5, Lv.3: 20, Lv.4: 45 XP.
- 같은 오류 계열은 1분에 최대 1 XP를 받습니다. 세부종류를 바꿔도 쿨다운을 우회하지 못하며 조우 기록은 모두 보관합니다.
- 해결은 원인과 해결 방법을 모두 기록해야 완료할 수 있습니다.
- 랭킹 점수는 `현재 해결된 고유 버그 수 × 100 + 마스터한 오류 계열 수 × 500`입니다. 같은 계열의 세부카드가 여러 개여도 마스터 점수는 한 번만 계산합니다.
- 해결 상태를 반복 변경해도 추가 점수가 누적되지 않습니다.
- 랭킹 공개는 기본 비활성입니다. GitHub 사용자명과 점수만 공개하고, 로그·프로젝트·해결 메모는 공개하지 않습니다.
- 실제 해결 여부는 사용자가 기록하므로 경쟁 랭킹의 진위 검증은 아직 제공하지 않습니다.
- 무료 사용자는 기본 도감을 이용하고, Pro 사용자만 고급 통계와 랭킹을 조회합니다. 운영자가 테스트 플랜을 설정할 수 있습니다.

## Mac mini 배포

[맥미니 운영 가이드](docs/mac-mini.md)를 참고하세요. Docker Compose, GitHub OAuth, HTTPS 터널,
재시작 및 백업 방법을 포함합니다. 현재 Mac mini에 접근한 상태가 아니므로 원격 배포가 완료된 것은 아닙니다.

## 검증

```bash
pip install -r requirements.lock pytest==9.0.2
python -m pytest -q
python -m scripts.build_catalog --check
node --test extension/*.test.js
```

Windows 환경에서 임시 폴더 접근 제한이 있다면 `--basetemp .pytest_tmp`를 추가하세요.
GitHub Actions는 API·확장 테스트, JavaScript 문법 검사, Docker 이미지 빌드를 실행합니다.
OAuth 테스트는 외부 GitHub 요청을 모의 처리합니다. VS Code 확장 런타임 테스트도 API를 모의 처리하므로
설치된 VS Code와 실제 GitHub 계정에서의 최종 검증이 별도로 필요합니다.

## 오류 세분화

[분류 목록과 확장 방법](docs/catalog.md)을 참고하세요. 기존 21개 통합 분류의 번호는 유지하고,
Python 내장 예외, Java 표준 예외, C/Java 컴파일 오류와 C sanitizer 진단을 추가했습니다.
v0.3에는 공식 소스에서 추출한 Python 라이브러리 진단 9,579개와 Java 라이브러리·빌드 도구 예외 10개를 추가했습니다.
9,819개는 통합 분류와 세부 메시지 유형을 합한 지원 항목 수이며, 전체 가능한 버그 수를 뜻하지 않습니다.
파일명·변수명·입력값만 달라지는 메시지는 새 종류로 세지 않습니다. 모든 라이브러리 항목에 고정 소스 버전과 발생 위치 링크가 있습니다.
전체 대표 로그와 일부 실제 실행 오류를 검증했으며 모든 항목을 실제 라이브러리 실행으로 재현한 것은 아닙니다.
미분류 기록은 원본 마스킹 로그와 해결 메모를 보관합니다. 재분류는 사용자가 요청할 때 수행하고 과거 XP는 지급하지 않습니다.

## 남은 출시 결정

- 운영 도메인과 Mac mini 접근/설치 방식
- 실제 GitHub OAuth App 설정
- 월 구독 가격과 결제 연동
- 사용자 확인 후 UI 스타일 및 레벨·랭킹 밸런스 조정
- Marketplace 확장 공개 및 실제 C·Python·Java 프로젝트의 수집 검증
