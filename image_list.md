# 이미지 기반 CCTV(78개) 적용 작업 순서

목표
- **CCTV_01~CCTV_04**: 기존처럼 **영상(mp4)** 기반으로 화면 표시 및 분석
- **CCTV_05~CCTV_82**: **단일 이미지(jpg)** 를 화면에 “영상처럼” 표시
- **혼잡도 표시값**: CCTV_05~CCTV_82는 **로그인 시 1회** 이미지 분석 결과를 **프론트에서만** 적용 (DB 저장 X)
- **DB**: 기존 더미 생성 로직은 그대로 유지 (DAT_Crowd_Detection에 임의 값 저장)

---

## 0. 사전 정보(고정 규칙)
- **이미지 저장 경로(Server B)**: `/home/ubuntu/storage/m3/image/`
- **이미지 파일명 규칙**: `dash (1).jpg` ~ `dash (78).jpg`
- **대상 CCTV 범위**: `CCTV_05` ~ `CCTV_82`
- **매핑 규칙**:
  - `dash (1).jpg`  → `CCTV_05`
  - `dash (78).jpg` → `CCTV_82`

---

## 1. 인프라/파일 준비 (Server B)
1) S3 → Server B로 이미지 배치 업로드/동기화
- 최종 위치가 `/home/ubuntu/storage/m3/image/`가 되도록 준비
- 파일명 공백/괄호 포함: `dash (1).jpg` 형태 유지

2) 파일 존재/권한 확인
- `ls -al /home/ubuntu/storage/m3/image/`
- 웹서버/프로세스가 읽을 수 있는 권한인지 확인

---

## 2. 백엔드(Server B: m3) - 정적 이미지 서빙 추가
목표
- 프론트에서 이미지가 로드될 수 있도록 **HTTP 경로 제공**

작업
- `m3/server.py`에 이미지 정적 서빙을 추가
  - 예: `app.mount("/images", StaticFiles(directory="/home/ubuntu/storage/m3/image"), name="images")`

검증
- 브라우저에서 아래 URL이 열리는지 확인
  - `https://api.likeyousafety.cloud/images/dash%20(1).jpg`
  - (공백은 URL 인코딩 `%20`)

---

## 3. 백엔드(Server B: m3) - “로그인 시 1회” 이미지 배치 분석 API 추가
목표
- CCTV_05~CCTV_82에 대해 **이미지 78장 1회 분석**
- 결과를 **JSON으로 반환**
- **DB 저장은 하지 않음**

작업
1) 신규 엔드포인트 추가 (예: `POST /control/analyze-images-once`)
2) 내부 로직
- `dash (1).jpg` ~ `dash (78).jpg` 파일 번호에 매핑된 랜덤 혼잡도 값 생성
- **실제 AI 분석은 생략** (응답 속도 개선)
- **High (60~75%)**: 1~6, 8~11, 14~20, 24, 25, 28~30, 53, 55
- **Mid (20~50%)**: 7, 12, 13, 27, 32, 39, 48, 51, 52, 54, 56, 57
- **Low (0~10%)**: 나머지
- 결과 구조 예시
  - `{"CCTV_05": {"density": 12, "risk_level": "안전"}, ...}`

주의
- 이 API는 호출 비용이 있으므로 **로그인 시 1회만 호출**하도록 프론트에서 제한
- 처리 시간이 길면 타임아웃 고려(서버/프록시)

검증
- `curl` 또는 Swagger(`/docs`)에서 호출하여 78개가 반환되는지 확인

---

## 4. 프론트엔드 - 이미지/영상 렌더링 분기 및 값 병합
목표
- CCTV_01~04: `<video>`
- CCTV_05~82: `<img>`를 영상처럼 보이게 UI 적용
- 혼잡도 표시 우선순위
  1) 로그인 시 받은 이미지 분석 결과(메모리 state)
  2) 기존 DB 기반 `getCrowdSummary()` 값(=더미 포함)

작업
1) `LoginPage.tsx`
- 로그인 성공 후:
  - 기존 `/control/start` (CCTV_01~04) 호출 유지
  - 추가로 `/control/analyze-images-once` 1회 호출
  - 응답 결과를 전역 상태(예: context/zustand/recoil) 또는 상위 컴포넌트 state에 저장

2) `CCTVMonitoring.tsx`
- CCTV 목록 렌더링 시 모드 분기
  - CCTV_01~04: `videoUrl = https://api.likeyousafety.cloud/videos/CCTV_01.mp4`
  - CCTV_05~82: `imageUrl = https://api.likeyousafety.cloud/images/dash%20(1).jpg` (매핑 적용)
- 혼잡도 병합
  - `if (imageResult[cctvIdx]) density = imageResult[cctvIdx].density else density = crowdSummaryDensity`

검증
- 그리드: CCTV_05~82가 이미지로 표시되고 LIVE UI가 유지되는지
- 모달: CCTV_05~82는 이미지가 크게 보이는지(영상 컨트롤 불필요)
- 혼잡도: 로그인 직후 이미지 분석 결과가 화면에 반영되는지

---

## 5. 배포/재시작 및 최종 테스트
1) Server B
- 코드 반영 후 `pm2 restart m3-gpu`

2) Nginx (api.likeyousafety.cloud)
- `/images/` 경로가 Server B로 프록시되도록 설정 필요 시 추가
  - `/videos/`와 동일한 방식으로 `/images/` 추가

3) 프론트
- 빌드/배포 후 실제 도메인에서 확인

최종 확인 체크리스트
- [ ] `https://api.likeyousafety.cloud/images/dash%20(1).jpg` 접속 OK
- [ ] 로그인 시 이미지 배치 분석 API 1회 호출됨
- [ ] CCTV_05~82는 이미지가 표시됨(영상처럼 보이게)
- [ ] CCTV_01~04는 영상이 재생됨
- [ ] CCTV_05~82 혼잡도는 로그인 직후 값으로 표시됨(페이지 새로고침 시 초기화되는지 정책 확인)
