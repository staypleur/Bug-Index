# 오류 분류 v0.2

225개 지원 항목: C 54개 / Python 87개 / Java 84개.
여기에는 메시지를 세분화할 수 없는 경우를 위한 통합 분류도 포함됩니다.
모든 항목에 이름, 고정 ID, 계열 ID, 진단 패턴, 대표 로그 fixture, 참고 문서가 있습니다.
세부종류는 진단 메시지에서 확인할 수 있는 차이를 기준으로 구분합니다. 원인이 출력되지 않은
Segmentation Fault를 NULL 역참조라고 추측하는 식의 분류는 하지 않습니다.

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
- 컴파일러·런타임 버전이나 출력 언어가 바뀌면 정확한 메시지가 달라질 수 있습니다. 알려진 패턴에 맞지 않는 진단은 통합 분류에 남거나 미수집될 수 있습니다.
- C 메모리 오류는 sanitizer가 실제 진단을 출력해야 수집합니다. 소스 코드를 분석해 잠재 오류를 추측하지 않습니다.
- Ctrl+C, 정상 반복 종료, 일반 경고, 예외 이름만 언급하는 설명문은 수집 대상에서 제외합니다.

대표 fixture 전부를 분류기에 통과시켜 규칙 겹침과 누락을 검사합니다.
별도로 실제 Python 프로그램 33개, javac 진단 8개, GCC/Clang 진단 8개를 실행하는 테스트도 포함합니다.
해당 컴파일러가 설치되지 않은 환경에서는 그 실행 테스트가 skip됩니다.
이는 대표 오류를 검증하는 범위이며, 모든 버전의 진단 메시지를 검증했다는 의미는 아닙니다.

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

## 참고 자료

- [Python 내장 예외](https://docs.python.org/3/library/exceptions.html)
- [Java SE 표준 API](https://docs.oracle.com/en/java/javase/21/docs/api/)
- [Clang 진단 문서](https://clang.llvm.org/docs/DiagnosticsReference.html)
- [GCC 진단 출력](https://gcc.gnu.org/onlinedocs/gcc/Diagnostic-Message-Formatting-Options.html)
- [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)
- [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)
