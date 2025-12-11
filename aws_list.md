# AWS 단일 EC2 배포 체크리스트 (Dockerless)

본 문서는 Docker 없이 하나의 EC2 인스턴스에서 Main API, P2PNet API, Spring Boot 서버를 동시에 운영하기 위한 작업 순서입니다.

> **참고 자료 모음**
> *   [AWS 공식 문서: EC2 인스턴스에서 스왑 메모리 설정](https://repost.aws/ko/knowledge-center/ec2-memory-swap-file)
> *   [CodeChaCha: Ubuntu에 Python 특정 버전 설치 (PPA 활용)](https://codechacha.com/ko/ubuntu-install-python39/)
> *   [PM2 공식 문서: Ecosystem File 설정](https://pm2.keymetrics.io/docs/usage/application-declaration/)
> *   [Velog: PM2로 Python Flask/FastAPI 배포하기](https://velog.io/@markyang92/pm2-python-flask)
> *   [Tistory: Nginx 리버스 프록시 설정 및 Spring Boot 연동 예시](https://7942yongdae.tistory.com/136)

## 1. 서버 아키텍처 및 포트 계획 (예시)

| 서비스 명 | 언어/버전 | 경로 | 내부 포트 | 비고 |
| --- | --- | --- | --- | --- |
| **Main API** | Python 3.10 | `/home/ubuntu/main-api` | `8005` | FastAPI (m1, m2, m4, m5) |
| **P2PNet API** | Python 3.8 | `/home/ubuntu/p2pnet-api` | `8001` (예정) | P2PNet (m3) |
| **Spring Boot** | Java 17 | `/home/ubuntu/springboot` | `8080` | 메인 백엔드 |
| **Nginx** | - | - | `80`, `443` | 리버스 프록시 (라우팅) |

---

## 2. EC2 인스턴스 초기 설정

### 2-1. 인스턴스 생성 및 접속
*   OS: **Ubuntu Server 22.04 LTS** (권장)
*   Instance Type: 최소 **t3.medium** 또는 **t3.large** (딥러닝 모델 메모리 고려)
*   Storage: 30GB 이상 (모델 가중치 및 라이브러리 용량)

### 2-2. 필수 패키지 설치 및 Python 버전 관리
Ubuntu 22.04는 기본적으로 Python 3.10을 탑재하고 있습니다. 3.8 버전을 추가로 설치해야 합니다.

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 기본 도구 설치
sudo apt install -y git curl unzip build-essential

# Python 버전 관리를 위한 PPA 추가 (deadsnakes)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Python 3.8 및 3.10 관련 패키지 설치 (venv, dev 필수)
sudo apt install -y python3.8 python3.8-venv python3.8-dev
sudo apt install -y python3.10 python3.10-venv python3.10-dev

# Java 17 설치 (Spring Boot 용)
sudo apt install -y openjdk-17-jdk
java -version  # 설치 확인
```

### 2-3. Swap 메모리 설정 (★매우 중요★)
메모리 부족으로 서버가 다운되는 것을 방지하기 위해 반드시 설정합니다. (4GB 권장)
> **참고:** [AWS 공식 가이드 - 스왑 공간 할당](https://repost.aws/ko/knowledge-center/ec2-memory-swap-file)

```bash
# 4GB 스왑 파일 생성
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 재부팅 후에도 유지되도록 fstab 등록
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 확인
free -h
```

---

## 3. 애플리케이션 배포 및 환경 구성

### 3-1. 디렉토리 구조 생성
```bash
mkdir -p /home/ubuntu/main-api
mkdir -p /home/ubuntu/p2pnet-api
mkdir -p /home/ubuntu/springboot
```

### 3-2. Main API 배포 (Python 3.10)
*   **경로**: `/home/ubuntu/main-api`
*   **구성**: `package` 폴더(m1, m2, m4, m5) 및 실행 파일
*   **주의**: 로컬 개발 환경의 `Model/package` 구조를 서버에서도 동일하게 인식할 수 있도록 배치해야 합니다.

```bash
cd /home/ubuntu/main-api

# 가상환경 생성 (Python 3.10)
python3.10 -m venv venv
source venv/bin/activate

# 의존성 설치
# pip install -r requirements.txt  (requirements.txt가 있다면)
pip install fastapi uvicorn pandas numpy scikit-learn tensorflow # 필요한 패키지들 직접 설치
# (tensorflow나 torch 버전은 로컬과 맞춰야 함)

# .env 또는 환경변수 설정 확인
```

### 3-3. P2PNet API 배포 (Python 3.8)
*   **경로**: `/home/ubuntu/p2pnet-api`
*   **구성**: `package` 폴더(m3)

```bash
cd /home/ubuntu/p2pnet-api

# 가상환경 생성 (Python 3.8)
python3.8 -m venv venv
source venv/bin/activate

# P2PNet 전용 의존성 설치 (PyTorch 등)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # CPU 버전 예시 (GPU 사용시 변경)
pip install -r requirements.txt
```

### 3-4. Spring Boot 배포 (Java 17)
*   **경로**: `/home/ubuntu/springboot`
*   **파일**: 빌드된 `.jar` 파일 (예: `app.jar`) 업로드

---

## 4. 프로세스 관리 (PM2 활용)

Node.js 기반의 PM2를 사용하여 모든 프로세스를 한눈에 관리하고 자동 재시작을 구성합니다.
> **참고:** [PM2로 Python 배포하기 (Velog)](https://velog.io/@markyang92/pm2-python-flask)

### 4-1. PM2 설치
```bash
# Node.js 설치 (LTS 버전)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs

# PM2 설치
sudo npm install -g pm2
```

### 4-2. ecosystem.config.js 작성
홈 디렉토리(`/home/ubuntu`)에 설정 파일을 만듭니다.

```javascript
// ecosystem.config.js
module.exports = {
  apps : [
    {
      name: "main-api",
      script: "/home/ubuntu/main-api/package/m5/server.py", // 실제 실행 파일 경로 확인 필요
      interpreter: "/home/ubuntu/main-api/venv/bin/python",
      env: {
        PORT: 8005,
        PYTHONPATH: "/home/ubuntu/main-api" // 모듈 인식을 위해 필요할 수 있음
      }
    },
    {
      name: "p2pnet-api",
      script: "/home/ubuntu/p2pnet-api/package/m3/run.py", // 실행 파일명 가정
      interpreter: "/home/ubuntu/p2pnet-api/venv/bin/python",
      env: {
        PORT: 8001
      }
    },
    {
      name: "springboot",
      script: "java",
      args: "-jar /home/ubuntu/springboot/app.jar",
      exec_interpreter: "none", // Java는 인터프리터 없이 실행
      exec_mode: "fork"
    }
  ]
}
```

### 4-3. 실행 및 자동 실행 등록
```bash
# 실행
pm2 start ecosystem.config.js

# 상태 확인
pm2 list
pm2 monit

# 서버 재부팅 시 자동 실행 등록
pm2 save
pm2 startup
# (출력되는 sudo 명령어 복사해서 실행)
```

---

## 5. Nginx 설정 (Reverse Proxy)

외부(80 포트) 요청을 내부 포트로 분배합니다.
> **참고:** [Nginx 리버스 프록시 설정 예시 (Tistory)](https://7942yongdae.tistory.com/136)

### 5-1. 설치 및 설정
```bash
sudo apt install -y nginx
```

`/etc/nginx/sites-available/default` 파일 수정:

```nginx
server {
    listen 80;
    server_name your-domain.com; # 도메인이 없으면 public IP

    # 1. 메인 백엔드 (Spring Boot)
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 2. Main API (FastAPI)
    location /api/main/ {
        # URL 뒤에 /를 붙여서 경로를 제거하거나 그대로 넘길지 결정 필요
        proxy_pass http://localhost:8005/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 3. P2PNet API
    location /api/p2p/ {
        proxy_pass http://localhost:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5-2. 적용
```bash
sudo nginx -t  # 문법 검사
sudo systemctl restart nginx
```

