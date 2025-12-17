# AWS 하이브리드 서버 배포 체크리스트 (CPU + GPU)

본 문서는 비용 효율성과 성능을 동시에 잡기 위해 **CPU 서버(메인)**와 **GPU 서버(P2PNet 전용)**를 분리하여 운영하는 작업 순서입니다.

*   **CPU 서버**: 상시 가동. 웹 서버, 경량 AI 모델(m1, m2, m4, m5), DB 연결 등을 담당합니다.
*   **GPU 서버**: 선택적 가동. 무거운 딥러닝 모델(m3: P2PNet)을 전담하여 고속 처리를 보장합니다.

> **참고 자료 모음**
> *   [AWS 공식 문서: EC2 인스턴스에서 스왑 메모리 설정](https://repost.aws/ko/knowledge-center/ec2-memory-swap-file)
> *   [PM2 공식 문서: Ecosystem File 설정](https://pm2.keymetrics.io/docs/usage/application-declaration/)
> *   [Certbot: Nginx on Ubuntu](https://certbot.eff.org/instructions?ws=nginx&os=ubuntufocal)

## 1. 서버 아키텍처 및 포트 계획

**인프라 전략**: Hybrid Cloud (CPU Main + GPU Sub)

| 서버 구분 | 인스턴스 타입 | OS | 포함 모듈 | 주요 역할 |
| :--- | :--- | :--- | :--- | :--- |
| **Server A (Main)** | `t3.large` | Ubuntu 22.04 | Main API (m1, m2, m4, m5)<br>Spring Boot<br>Nginx | 웹 서비스, 경량 분석, API 게이트웨이 |
| **Server B (GPU)** | `g4dn.xlarge` | Ubuntu 24.04 (DL AMI) | P2PNet API (m3) | 인구 밀집도 분석 (고부하 작업) |

### 포트 구성

| 서비스 명 | 실행 서버 | 언어/버전 | 경로 | 내부 포트 | 비고 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Main API** | Server A | Python 3.10 | `/home/ubuntu/main-api` | `8005` (m5)<br>`8002` (m2)<br>`8004` (m4) | FastAPI 통합 |
| **P2PNet API** | **Server B** | Python 3.8 | `/home/ubuntu/p2pnet-api` | `8003` | **외부 IP로 호출** |
| **Spring Boot** | Server A | Java 17 | `/home/ubuntu/springboot` | `8080` | 메인 백엔드 |
| **Nginx** | Server A | - | - | `80`, `443` | 리버스 프록시 / SSL |

---

## 2. Server A: 메인 CPU 서버 설정

### 2-1. 인스턴스 생성 및 필수 패키지
*   **OS**: Ubuntu Server 22.04 LTS
*   **Type**: `t3.large` (메모리 8GB 권장)

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 기본 도구 및 Java 17 설치
sudo apt install -y git curl unzip build-essential awscli openjdk-17-jdk

# Python 3.10 가상환경 패키지
sudo apt install -y python3.10-venv python3.10-dev
```

### 2-2. Swap 메모리 설정 (필수)
`t3.large`라도 AI 모델 여러 개를 동시에 띄우면 메모리가 부족할 수 있습니다.

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2-3. 애플리케이션 배포 (Git Clone)
`main_package` 리포지토리를 클론하여 필요한 모듈만 실행합니다.

```bash
# 디렉토리 생성
mkdir -p /home/ubuntu/main-api
mkdir -p /home/ubuntu/p2pnet-api
mkdir -p /home/ubuntu/springboot

# 1. Main API Clone
git clone https://github.com/kimyujong/likeyou_final_mainapi.git /home/ubuntu/main-api

# 2. 가상환경 생성 (Python 3.10)
cd /home/ubuntu/main-api
python3.10 -m venv venv
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. .env 설정 (Supabase 등)
vi .env
```

### 2-4. Spring Boot & 리소스 설정
S3에서 모델 파일과 Jar 파일을 다운로드합니다. (IAM Role 권한 필요)

```bash
mkdir -p /home/ubuntu/storage
# S3 다운로드 예시
aws s3 cp s3://likeyou-storage/m4 /home/ubuntu/storage/m4 --recursive
aws s3 cp s3://likeyou-storage/m5/total_weather.xlsx /home/ubuntu/storage/
aws s3 cp s3://likeyou-storage/jar/app.jar /home/ubuntu/springboot/app.jar
```

### 2-5. PM2 프로세스 관리 (Server A)
`ecosystem.config.js`를 작성하여 m1, m2, m4, m5, SpringBoot를 관리합니다. **(m3 제외)**

```javascript
module.exports = {
  apps : [
    {
      name: "m1-road",
      script: "/home/ubuntu/main-api/m1/server.py",
      interpreter: "/home/ubuntu/main-api/venv/bin/python",
      cwd: "/home/ubuntu/main-api",
      env: { PORT: 8000, PYTHONPATH: "/home/ubuntu/main-api" }
    },
    {
      name: "m5-predict",
      script: "/home/ubuntu/main-api/m5/server.py",
      interpreter: "/home/ubuntu/main-api/venv/bin/python",
      cwd: "/home/ubuntu/main-api",
      env: { PORT: 8005, PYTHONPATH: "/home/ubuntu/main-api" }
    },
    {
      name: "m2-route",
      script: "/home/ubuntu/main-api/m2/server.py",
      interpreter: "/home/ubuntu/main-api/venv/bin/python",
      cwd: "/home/ubuntu/main-api",
      env: { PORT: 8002, PYTHONPATH: "/home/ubuntu/main-api" }
    },
    {
      name: "m4-fall",
      script: "/home/ubuntu/main-api/m4/server.py",
      interpreter: "/home/ubuntu/main-api/venv/bin/python",
      cwd: "/home/ubuntu/main-api",
      env: { PORT: 8004, PYTHONPATH: "/home/ubuntu/main-api" }
    }
    /*{
      name: "springboot",
      script: "java",
      args: "-jar /home/ubuntu/springboot/app.jar",
      exec_interpreter: "none",
      exec_mode: "fork"
    }*/
  ]
}
```

---

## 3. Server B: GPU 서버 설정 (P2PNet 전용)

### 3-1. 인스턴스 생성
*   **AMI**: `Deep Learning Base AMI with Single CUDA` (Ubuntu 22.04)
    *   *NVIDIA 드라이버와 CUDA만 설치되어 있어, 원하는 버전의 PyTorch를 설치하기에 가장 적합합니다.*
*   **Type**: `g4dn.xlarge` (Tesla T4 GPU)
*   **Security Group**: `TCP 8003` (외부 접근 허용), `SSH 22`

### 3-2. 환경 세팅 (Conda)
DL AMI는 Conda가 기본 설치되어 있습니다. Python 3.8 환경을 만듭니다.

```bash
# Conda 환경 생성
conda create -n p2pnet python=3.8 -y
conda activate p2pnet

# PyTorch 1.13.1 설치 (CUDA 11.7 호환, 튜닝 환경과 동일)
pip install torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1+cu117 --extra-index-url https://download.pytorch.org/whl/cu117
```

### 3-3. 코드 배포 (M3 Only)
로컬이나 Git에서 코드를 가져옵니다.

```bash
# 디렉토리 생성
mkdir -p /home/ubuntu/p2pnet-api

# Clone
git clone https://github.com/kimyujong/likeyou_final_p2pnet.git /home/ubuntu/p2pnet-api

# 의존성 설치
cd /home/ubuntu/p2pnet-api/m3
pip install -r requirements.txt

# OpenCV 라이브러리 설치
sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
```

### 3-4. .env 및 실행
GPU 서버용 `.env`를 설정하고 서버를 실행합니다.

```bash
# .env 설정 (DB 정보 등)
vi .env

# 실행 테스트
python server.py
# -> Uvicorn running on http://0.0.0.0:8003
```

### 3-5. PM2 설정 (Server B)
GPU 서버에서도 PM2를 사용하여 백그라운드 실행 및 자동 재시작을 설정합니다.

```bash
# Node.js & PM2 설치
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# 실행
pm2 start /home/ubuntu/p2pnet-api/m3/server.py --name "m3-gpu" --interpreter python
pm2 save
pm2 startup
```

---

## 4. 서버 간 연동 및 도메인 설정

### 4-1. Main Server (A) Nginx 설정 수정
Main 서버의 Nginx가 `/ai/m3` 요청을 GPU 서버(B)로 전달하도록 설정하거나, 클라이언트가 직접 GPU 서버 IP를 호출하도록 합니다.

**방법 A: Nginx 리버스 프록시 (추천)**
GPU 서버 IP가 바뀌어도 클라이언트는 메인 도메인만 알면 됩니다.

```nginx
# /etc/nginx/sites-available/likeyou

server {
    listen 80;
    
    # 1. 메인 API (Spring Boot)
    location /api {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 2. 각 모듈별 직접 접근 (테스트용)
    location /m2 {
        rewrite ^/m2/(.*) /m2/$1 break; # m2는 prefix가 /m2라 그대로 전달
        proxy_pass http://localhost:8002;
    }
    
    location /m4 {
        # m4는 prefix가 없으므로 경로를 지우고 전달해야 함 (/m4/start -> /start)
        rewrite ^/m4/(.*) /$1 break; 
        proxy_pass http://localhost:8004;
    }
}


```

### 4-2. IP 관리 주의사항
*   **Elastic IP**: GPU 서버를 껐다 켤 때마다 IP가 바뀌는 것을 방지하려면 Elastic IP를 할당하세요.
*   **비용 관리**: `g4dn.xlarge`는 시간당 비용이 높으므로, 사용하지 않는 야간에는 **Stop(중지)** 상태로 두는 것이 좋습니다.

---

## 요약 체크리스트

- [ ] **Server A (CPU)**: `t3.large` 생성 및 기본 설정
- [ ] **Server A**: Main API (m1, m2, m4, m5) 및 Spring Boot 배포
- [ ] **Server A**: Nginx 및 SSL 설정
- [ ] **Server B (GPU)**: `g4dn.xlarge` 생성 (DL AMI 사용)
- [ ] **Server B**: Python 3.8 환경 및 M3 (P2PNet) 배포
- [ ] **연동**: Server A Nginx -> Server B 포워딩 설정
