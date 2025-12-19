# 2025-12-19 서버 최적화 및 CI/CD 구축 작업 요약

## 1. 인프라 업그레이드 (AWS EC2)

성능 병목(RAM 부족, CPU 처리량 한계) 해결을 위해 서버 스펙을 상향 조정함.

*   **Server A (Main API & Spring Boot)**
    *   **Instance**: `t3.large` (2 vCPU, 8GB) → **`m5.xlarge` (4 vCPU, 16GB)**
    *   **Storage**: 30GB → 60GB (볼륨 확장 및 파일시스템 `growpart`, `resize2fs` 적용)
*   **Server B (GPU API)**
    *   **Instance**: `g4dn.xlarge` (4 vCPU, 16GB, Tesla T4 GPU) 유지/생성
*   **Front Server**
    *   `t3.micro` 유지 (빌드는 로컬에서 수행 후 결과물만 배포하는 방식 권장)

---

## 2. 소프트웨어 성능 최적화

하드웨어 성능을 100% 활용하기 위해 프로세스 실행 방식 변경.

### 2.1. FastAPI (Python)
*   **문제**: `python server.py` 실행 시 단일 코어만 사용하여 `m5.xlarge`의 4코어를 낭비.
*   **해결**: `uvicorn` 직접 실행 및 워커 수 증가 (`--workers 2`).
*   **적용**: `ecosystem.config.js`에서 실행 명령어 변경.
    ```javascript
    script: "/home/ubuntu/main-api/venv/bin/uvicorn",
    args: "m1.server:app --host 0.0.0.0 --port 8001 --workers 2",
    ```

### 2.2. Spring Boot (Java)
*   **튜닝**: `application.yml`에서 DB 커넥션 풀(`maximum-pool-size: 20`) 및 톰캣 쓰레드 설정 최적화.
*   **실행**: `ecosystem.config.js`에서 힙 메모리 설정 추가 (`-Xms2g -Xmx8g`).

### 2.3. Nginx
*   `worker_processes auto`, `worker_connections 2048` 설정으로 동시 접속 처리량 증대.

---

## 3. 트러블슈팅: 무한 재시작 & 포트 충돌 해결

### 3.1. 문제 현상
*   PM2로 실행 시 `Address already in use` 에러가 발생하며 무한 재시작.
*   배포 후에도 기존 프로세스가 죽지 않고 포트를 점유.

### 3.2. 원인 분석
*   **이중 실행**: Python 코드 내 `if __name__ == "__main__": uvicorn.run(...)` 블록이 존재하여, PM2가 실행한 프로세스 외에 자식 프로세스가 또 생성됨. PM2가 종료 신호를 보내도 자식은 죽지 않고 고아(Zombie/Orphan) 프로세스가 되어 포트를 점유함.
*   **권한 문제**: CI/CD 배포 시 파일/폴더 권한(`sudo` 사용 여부) 충돌로 파일 삭제 실패.

### 3.3. 해결책
1.  **코드 수정**: 모든 `server.py` 파일의 `if __name__ == "__main__":` 블록 **주석 처리 또는 삭제**.
2.  **PM2 설정 변경**: 스크립트 실행 방식 대신 **바이너리 직접 실행(`interpreter: none`)** 방식으로 변경하여 PM2가 프로세스를 직접 제어하도록 수정.
3.  **배포 스크립트 강화**:
    *   Spring Boot 배포 시 `pm2 stop` 후 `fuser -k`로 강제 종료 및 `sudo rm`으로 파일 강제 삭제 로직 추가.

---

## 4. CI/CD 파이프라인 구축 (GitHub Actions)

3개의 리포지토리(Main API, GPU API, Spring Boot)에 대한 자동 배포 시스템 구축.

### 4.1. Server A: Main API (FastAPI)
*   **전략**: `pm2 startOrReload`를 사용하여 무중단 배포 지향.
*   **절차**: Git Pull -> 가상환경 의존성 설치 -> PM2 Reload -> Save.

### 4.2. Server B: GPU API (P2PNet)
*   **전략**: Conda 가상환경 활용 및 `ecosystem.config.js` 기반 배포.
*   **절차**: Git Pull -> Conda 환경 활성화 -> PM2 Start/Reload -> Save.
*   **주의**: `p2pnet_env` 등의 절대 경로 사용 필수.

### 4.3. Server A: Spring Boot
*   **전략**: GitHub Actions Runner에서 빌드 후 JAR 파일만 전송 (서버 리소스 절약).
*   **절차**:
    1.  GitHub에서 `gradlew build` 수행.
    2.  SSH 접속하여 기존 서버 중지 (`pm2 stop`) 및 JAR 파일 강제 삭제 (`sudo rm`).
    3.  SCP로 새 JAR 파일 전송.
    4.  서버 재시작 (`pm2 restart`) 및 권한 부여.

---

## 5. 최종 서버 설정 파일 (ecosystem.config.js)

### Server A (Main)
```javascript
module.exports = {
  apps : [
    {
      name: "m1-road",
      script: "/home/ubuntu/main-api/venv/bin/uvicorn",
      args: "m1.server:app --host 0.0.0.0 --port 8001 --workers 2",
      cwd: "/home/ubuntu/main-api",
      interpreter: "none",
      env: { PYTHONPATH: "/home/ubuntu/main-api" },
      restart_delay: 5000,
      max_restarts: 10
    },
    // ... (m2, m4, m5 동일 패턴) ...
    {
      name: "springboot-server",
      script: "/usr/bin/java",
      args: [
        "-jar",
        "-Xms2g",
        "-Xmx8g",
        "build/libs/safety-0.0.1-SNAPSHOT.jar"
      ],
      cwd: "/home/ubuntu/springboot",
      exec_mode: "fork",
      restart_delay: 10000,
      max_restarts: 10
    }
  ]
}
```

### Server B (GPU)
```javascript
module.exports = {
  apps : [{
    name: "m3-gpu",
    script: "/home/ubuntu/p2pnet_env/bin/uvicorn", // Conda 환경 경로
    args: "server:app --host 0.0.0.0 --port 8003 --workers 1",
    cwd: "/home/ubuntu/p2pnet-api/m3",
    interpreter: "none",
    exec_mode: "fork",
    restart_delay: 5000,
    max_restarts: 10
  }]
}
```
