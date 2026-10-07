# 오류 분류 v0.4

27,990개 지원 항목: C 54개 / Python 9,671개 / Java 18,265개.
여기에는 메시지를 세분화할 수 없는 경우를 위한 통합 분류도 포함됩니다.
모든 항목에 이름, 고정 ID, 계열 ID, 진단 패턴, 대표 로그 fixture, 참고 문서가 있습니다.
라이브러리별 정적 메시지 유형을 구분하며, 라이브러리·예외 클래스·값을 제거한 메시지 템플릿이 같은 항목은 중복 집계하지 않습니다.
세부종류는 진단 메시지에서 확인할 수 있는 차이를 기준으로 구분합니다. 원인이 출력되지 않은
Segmentation Fault를 NULL 역참조라고 추측하는 식의 분류는 하지 않습니다.

## 외부 라이브러리

Java 중심 확장으로 Java 18,265개를 지원합니다. 이 중 18,133개는 공식 소스에서 추출한 메시지 템플릿입니다.
OpenJDK 6,051 / Android 4,523 / Spring 2,794 / Spring Boot 1,046 / Gradle 1,207 / Maven 237 / Hibernate 1,422 / Netty 655 / Guava 198개입니다.
Jackson은 현재 안전하게 추출할 수 있는 표준 예외 메시지가 없어 추가 항목이 없습니다.
아래 표는 기존 Python 및 문서화된 Java 예외 항목이며, 위 메시지 템플릿이 추가됩니다.

Java AST의 실제 `throw new`와 확인된 Assert/Preconditions/Objects 호출만 읽습니다.
표준 예외의 문자열 생성자를 사용하고, 사용자 정의 생성자·동적 메시지 생성기·텍스트 블록은 추측하지 않습니다.
Java 세부 항목은 스택의 첫 발생 지점이 해당 라이브러리인지 확인합니다. 확인된 검증 도우미 프레임은 건너뜁니다.
JDK 모듈 접두사와 생성자 프레임, AndroidRuntime Logcat 접두사, Maven `[ERROR]` 접두사를 지원합니다.
Android 범위는 framework의 core/java, graphics/java, media/java, telephony/java입니다. Android 전체 오류 목록은 아닙니다.
각 소스의 SHA와 아카이브 해시는 [java-catalog-sources.json](java-catalog-sources.json)에 있습니다.
템플릿 검증은 전체 Android 기기나 라이브러리를 실제 실행했다는 의미가 아닙니다.

| 대상 | 세부 항목 수 |
| --- | ---: |
| NumPy | 506 |
| pandas | 1,753 |
| SciPy | 2,769 |
| scikit-learn | 1,176 |
| SymPy | 2,294 |
| Django | 829 |
| SQLAlchemy | 184 |
| Flask | 38 |
| requests | 18 |
| FastAPI | 12 |
| Spring | 8 |
| Maven | 1 |
| Gradle | 1 |
| 기본 언어 오류·통합 계열 | 230 |

Python 라이브러리 9,579개는 공식 저장소의 실제 `raise` 문에서 읽은 메시지 템플릿입니다.
검증 수준은 `source-template`이며, 대표 fixture 검증과 실제 라이브러리 전 항목 재현은 다릅니다.
테스트·예제·경고·사용자 입력에서 동적으로 만들어지는 메시지·문자열 출력을 추론할 수 없는 사용자 정의 예외는 제외합니다.
`KeyError`의 repr 출력, 다중 인자 예외, 예외 그룹처럼 출력이 달라지는 생성자도 제외합니다.
라이브러리 경로와 예외 이름을 먼저 확인하고, 고정 메시지 부분과 변동값을 분리하여 비교합니다.
값 매칭은 정규식 역추적 없이 문자열 검색으로 수행합니다.
공백·대소문자만 다른 템플릿과 파일별 중복은 합치고, 포맷 인자의 실제 값은 추가 종류로 세지 않습니다.
Java 추가 10개는 공식 API에 문서화된 예외 클래스이며 `documented-exception`으로 표시합니다.

고정 commit SHA·아카이브 SHA-256·항목 수는 [catalog-sources.json](catalog-sources.json)에 기록했습니다.
각 진단의 링크는 해당 commit의 실제 발생 줄로 연결됩니다. 라이선스 고지는 [catalog-licenses](catalog-licenses)에 있고 확장에도 포함합니다.
일반 빌드에는 네트워크가 필요하지 않으며, 커밋된 `server/library_templates.json`을 사용합니다.

## 예시

| 계열 | 세부종류 |
| --- | --- |
| Python TypeError | 피연산자 타입 불일치, 호출 불가 객체, 인덱싱 불가 객체, 인자 누락·중복, 해시 불가 키 |
| Python SyntaxError | 닫히지 않은 괄호·문자열, 콜론 누락, 함수 밖의 return, 반복문 밖의 break |
| Python ValueError | 정수·실수 변환 실패, 언패킹 값 부족·초과, 수학 정의역 오류 |
| Java NullPointerException | null 메서드 호출, 필드 읽기·쓰기, 배열 읽기·쓰기·길이 조회 |
| Java OutOfMemoryError | 힙 부족, Metaspace 부족, GC 한도 초과, 네이티브 스레드 생성 실패 |
| JavaCompileError | 세미콜론 누락, 심볼·패키지 누락, 타입 불일치, 반환문 누락, final 재대입 |
| CCompileError | 세미콜론 누락, 미선언 변수·함수, 헤더 누락, 인자 부족·초과, 잘못된 역참조 |
| C Buffer Overflow | 힙·스택·전역 버퍼 경계 초과 |
| C sanitizer | 이중 해제, 할당하지 않은 주소 해제, 정수 오버플로, NULL 역참조, 정렬 오류 |

