# 🎯 M3 P2PNet 혼잡도 분석 API 배포 TODO LIST

## 📅 프로젝트 개요
- **목표**: M3 P2PNet 모델을 FastAPI로 서빙 + Supabase 연동 + AWS 배포
- **환경**: AWS EC2 1개 (Docker 없이) + Python 3.8
- **나의 역할**: 
  - ✅ **p2pnet-api** (Python 3.8, 포트 8001)
  - M3 P2PNet 혼잡도 분석 모델 서빙
  - 이미지/영상 분석 API
  - Supabase 직접 연동 (분석 결과 저장)
  
- **다른 개발자들**: 
  - SpringBoot :8080 (메인 백엔드)
  - main-api :8000 (다른 3개 ML 모델, Python 3.10)

## 🏗️ 최종 아키텍처
```
[React EC2] (이미 존재)
    ↓
[Backend EC2 1개]
    ├─ SpringBoot :8080 (다른 개발자)
    ├─ main-api :8000 (다른 개발자)
    └─ p2pnet-api :8001 ⭐ 당신 담당
         ├─ M3 P2PNet 모델
         ├─ 이미지/영상 분석
         └─ Supabase 저장
```

---

## Phase 1: 로컬 개발 환경 (1-2일)

### ✅ 1. FastAPI 서버 구축
- [ ] `server.py` 파일 생성
  - [ ] M3CongestionAPI 초기화
  - [ ] `/health` 헬스체크 엔드포인트
  - [ ] `/analyze` 이미지 분석 엔드포인트 (POST)
  - [ ] CORS 설정 (SpringBoot 연동 대비)
- [ ] `requirements.txt` 업데이트
  - [ ] fastapi
  - [ ] uvicorn[standard]
  - [ ] supabase-py
  - [ ] python-dotenv
  - [ ] opencv-python
  - [ ] 기존 M3 패키지들
- [ ] 로컬에서 FastAPI 서버 실행 테스트
  ```bash
  uvicorn server:app --reload --port 8001
  ```
- [ ] Swagger UI 접속 확인 (`http://localhost:8001/docs`)

