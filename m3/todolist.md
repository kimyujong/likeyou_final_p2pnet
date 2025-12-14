# 🏗️ 하이브리드 서버 구성 가이드 (CPU + GPU Spot)

## 🎯 목표
- **CPU 서버 (`t3.large`)**: `m1`, `m2`, `m4`, `m5` 및 메인 백엔드 실행 (상시 가동)
- **GPU 서버 (`g4dn.xlarge` Spot)**: `m3` (P2PNet) 전용 실행 (필요 시 가동)

---

## 1. GPU 서버 생성 (AWS 콘솔)
- [ ] **인스턴스 시작**
  - **AMI**: `Deep Learning OSS Nvidia Driver AMI GPU PyTorch` 검색 후 최신 버전(Ubuntu 24.04 등) 선택
  - **유형**: `g4dn.xlarge`
  - **★ 스팟 인스턴스 요청 (Request Spot Instances)**: **체크 해제 (On-Demand 사용)** ❌
  - **보안 그룹**: `TCP 8003` (M3 API용), `SSH 22` 허용
  - **키 페어**: 기존 키 사용

## 2. 코드 분리 및 이관
- [ ] **CPU 서버 (기존)**
  - 여기서 `m3` 관련 프로세스는 종료 (`python m3/server.py` 중지)
  - 나머지 `m1, m2, m4, m5`는 그대로 유지

- [ ] **GPU 서버 (신규)**
  - [ ] **접속**: `ssh -i key.pem ubuntu@GPU_SERVER_IP`
  - [ ] **코드 다운로드**:
    ```bash
    # (로컬 PC에서 수행) m3 폴더만 보내도 됨
    scp -i key.pem -r p2pnet-api/m3 ubuntu@GPU_SERVER_IP:/home/ubuntu/
    # 또는 전체 전송
    scp -i key.pem -r p2pnet-api ubuntu@GPU_SERVER_IP:/home/ubuntu/
    ```
  - [ ] **영상 파일 전송**: `video/*.mov` 파일들도 GPU 서버로 전송 필수!

## 3. GPU 서버 환경 세팅 (Python 3.8 필수)
- [ ] **Conda 가상환경 생성** (P2PNet 호환성 위해 3.8 사용)
  ```bash
  conda create -n p2pnet python=3.8 -y
  source activate p2pnet
  ```
- [ ] **패키지 설치**
  ```bash
  cd p2pnet-api/m3
  # PyTorch GPU 버전 설치 (CUDA 11.8 호환)
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  # 나머지 패키지 설치
  pip install -r requirements.txt
  ```
- [ ] **OpenCV 의존성 설치** (ImportError 대비)
  ```bash
  sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
  ```
- [ ] **.env 설정**: DB 연결 정보(`SUPABASE_URL` 등) 설정
- [ ] **서버 실행**
  ```bash
  python server.py
  # 정상 실행 시: Uvicorn running on http://0.0.0.0:8003
  ```

## 4. 연동 및 테스트
- [ ] **API 호출 주소 변경**
  - 프론트엔드나 메인 서버에서 `m3`를 호출하는 주소를 `localhost:8003` -> `http://GPU_SERVER_IP:8003`으로 변경
- [ ] **테스트**
  ```bash
  # 로컬 PC에서 호출
  curl -X POST "http://GPU_SERVER_IP:8003/control/start?cctv_no=CCTV-01&interval_seconds=10"
  ```
- [ ] **성능 확인**: 로그에서 분석 속도가 0.5초 내외인지 확인 (`g4dn` 성능)

## 💡 운영 팁
- **비용 절감**: 사용하지 않을 때는 인스턴스 상태를 **중지(Stop)** 하세요. (데이터 유지됨, 서버 비용 0원)
- **IP 관리**: 서버를 껐다 켜면 IP가 바뀔 수 있으니, `Elastic IP`를 쓰거나 매번 IP를 확인해야 합니다.
