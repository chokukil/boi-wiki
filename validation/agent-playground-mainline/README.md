# Agent Playground 로컬 검증

이 디렉터리의 스택과 도구는 `boi-validation` 로컬 환경 전용이다. 사내
Keycloak, Langflow, Agent Hub 운영 데이터에는 적용하지 않는다.

## 공용 데모 로그인

발표용 `boi-dev` 로그인은 별도 사용자를 위한 새 업무 공간이 아니다. OIDC의
`empno=100002` 별칭으로 기존 개발자 공간, `boi-100002` 프로젝트, 검증된
DEV/PRD Flow와 Action을 그대로 사용한다. Wiki 저장 기본값도 `preview`다.

준비:

```bash
BOI_DEMO_PASSWORD='<local-demo-password>' \
python validation/agent-playground-mainline/prepare_demo_account.py
```

준비가 끝나면 `http://localhost:28005/playground`에서 `boi-dev`로 로그인한다.
같은 브라우저에서 Langflow 원본 Canvas와 Agent Hub를 열면 같은
`employee_id=100002` 자산을 사용한다. 데모 중에는 원래 `100002` 계정으로
Agent Hub에 동시에 로그인하지 않는다.

복구:

```bash
python validation/agent-playground-mainline/restore_demo_account.py
```

준비 도구는 원래 Agent Hub `100002` 사용자의 표시 이름, 이메일과 Keycloak
subject를 사용자 로컬 state 디렉터리의 mode `0600` 파일에 한 번만 백업한다.
복구 도구는 해당 값을 정확히 되돌린 뒤 `boi-dev` Keycloak 사용자를 제거한다.
두 도구는 지정 Agent Hub SHA와 clean checkout, localhost Keycloak,
`boi-validation` realm을 확인한다.

이 계정은 로컬 시연 편의를 위한 공용 계정이며 사내 계정이 아니다. 사내 SSO가
연결되면 이 데모 매핑을 제거하고 실제 사번 Principal을 사용한다.
