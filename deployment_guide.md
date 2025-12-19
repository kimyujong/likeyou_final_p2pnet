# 배포 및 테스트 가이드

## 1. Server B (GPU 서버)
`m3/server.py`가 수정되었습니다. 서비스를 재시작하여 정적 파일 서빙 설정을 적용하세요.

```bash
# m3 디렉토리로 이동 (필요시)
cd /home/ubuntu/p2pnet-api/m3

# PM2 프로세스 재시작
pm2 restart m3-gpu
```

## 2. Server A (Main 서버)
Nginx 설정 파일(`nginx_config.conf`)을 루트 디렉토리에 생성해 두었습니다. 이 내용을 참고하여 `/etc/nginx/sites-available/likeyou` 파일을 수정하세요.

```bash
# Nginx 설정 수정
sudo vi /etc/nginx/sites-available/likeyou
# (nginx_config.conf 파일의 location /videos/ 블록을 복사해서 붙여넣으세요)

# 설정 문법 검사
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

## 3. Frontend (Local/Server A)
프론트엔드 코드가 수정되었습니다 (`CCTVMonitoring.tsx`, `LoginPage.tsx`).

```bash
# 로컬 개발 환경인 경우
npm start

# 배포 환경인 경우 (빌드 후 배포)
npm run build
# 빌드 결과물을 웹 서버 경로로 이동 (예: /var/www/html)
```

## 4. 최종 확인 체크리스트
1. **로그인**: `LoginPage`에서 로그인 시 콘솔에 CCTV 분석 요청 로그가 찍히는지 확인.
2. **CCTV 화면**: 대시보드 진입 시 CCTV 썸네일에 영상이 나오는지 확인 (마우스 오버 시 재생).
3. **상세 모달**: 클릭 시 모달창에서 영상이 자동 재생되는지 확인.
