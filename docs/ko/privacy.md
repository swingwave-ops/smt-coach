# 개인정보 경계

[English version](../privacy.md)

SMT Coach는 로컬 읽기 전용 advisor입니다. 설정된 collector에서 정규화된 usage output을
받아 recommendation을 출력합니다. usage data를 upload하지 않고, browser cookie를 검사하거나
API key를 읽거나 OAuth token을 출력하지 않습니다.

하위 collector 환경에서는 provider-home override, API-key 변수, proxy override, alternate
base URL을 제거합니다. process는 현재 account의 일반 home directory를 사용하며 browser-cookie
import를 끕니다.

명시적 policy 파일은 신뢰하지 않는 로컬 입력으로 취급합니다. engine은 최종 file component의
symlink 여부, regular-file 소유자와 권한을 확인하고, 최대 1MiB+1바이트만 읽으며, parse하는
것과 동일한 bytes를 hash합니다. 오류에는 경로, key, value, stack trace를 echo하지 않습니다.

Fixture mode가 권장되는 테스트 방식입니다. fixture data는 synthetic이어야 하며 repository에
account name, email address, quota receipt, token을 넣지 마세요.