## 인식과 호환성

- 영어 CPython traceback, javac/GCC/Clang 진단, Java 기본 stack trace 및 C sanitizer 출력을 기준으로 합니다.
- 예외 출력의 같은 줄에서 통합 규칙과 세부 규칙이 모두 맞으면 세부 규칙을 선택합니다.
- 이어진 traceback에서는 마지막 진단을 선택합니다. 한 실행에서 여러 오류를 독립적으로 수집하는 기능은 아직 없습니다.
- 컴파일러·런타임·라이브러리 버전이나 출력 언어가 바뀌면 메시지가 달라질 수 있습니다. 알려진 패턴에 맞지 않는 진단은 통합 계열 또는 미분류 발견에 남습니다. 오류 증거도 인식하지 못하면 수집하지 않습니다.
- 라이브러리 traceback 없이 마지막 예외 줄만 입력하면 라이브러리를 추측하지 않고 기본 계열로 분류합니다.
- C 메모리 오류는 sanitizer가 실제 진단을 출력해야 수집합니다. 소스 코드를 분석해 잠재 오류를 추측하지 않습니다.
- Ctrl+C, 정상 반복 종료, 일반 경고, 예외 이름만 언급하는 설명문은 수집 대상에서 제외합니다.

대표 fixture 전부를 분류기에 통과시켜 규칙 겹침과 누락을 검사합니다.
별도로 실제 Python 프로그램 33개, javac 진단 8개, GCC/Clang 진단 8개를 실행하는 테스트도 포함합니다.
해당 컴파일러가 설치되지 않은 환경에서는 그 실행 테스트가 skip됩니다.
NumPy·pandas의 실제 traceback 8개도 테스트하며 CI는 고정된 두 패키지를 설치합니다. API 운영 의존성에는 포함하지 않습니다.
이는 대표 오류를 검증하는 범위이며, 모든 버전의 진단 메시지를 검증했다는 의미는 아닙니다.

## 미분류 발견

정식 항목에 맞지 않지만 traceback/stack trace/컴파일 진단 증거가 있는 오류를 사용자별로 저장합니다.
마스킹은 저장 전 수행하고, request ID 중복 방지와 분당 60건 한도는 정식 수집과 공유합니다.
로그·프로젝트·발생 시간·조우 횟수·원인·해결·메모를 보관하며, 정식 도감 종류 수·XP·마스터·랭킹에는 포함하지 않습니다.
업데이트 후 화면의 **다시 분류** 버튼으로 재평가할 수 있습니다. 모든 조우가 같은 종·사례로 분류될 때만 이동합니다.
발생 시간과 메모를 유지하고 기존 해결 메모는 덮어쓰지 않습니다. 과거 로그에는 XP를 소급 지급하지 않습니다.
재분류 전 기록도 감사·내보내기용으로 보관하고 `resolved_bug_id`로 정식 기록에 연결합니다.

## 데이터와 레벨

기존 ID 1~21과 fingerprint, 해결 메모, 발생 기록은 유지합니다. DB 시작 시 `family_id`를 추가하는
멱등 마이그레이션을 실행합니다. 기존 통합 분류 기록을 임의로 재분류하지 않습니다.
따라서 세분화 전에 통합 카드로 수집했던 오류는 이후 새로운 세부 카드로도 나타날 수 있습니다.
양쪽 기록의 경험치는 같은 계열에 합산되고 과거 메모는 통합 카드에서 조회할 수 있습니다.

세부 카드의 조우·해결 건수는 각각 계산하고, 레벨과 마스터 조건은 계열에 합산합니다.
마스터한 계열 수와 랭킹 점수는 중복 계산하지 않습니다.

## 추가 방법

1. `scripts/build_catalog.py`에 새로운 고정 ID, 패턴, fixture와 참고 자료를 추가합니다.
2. 기존 ID를 재사용하거나 바꾸지 않습니다. 통합 계열이 있다면 `family_id`를 지정합니다.
3. `python -m scripts.build_catalog`로 API와 확장의 JSON을 함께 생성합니다.
4. `python -m scripts.build_catalog --check`, `python -m pytest -q`, `node --test extension/*.test.js`를 실행합니다.
5. 기존 로그와 겹칠 수 있는 패턴은 실제 실행 결과와 오탐 예제로 확인합니다.

Python 라이브러리를 추가할 때는 `scripts/import_library_catalog.py`의 공식 저장소 목록을 확장하고 명시적으로 실행합니다.
Java는 `pip install -r requirements-dev.txt` 후 `python -m scripts.import_java_catalog`로 갱신합니다.
Windows 안정성을 위해 Tree-sitter 0.25.2와 Java grammar 0.23.5를 고정했습니다.
도구는 원격 소스를 AST로 읽으며 실행하지 않습니다. 내려받은 자료는 ignored `artifacts/catalog-sources`에 보관합니다.
이미 공개한 ID와 템플릿은 다시 번호를 매기거나 제거하지 않습니다. upstream에서 제거된 오류도 이전 버전 사용자에게 필요하므로 유지합니다.

## 참고 자료

- [Python 내장 예외](https://docs.python.org/3/library/exceptions.html)
- [Java SE 표준 API](https://docs.oracle.com/en/java/javase/21/docs/api/)
- [Clang 진단 문서](https://clang.llvm.org/docs/DiagnosticsReference.html)
- [GCC 진단 출력](https://gcc.gnu.org/onlinedocs/gcc/Diagnostic-Message-Formatting-Options.html)
- [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)
- [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)