### ✅ 2. Supabase 데이터베이스 연동
- [ ] Supabase 프로젝트 생성 (https://supabase.com)
- [ ] 데이터베이스 테이블 생성 (SQL Editor에서 실행)
  - [ ] `congestion_logs` 테이블 (분석 결과 저장)
    ```sql
    CREATE TABLE congestion_logs (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      created_at TIMESTAMP DEFAULT NOW(),
      cctv_id VARCHAR(50),
      count INTEGER,
      density FLOAT,
      pct FLOAT,
      risk_level VARCHAR(20),
      alert BOOLEAN,
      video_url TEXT,
      frame_number INTEGER,
      points JSONB
    );
    ```
  - [ ] `alert_history` 테이블 (경보 이력)
    ```sql
    CREATE TABLE alert_history (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      created_at TIMESTAMP DEFAULT NOW(),
      cctv_id VARCHAR(50),
      pct FLOAT,
      risk_level VARCHAR(20),
      alert_message TEXT,
      resolved BOOLEAN DEFAULT FALSE
    );
    ```
- [ ] `.env` 파일 생성 (로컬)
  ```env
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_KEY=your-anon-key
  MODEL_PATH=C:/Users/user/m3_p2pnet/output/org_from_scratch/ckpt/best_mae.pth
  P2PNET_SOURCE=C:/Users/user/m3_p2pnet/p2pnet_source
  MAX_CAPACITY=200
  ```
- [ ] `database.py` 파일 생성
  - [ ] Supabase 클라이언트 초기화
  - [ ] `save_analysis_result()` 함수
  - [ ] `save_alert()` 함수
  - [ ] `get_recent_logs()` 함수 (조회용)
- [ ] DB 연동 테스트
  - [ ] 임시 데이터 삽입 테스트
  - [ ] Supabase 대시보드에서 확인

### ✅ 3. 영상 분석 기능 추가 (새로 추가!)
- [ ] `video_processor.py` 파일 생성
  - [ ] 영상 파일 로드 (로컬 또는 URL)
  - [ ] 프레임 추출 (N프레임마다 샘플링)
  - [ ] 배치 처리 (여러 프레임 동시 분석)
  - [ ] 진행률 추적
- [ ] `server.py`에 영상 분석 API 추가
  - [ ] `/analyze/video` 엔드포인트 (파일 업로드)
    - 영상 파일 받기
    - 프레임별 분석
    - 결과 반환
  - [ ] `/analyze/video-url` 엔드포인트 (URL 방식)
    - S3 또는 서버 URL에서 영상 로드
    - 비동기 처리 (BackgroundTasks)
  - [ ] `/analyze/status/{job_id}` 엔드포인트
    - 분석 진행 상황 조회
- [ ] 영상 분석 결과를 Supabase에 자동 저장
  - [ ] 프레임별 결과 저장
  - [ ] 경보 발생 시 alert_history 저장

### ✅ 4. API에 DB 저장 로직 통합
- [ ] `server.py` 수정
  - [ ] `/analyze` (이미지) → 분석 후 자동 DB 저장
  - [ ] `/analyze/video` (영상) → 프레임별 DB 저장
  - [ ] 경보 발생 시 `alert_history`에 자동 저장
  - [ ] `/logs` 엔드포인트 (최근 분석 결과 조회)
  - [ ] `/alerts` 엔드포인트 (경보 이력 조회)
- [ ] 에러 핸들링 추가
  - [ ] DB 연결 실패 시 처리 (로그만 남기고 계속)
  - [ ] 모델 추론 실패 시 처리
  - [ ] 영상 로드 실패 시 처리

### ✅ 5. 로컬 테스트
- [ ] Postman/Thunder Client 테스트
  - [ ] `/health` 헬스체크
  - [ ] `/analyze` 이미지 업로드 → 분석 → DB 저장 확인
  - [ ] `/analyze/video` 영상 업로드 → 프레임별 분석
  - [ ] Supabase 대시보드에서 데이터 확인
- [ ] 성능 측정
  - [ ] 이미지 10장으로 평균 추론 시간 기록
  - [ ] 영상 1개 (30초)로 처리 시간 측정
  - [ ] 메모리 사용량 확인
- [ ] 테스트 시나리오
  - [ ] 혼잡도 0-25% (안전) 테스트
  - [ ] 혼잡도 76-100% (위험) → 경보 발생 확인
  - [ ] DB에 올바르게 저장되는지 확인

---

## Phase 2: AWS EC2 배포 (1일)

> **참고**: EC2는 이미 팀에서 준비됨. 당신은 `/home/ubuntu/p2pnet-api` 폴더만 담당!

### ✅ 6. EC2 접속 및 확인
- [ ] 팀에서 EC2 접속 정보 받기
  - [ ] EC2 IP 주소
  - [ ] SSH 키페어 (.pem 파일)
  - [ ] 접속 계정 (ubuntu)
- [ ] SSH 접속 테스트
  ```bash
  ssh -i your-key.pem ubuntu@your-ec2-ip
  ```
- [ ] EC2 환경 확인
  - [ ] GPU 확인: `nvidia-smi`
  - [ ] Python 3.8 설치 확인: `python3.8 --version`
  - [ ] 디스크 용량 확인: `df -h`

### ✅ 7. p2pnet-api 폴더 생성 및 파일 업로드
- [ ] EC2에 작업 디렉토리 생성
  ```bash
  ssh -i your-key.pem ubuntu@your-ec2-ip
  cd /home/ubuntu
  mkdir p2pnet-api
  ```
- [ ] 방법 1: Git 사용 (추천)
  ```bash
  cd /home/ubuntu
  git clone your-repo-url p2pnet-api
  ```
- [ ] 방법 2: SCP로 파일 전송 (Windows에서 실행)
  ```bash
  # Windows PowerShell에서
  scp -i your-key.pem -r C:\Users\user\m3_p2pnet\M3_dbtest\* ubuntu@your-ec2-ip:/home/ubuntu/p2pnet-api/
  ```
- [ ] 모델 파일 업로드 (용량 큼, 별도 전송)
  ```bash
  # 모델 파일 디렉토리 생성
  ssh -i your-key.pem ubuntu@your-ec2-ip "mkdir -p /home/ubuntu/p2pnet-api/models"
  
  # 모델 파일 전송
  scp -i your-key.pem C:\Users\user\m3_p2pnet\output\org_from_scratch\ckpt\best_mae.pth ubuntu@your-ec2-ip:/home/ubuntu/p2pnet-api/models/
  ```
- [ ] P2PNet 소스 코드 업로드
  ```bash
  scp -i your-key.pem -r C:\Users\user\m3_p2pnet\p2pnet_source ubuntu@your-ec2-ip:/home/ubuntu/p2pnet-api/
  ```
- [ ] 업로드 확인
  ```bash
  ssh -i your-key.pem ubuntu@your-ec2-ip
  ls -la /home/ubuntu/p2pnet-api/
  ```

### ✅ 8. Python 3.8 가상환경 구축
- [ ] 가상환경 생성
  ```bash
  cd /home/ubuntu/p2pnet-api
  python3.8 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  ```
- [ ] 패키지 설치
  ```bash
  pip install -r requirements.txt
  ```
- [ ] PyTorch GPU 확인
  ```bash
  python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
  ```
- [ ] M3 모듈 로드 테스트
  ```bash
  python -c "from api import M3CongestionAPI; print('M3 import OK')"
  ```

### ✅ 9. 환경변수 설정 (.env 파일)
- [ ] `.env` 파일 생성 (EC2에서)
  ```bash
  cd /home/ubuntu/p2pnet-api
  nano .env
  ```
- [ ] 환경변수 입력 (로컬과 동일, 경로만 수정)
  ```env
  # Supabase (로컬과 동일)
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_KEY=your-anon-key
  
  # 모델 경로 (EC2 경로로 수정!)
  MODEL_PATH=/home/ubuntu/p2pnet-api/models/best_mae.pth
  P2PNET_SOURCE=/home/ubuntu/p2pnet-api/p2pnet_source
  
  # 혼잡도 설정
  MAX_CAPACITY=200
  ALERT_THRESHOLD=50
  ```
- [ ] 파일 권한 설정
  ```bash
  chmod 600 .env
  ```

### ✅ 10. 수동 실행 테스트 (먼저!)
- [ ] 가상환경에서 서버 실행
  ```bash
  cd /home/ubuntu/p2pnet-api
  source venv/bin/activate
  uvicorn server:app --host 127.0.0.1 --port 8001
  ```
- [ ] 다른 터미널에서 테스트
  ```bash
  curl http://localhost:8001/health
  ```
- [ ] 에러 확인 및 수정
  - [ ] 모델 로드 실패 → 경로 확인
  - [ ] 패키지 import 에러 → pip install
  - [ ] Supabase 연결 에러 → .env 확인

### ✅ 11. systemd 서비스 등록
> **참고**: 수동 실행이 성공한 후에 진행!

- [ ] 서비스 파일 생성
  ```bash
  sudo nano /etc/systemd/system/p2pnet-api.service
  ```
  
  **파일 내용:**
  ```ini
  [Unit]
  Description=M3 P2PNet FastAPI Service
  After=network.target

  [Service]
  Type=simple
  User=ubuntu
  WorkingDirectory=/home/ubuntu/p2pnet-api
  Environment="PATH=/home/ubuntu/p2pnet-api/venv/bin"
  ExecStart=/home/ubuntu/p2pnet-api/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
  Restart=always
  RestartSec=3

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] 서비스 활성화 및 시작
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable p2pnet-api
  sudo systemctl start p2pnet-api
  ```
  
- [ ] 서비스 상태 확인
  ```bash
  sudo systemctl status p2pnet-api
  ```
  
- [ ] 로그 실시간 확인
  ```bash
  sudo journalctl -u p2pnet-api -f
  ```

### ✅ 12. Nginx 설정 (다른 개발자와 협업)
> **참고**: Nginx는 이미 설정되어 있을 수 있음. 팀에 확인 후 추가만 하기!

- [ ] 팀에 현재 Nginx 설정 확인
  ```bash
  sudo cat /etc/nginx/sites-available/default
  ```
  
- [ ] p2pnet-api 라우팅 추가 요청
  ```nginx
  # Nginx에 추가할 내용
  location /api/p2pnet {
      rewrite ^/api/p2pnet(.*) $1 break;
      proxy_pass http://127.0.0.1:8001;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_read_timeout 300s;
  }
  ```
  
- [ ] 또는 직접 추가 (권한 있는 경우)
  ```bash
  sudo nano /etc/nginx/sites-available/default
  # 위 내용 추가 후 저장
  sudo nginx -t
  sudo systemctl reload nginx
  ```

---

## Phase 3: 배포 테스트 (반나절)

### ✅ 13. 배포 환경 테스트
- [ ] 내부 테스트 (EC2 내부에서)
  ```bash
  curl http://localhost:8001/health
  curl http://localhost:8001/docs  # Swagger UI 확인
  ```
  
- [ ] 외부 접근 테스트 (로컬 PC에서)
  ```bash
  curl http://your-ec2-ip/api/p2pnet/health
  ```
  
- [ ] Postman으로 API 테스트
  - URL: `http://your-ec2-ip/api/p2pnet/analyze`
  - 이미지 파일 업로드
  - 응답 JSON 확인
  
- [ ] Supabase 대시보드에서 데이터 확인
  - congestion_logs 테이블에 데이터 들어왔는지
  - 시간, cctv_id, count, pct 등 올바른지
  
- [ ] 로그 모니터링
  ```bash
  sudo journalctl -u p2pnet-api -f
  ```

### ✅ 14. 성능 확인
- [ ] GPU 사용 확인
  ```bash
  watch -n 1 nvidia-smi
  ```
  - GPU 메모리 사용량 확인
  - 추론 시 GPU 사용률 확인
  
- [ ] 응답 시간 측정
  - [ ] 이미지 분석: 3초 이내 목표
  - [ ] 영상 분석 (30초 영상): 진행률 표시 확인
  
- [ ] 동시 요청 테스트 (선택)
  - [ ] 2-3개 이미지 동시 전송
  - [ ] 서버 다운 없이 처리되는지 확인

### ✅ 15. 문제 해결 (발생 시)
- [ ] 서비스가 시작 안 될 때
  ```bash
  sudo systemctl status p2pnet-api
  sudo journalctl -u p2pnet-api -n 100
  ```
  
- [ ] DB 연결 실패 시
  - [ ] `.env` 파일 확인
  - [ ] Supabase URL과 Key 재확인
  
- [ ] 모델 로드 실패 시
  - [ ] 모델 파일 경로 확인
  - [ ] GPU 메모리 확인 (`nvidia-smi`)
  
- [ ] 502 Bad Gateway 에러
  - [ ] FastAPI 서버 실행 상태 확인
  - [ ] 포트 8001 사용 중인지 확인
    ```bash
    sudo netstat -tulpn | grep 8001
    ```

---

## Phase 4: SpringBoot 연동 및 통합 테스트 (1일)

### ✅ 16. API 문서 작성 및 공유
- [ ] Swagger UI 문서 확인
  - URL: `http://your-ec2-ip/api/p2pnet/docs`
  - 모든 엔드포인트가 올바르게 표시되는지 확인
  
- [ ] API 명세서 작성 (`API_SPEC.md`)
  ```markdown
  # P2PNet API 명세서
  
  Base URL: http://your-ec2-ip/api/p2pnet
  
  ## Endpoints
  
  ### 1. GET /health
  헬스체크
  
  ### 2. POST /analyze
  이미지 분석
  - Request: multipart/form-data (file)
  - Response: JSON (count, pct, risk_level, ...)
  
  ### 3. POST /analyze/video
  영상 분석
  - Request: multipart/form-data (file) 또는 JSON (video_url)
  - Response: JSON (job_id, status, results)
  ```
  
- [ ] SpringBoot 개발자에게 공유
  - [ ] API Base URL
  - [ ] Postman Collection (선택)
  - [ ] 예제 요청/응답

### ✅ 17. SpringBoot와 통합 테스트
- [ ] SpringBoot 개발자와 협업
  - [ ] SpringBoot에서 FastAPI 호출 테스트
  - [ ] 에러 발생 시 함께 디버깅
  
- [ ] 통합 시나리오 테스트
  1. [ ] React → SpringBoot → FastAPI → DB
  2. [ ] 전체 흐름 정상 작동 확인
  3. [ ] 실제 CCTV 영상으로 End-to-End 테스트
  
- [ ] CORS 문제 발생 시
  ```python
  # server.py에 추가
  from fastapi.middleware.cors import CORSMiddleware
  
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],  # 개발용 (운영에서는 특정 도메인만)
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

---

## Phase 5: 최종 점검 (반나절)

### ✅ 18. 보안 점검
- [ ] `.env` 파일 권한 확인
  ```bash
  chmod 600 /home/ubuntu/p2pnet-api/.env
  ls -la /home/ubuntu/p2pnet-api/.env
  ```
  
- [ ] `.gitignore` 설정 확인
  ```bash
  # .gitignore에 다음 추가
  .env
  *.pth
  __pycache__/
  venv/
  ```

### ✅ 19. 운영 문서 작성
- [ ] `DEPLOYMENT.md` 작성
  ```markdown
  # p2pnet-api 운영 가이드
  
  ## 서비스 재시작
  sudo systemctl restart p2pnet-api
  
  ## 로그 확인
  sudo journalctl -u p2pnet-api -f
  
  ## 모델 재로드 (코드 수정 시)
  1. 코드 업데이트 (git pull 또는 scp)
  2. sudo systemctl restart p2pnet-api
  3. 상태 확인: sudo systemctl status p2pnet-api
  ```
  
- [ ] 주요 명령어 정리
  - [ ] 서비스 시작/중지/재시작
  - [ ] 로그 확인 방법
  - [ ] 문제 발생 시 체크리스트

### ✅ 20. 최종 테스트 및 시연
- [ ] 팀 전체 통합 테스트
  - [ ] React → SpringBoot → FastAPI 전체 흐름
  - [ ] 실제 CCTV 영상으로 분석
  - [ ] 결과가 화면에 올바르게 표시되는지
  
- [ ] 성능 확인
  - [ ] 이미지 10장 연속 처리
  - [ ] 응답 시간 기록
  - [ ] DB 저장 확인
  
- [ ] 최종 시연 준비
  - [ ] 데모 시나리오 작성
  - [ ] 예상 질문 답변 준비

---

## 📌 중요 체크포인트

### 🚨 반드시 확인할 것
- [ ] `.env` 파일이 Git에 커밋되지 않도록 `.gitignore` 설정
- [ ] Supabase anon key 사용 (service key 절대 노출 금지)
- [ ] 모델 파일 경로 (로컬 vs EC2 다름!)
  - 로컬: `C:/Users/user/m3_p2pnet/...`
  - EC2: `/home/ubuntu/p2pnet-api/...`
- [ ] GPU 사용 확인 (`nvidia-smi`)
- [ ] Python 3.8 가상환경 사용 (P2PNet은 3.8 필요!)

### 🎯 성공 기준
- [ ] 로컬에서 FastAPI 서버 정상 실행
- [ ] 이미지 분석 API 작동
- [ ] Supabase에 데이터 저장됨
- [ ] EC2에서 서비스 자동 시작
- [ ] SpringBoot와 통신 성공

---

## 📞 빠른 문제 해결 가이드

### ❌ ModuleNotFoundError
```bash
# 가상환경 활성화 확인
source venv/bin/activate
# 패키지 재설치
pip install -r requirements.txt
```

### ❌ CUDA not available
```bash
# GPU 확인
nvidia-smi
# PyTorch 재설치
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu113
```

### ❌ Supabase 연결 실패
```bash
# .env 파일 확인
cat .env
# URL 끝에 / 없는지 확인
# Key가 정확한지 확인
```

### ❌ 모델 로드 실패
```bash
# 파일 존재 확인
ls -la /home/ubuntu/p2pnet-api/models/best_mae.pth
# 경로가 .env와 일치하는지 확인
```

### ❌ systemd 서비스 시작 실패
```bash
# 로그 확인
sudo journalctl -u p2pnet-api -n 50
# 수동 실행으로 에러 확인
cd /home/ubuntu/p2pnet-api
source venv/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8001
```

---

## 🎉 완료 후 최종 확인

### ✅ 로컬 개발 완료
- [ ] FastAPI 서버 실행됨
- [ ] Swagger UI 접근 가능
- [ ] 이미지 분석 작동
- [ ] Supabase에 데이터 저장됨

### ✅ EC2 배포 완료
- [ ] SSH 접속 가능
- [ ] p2pnet-api 서비스 실행 중
- [ ] 외부에서 API 호출 가능
- [ ] 로그 정상 출력

### ✅ 통합 테스트 완료
- [ ] SpringBoot → FastAPI 통신 성공
- [ ] React → SpringBoot → FastAPI 전체 흐름 작동
- [ ] 실제 CCTV 영상 분석 성공
- [ ] 팀 시연 완료

---

## 📝 나의 담당 범위 요약

### ✅ 내가 하는 것
- **p2pnet-api** (Python 3.8, 포트 :8001)
- 이미지/영상 분석 API
- M3 P2PNet 모델 서빙
- Supabase 연동
- `/home/ubuntu/p2pnet-api/` 폴더 관리

### ❌ 내가 하지 않는 것
- SpringBoot (다른 개발자)
- main-api (다른 개발자)
- React 프론트엔드 (이미 완성)
- Nginx 전체 설정 (팀 협업)
- EC2 인스턴스 생성 (팀에서 준비)

---

**⏱️ 예상 소요 시간**: 총 3-4일
- Phase 1: 1-2일 (로컬 개발)
- Phase 2: 1일 (EC2 배포)
- Phase 3: 반나절 (테스트)
- Phase 4: 반나절 (통합)
- Phase 5: 반나절 (최종 점검)

**🎯 우선순위**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

**🚀 지금 바로 Phase 1부터 시작하세요!**

다음 단계: `server.py` 파일 작성

