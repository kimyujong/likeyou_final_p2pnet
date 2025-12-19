# 실시간 CCTV 모니터링 기능 구현 작업 리스트

현재 시스템은 CCTV 화면이 목업(Mockup) 상태이며, 실제 영상 파일을 연결하여 웹에서 볼 수 있도록 구현해야 합니다.
이를 위해 Server B(GPU)에서 영상을 서빙하고, Server A(Main)를 거쳐 프론트엔드에서 재생하는 구조를 만듭니다.

## 1. 백엔드 (Server B: GPU 서버) - `m3/server.py`
- [ ] **정적 파일 서빙 설정 (`StaticFiles`)**
    - `FastAPI`의 `StaticFiles`를 사용하여 `/home/ubuntu/storage/m3` 폴더를 `/videos` URL로 노출합니다.
    - 이를 통해 `http://ServerB:8003/videos/CCTV_01.mp4` 주소로 영상 접근이 가능해집니다.

## 2. 인프라 (Server A: Main 서버) - `Nginx` 설정
- [ ] **리버스 프록시 설정 추가**
    - 프론트엔드(`likeyousafety.cloud`)에서 `/videos/`로 요청 시 Server B(`http://<ServerB_IP>:8003/videos/`)로 전달하도록 설정합니다.
    - **파일 수정**: `/etc/nginx/sites-available/likeyou` (또는 default)
    ```nginx
    location /videos/ {
        proxy_pass http://<Server_B_Private_IP>:8003/videos/;
        proxy_set_header Host $host;
        # ... (버퍼링 해제 등 옵션 추가)
    }
    ```

## 3. 프론트엔드 - `CCTVMonitoring.tsx`
- [ ] **영상 URL 매핑 로직 추가**
    - CCTV ID(`CCTV-01`)를 기반으로 영상 URL(`/videos/CCTV_01.mp4`)을 생성하는 함수 구현.
- [ ] **그리드 뷰 (썸네일) 수정**
    - 기존 가짜 화면(`div`)을 `<video>` 태그로 교체.
    - 속성: `muted`, `playsInline`, `preload="metadata"` (자동 재생 X, 썸네일 역할).
    - 마우스 오버 시 재생(`onMouseEnter`) 기능 추가 고려.
- [ ] **상세 모달 (재생) 수정**
    - `<video>` 태그로 실제 영상 재생.
    - 속성: `controls`, `autoplay`, `loop` (무한 반복 재생).

## 4. 프론트엔드 - `LoginPage.tsx` (기존 로직 유지/확인)
- [ ] **로그인 시 분석 시작 요청**
    - 앞서 구현한 `startAnalysis`가 로그인 시점에 정상적으로 4개의 CCTV에 대해 호출되는지 확인.
    - 영상 경로 파라미터가 실제 서버 경로(`/home/ubuntu/storage/m3/...`)와 일치하는지 재확인.

## 5. 배포 및 테스트
- [ ] **Server B**: `m3/server.py` 수정 후 재시작 (`pm2 restart m3-gpu`).
- [ ] **Server A**: Nginx 설정 수정 후 재시작 (`sudo systemctl restart nginx`).
- [ ] **프론트엔드**: 코드 수정 후 빌드 및 배포.
- [ ] **최종 확인**:
    1. 로그인 후 대시보드 진입.
    2. CCTV 화면에 영상이 뜨는지 확인.
    3. 영상 클릭 시 모달에서 재생되는지 확인.
    4. 혼잡도 수치가 실시간(3초 주기)으로 변하는지 확인.
