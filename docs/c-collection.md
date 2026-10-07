# C 오류 수집 v0.5

C 지원은 기존 54종에서 1,539종으로 늘었습니다. 전체 도감은 29,475종입니다.
전체 가능한 C 버그 수가 아니라 로그로 구분할 수 있는 지원 분류 수입니다.

| 범위 | 지원 항목 |
| --- | ---: |
| 기존 C 분류와 통합 분류 | 57 |
| GCC / Clang 메시지 | 970 |
| MSVC 컴파일 오류 코드 | 222 |
| LLD 링크 메시지 | 198 |
| MSVC 링크 오류 코드 | 13 |
| Cppcheck 오류 등급 진단 | 36 |
| ASan 추가 메시지 | 17 |
| UBSan 추가 메시지 | 26 |

기존 54종에는 기본 컴파일·링크·메모리 진단이 포함됩니다. 통합 분류 3종을 추가했습니다.
동일한 메시지 템플릿은 도구나 파일이 달라도 중복 집계하지 않습니다.
기존 세부 분류에 해당하는 메시지는 출처 스냅샷에 남기고 별도 종으로 추가하지 않습니다.
오류의 변수명·숫자·주소만 바뀌면 같은 종이며, 기존 ID와 해결 기록·계열 경험치는 유지합니다.

## VS Code에서 사용

확장을 설치하고 해당 작업 공간에서 수집을 켠 뒤 통합 터미널에서 실행합니다.
명령이 종료되면 오류 부분만 전송합니다. GCC·Clang·cl 명령의 `.c` 인자를 확인해
C 언어 정보도 함께 보내므로, 파일명이 없는 링크 오류를 처리할 수 있습니다.
명령 자체와 추가 인자는 서버에 보내지 않습니다.

```sh
gcc -std=c17 -Wall -Wextra main.c -o app
clang -std=c17 -Wall -Wextra -fuse-ld=lld main.c -o app
```

MSVC는 Visual Studio 개발자 터미널 환경에서 실행합니다.

```bat
cl /nologo /TC main.c /Fe:app.exe
```

Cppcheck는 다음 텍스트 형식으로 실행합니다. XML 출력은 이번 수집기에 포함하지 않습니다.

```sh
cppcheck --language=c --quiet --error-exitcode=2 --template='{file}:{line}:{column}: {severity}: {message} [{id}]' main.c
```

일반 경고·스타일 제안은 수집하지 않습니다. 오류로 승격된 컴파일 진단은 실제 `error:` 출력이면 수집합니다.
Cppcheck는 `error` 등급과 출력된 안정 ID로 구분합니다.

메모리 및 런타임 검사는 계측 옵션으로 빌드한 실행 파일에서 확인합니다.

```sh
clang -std=c17 -g -O0 -fsanitize=address,undefined main.c -o app
./app
```

ASan·UBSan은 사용자가 설치한 컴파일러와 플랫폼의 런타임 지원이 필요합니다.
계측하지 않은 프로그램의 조용한 메모리 오류를 이 서비스가 찾아내는 것은 아닙니다.
지원 진단과 일치하지 않는 MSVC 등의 새 오류는 미분류 발견으로 보관할 수 있습니다.
수동으로 파일명이 없는 링커 로그를 등록할 때는 언어를 C로 지정합니다.

## 출처와 검증

공식 소스의 고정 SHA·파일 해시·진단 정의 수는 [c-catalog-sources.json](c-catalog-sources.json)에 있습니다.
각 항목은 실제 발생 코드나 공식 오류 코드 문서의 줄로 연결되며, 라이선스는 확장에도 포함됩니다.
GCC는 `gcc/c`의 실제 오류 호출을 AST로 읽고 Objective-C 분기·메서드를 제외합니다.
Clang은 C에 적용되는 lexer/preprocessor 오류와 확인된 parser 진단을 사용합니다.
LLD는 ELF 링커가 실제 출력하는 오류 스트림을 읽습니다. MSVC는 확인한 C 공통 오류 코드와 링커 문서를 사용합니다.
Cppcheck는 C에 적용되는 검사 파일의 `error` 등급 호출을 읽고 C++ 전용 항목을 제외합니다.
Sanitizer는 실제 오류 출력에서 추출하며 C++ 전용 new/delete·vptr·missing-return 검사와 Objective-C 검사는 제외합니다.

`source-template`은 공식 소스 및 대표 로그 검증을 의미하며 모든 진단을 실제 프로그램으로 재현했다는 뜻은 아닙니다.
CI는 GCC·Clang C 모드, Cppcheck, LLD, 실제 ASan·UBSan 실행과 Windows MSVC C 모드를 별도로 검증합니다.

갱신은 개발 도구를 설치한 후 명시적으로 실행합니다. 서비스 구동과 일반 빌드에는 다운로드가 없습니다.

```sh
pip install -r requirements-dev.txt
python -m scripts.import_c_catalog
python -m scripts.build_catalog
python -m scripts.build_catalog --check
```
