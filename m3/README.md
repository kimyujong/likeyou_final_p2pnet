# M3 CCTV 혼잡도 경보 시스템

P2PNet 기반 실시간 군중 계수 및 4단계 혼잡도 경보 시스템

## 📦 모듈 구조

```
M3/
├── __init__.py          # 패키지 초기화
├── constants.py         # 상수 정의 (CongestionLevel 등)
├── model.py             # P2PNet 모델 로더
├── analyzer.py          # M3CongestionAnalyzer (핵심)
├── alert.py             # AlertSystem (경보)
├── api.py               # M3CongestionAPI (FastAPI용)
├── utils.py             # 유틸리티 함수
├── config.py            # 설정 클래스
└── README.md            # 이 파일
```

## 🚀 빠른 시작

### 1. 기본 사용 (Python)

```python
from M3 import M3CongestionAPI

# API 초기화
api = M3CongestionAPI(
    model_path='path/to/best_mae.pth',
    p2pnet_source_path='path/to/p2pnet_source',
    max_capacity=200
)

# 이미지 분석
with open('cctv_image.jpg', 'rb') as f:
    image_bytes = f.read()

result = api.analyze_image_bytes(image_bytes)
print(f"인원: {result['count']}명")
print(f"혼잡도: {result['pct']}%")
print(f"등급: {result['risk_level']}")
```

### 2. FastAPI 서버

```python
from fastapi import FastAPI, File, UploadFile
from M3 import M3CongestionAPI

app = FastAPI()

# M3 API 초기화
m3_api = M3CongestionAPI(
    model_path='C:/Users/user/m3_p2pnet/output/org_from_scratch/ckpt/best_mae.pth',
    p2pnet_source_path='C:/Users/user/m3_p2pnet/p2pnet_source',
    max_capacity=200
)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    result = m3_api.analyze_image_bytes(contents)
    return result
```

### 3. 비디오 처리

```python
import cv2
from M3 import M3Config
from M3.api import M3CongestionAPI

# API 초기화
api = M3CongestionAPI(**M3Config.get_model_config(), 
                      max_capacity=200)

# 비디오 처리
cap = cv2.VideoCapture('cctv_video.mp4')

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    result = api.analyze_frame(frame)
    print(f"혼잡도: {result['pct']:.1f}% - {result['risk_level'].korean}")
```

## 📊 출력 형식

```json
{
  "count": 176,
  "density": 0.000085,
  "pct": 88.0,
  "risk_level": "위험",
  "risk_level_en": "DANGER",
  "alert": true,
  "alert_message": "🚨 혼잡도 경보...",
  "points": [[x1, y1], [x2, y2], ...]
}
```

## 🎯 혼잡도 등급

| 등급 | PCT | 설명 |
|------|-----|------|
| 🟢 안전 | 0-25% | 여유 공간 충분 |
| 🟡 주의 | 26-50% | 약간 혼잡 |
| 🟠 경고 | 51-75% | 혼잡 주의 |
| 🔴 위험 | 76-100% | 매우 혼잡 |

## ⚙️ 설정

`config.py`에서 설정 변경:

```python
MAX_CAPACITY = 200        # 최대 수용 인원
ALERT_THRESHOLD = 50      # 경보 임계값 (%)
ALERT_COOLDOWN = 60       # 경보 쿨다운 (초)
ROI_POLYGON = None        # ROI 영역 (None=전체)
```

## 🔧 ROI 설정

특정 영역만 분석하려면:

```python
# 다각형 좌표 설정
ROI_POLYGON = [
    (400, 200),    # 좌상단
    (1520, 200),   # 우상단
    (1520, 880),   # 우하단
    (400, 880)     # 좌하단
]

api = M3CongestionAPI(
    ...,
    roi_polygon=ROI_POLYGON
)
```

## 📝 성능

- **MAE**: 7.03 (ShanghaiTech 52.74 대비 7배 우수)
- **학습 데이터**: 92,368개 (AI Hub CCTV)
- **추론 속도**: ~13ms/frame (GPU)

## 🌐 배포

### Docker

```dockerfile
FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04
COPY M3/ /app/M3/
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### AWS

- **EC2**: p3.2xlarge (V100 GPU) - FastAPI 서버
- **ECS**: SpringBoot 백엔드
- **S3**: 분석 결과 저장
- **CloudWatch**: 로그 및 모니터링

## 📄 라이선스

MIT License

## 👥 개발자

CCTV Congestion Analysis Team

