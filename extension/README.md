# Bug Index for VS Code

C, Python, Java 터미널 오류를 개인 Bug Index 도감에 기록합니다.
v0.5은 29,475개 도감 항목과 traceback/stack trace 기반 미분류 발견을 지원합니다.
Python 라이브러리의 세부 분류에는 오류 한 줄뿐 아니라 라이브러리 경로가 포함된 traceback이 필요합니다.

## 시작

1. Bug Index 웹 서비스에 로그인하고 VS Code 연결 화면에서 토큰을 발급합니다.
2. 명령 팔레트에서 **Bug Index: Connect**를 실행합니다.
3. 서비스 HTTPS 주소와 발급한 토큰을 입력합니다. localhost에는 HTTP도 허용합니다.
4. 신뢰한 프로젝트에서 **Bug Index: Enable Collection**을 실행합니다.
5. VS Code 통합 터미널에서 프로그램을 실행합니다.

VS Code 1.93 이상과 터미널 셸 통합이 필요합니다. Debug Console은 수집하지 않습니다.
Java 라이브러리 세부 분류에는 발생 지점이 포함된 stack trace가 필요합니다.
Gradle은 `./gradlew build --stacktrace`, Android는 `adb logcat -b crash -d -v threadtime`을 통합 터미널에서 실행합니다.
명령 종료 후 수집하므로 계속 실행되는 `adb logcat`은 종료하기 전까지 전송하지 않습니다.
Android 기기의 USB 디버깅과 adb 설치·연결은 별도로 필요합니다.
수집은 기본적으로 꺼져 있고, 작업 공간마다 따로 켭니다.
C는 GCC·Clang·MSVC 컴파일, C 링크 오류, Cppcheck `error` 등급, ASan·UBSan 출력까지 지원합니다.
파일명이 없는 링크 오류에는 `.c` 빌드 명령에서 확인한 C 언어 정보만 함께 전송합니다.
Cppcheck 텍스트 형식과 메모리 검사 빌드 옵션은 [C 수집 안내](https://github.com/staypleur/Bug-Index/blob/main/docs/c-collection.md)를 참고하세요.

## 데이터

알려진 비밀번호·토큰·이메일·홈 경로를 전송 전에 마스킹합니다.
모든 기밀을 자동 식별할 수는 없으므로 민감한 프로젝트에서는 수집을 꺼주세요.
수집 토큰과 서버 연결 실패 시 최대 50건의 마스킹한 로그는 VS Code SecretStorage에 보관합니다.
**Clear Pending Captures**는 대기 로그를 삭제하고, **Disconnect**는 대기 로그와 연결 정보를 삭제합니다.

지원 패턴과 운영 방법은 [프로젝트 README](https://github.com/staypleur/Bug-Index)를 참고하세요.
라이브러리 진단의 출처와 라이선스 고지는 함께 포함된 `THIRD_PARTY_NOTICES.txt`에 있습니다.
