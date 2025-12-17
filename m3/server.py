"""
M3 P2PNet FastAPI 서버

CCTV 혼잡도 분석 API 서버
- 이미지 분석
- 영상 분석
- Supabase 연동
"""

import os
import sys
import logging
from typing import Optional
from datetime import datetime
import traceback
import threading

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import cv2
import numpy as np
from dotenv import load_dotenv

from pathlib import Path

env_path = Path("/home/ubuntu/p2pnet-api/.env")
# env_path = Path("C:/Users/kyj/OneDrive/Desktop/p2pnet_package/m3/.env")
load_dotenv(dotenv_path=env_path) # test

# M3 모듈 import
from api import M3CongestionAPI
from constants import CongestionLevel
from database import get_db, save_detection
from video_processor import VideoProcessor
from dummy_generator import DummyGenerator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="M3 P2PNet API",
    description="CCTV 혼잡도 분석 API - P2PNet 기반",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용, 운영에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CCTV ID 매핑 (제거됨 - DB 조회 방식으로 변경)
# CCTV_MAPPING = {}

# 전역 변수
m3_api = None
dummy_thread_started = False  # 더미 스레드 실행 여부 체크

# Pydantic 모델
class AnalysisResponse(BaseModel):
    """분석 결과 응답 모델"""
    count: int
    density: float
    pct: float
    risk_level: str
    risk_level_en: str
    alert: bool
    alert_message: Optional[str] = None
    timestamp: str
    cctv_no: Optional[str] = None


class VideoAnalysisRequest(BaseModel):
    """영상 분석 요청 모델"""
    video_url: Optional[str] = None
    cctv_no: Optional[str] = "CCTV-01"
    frame_interval: int = 120  # N프레임마다 분석
    max_capacity: Optional[int] = None

# 더미 생성기 실행 함수
def run_dummy_generator():
    try:
        logger.info("🤖 Starting Dummy Data Generator in background...")
        generator = DummyGenerator()
        generator.run()
    except Exception as e:
        logger.error(f"❌ Dummy Generator failed: {e}")

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행"""
    global m3_api
    
    try:
        logger.info("🚀 M3 P2PNet API 서버 시작 중...")
        
        # 1. 더미 생성기 백그라운드 실행 (Daemon Thread)
        # 사용자의 요청으로 잠시 비활성화 (P2PNet 단독 테스트)
        # dummy_thread = threading.Thread(target=run_dummy_generator, daemon=True)
        # dummy_thread.start()
        
        # 2. 환경변수 확인
        model_path = os.getenv('MODEL_PATH')
        p2pnet_source = os.getenv('P2PNET_SOURCE')
        max_capacity = int(os.getenv('MAX_CAPACITY', '200'))
        
        if not model_path or not p2pnet_source:
            raise ValueError("환경변수 MODEL_PATH, P2PNET_SOURCE가 설정되지 않았습니다.")
        
        logger.info(f"📍 모델 경로: {model_path}")
        logger.info(f"📍 P2PNet 소스: {p2pnet_source}")
        logger.info(f"📊 최대 수용 인원: {max_capacity}명")
        
        # 3. M3 API 초기화
        m3_api = M3CongestionAPI(
            model_path=model_path,
            p2pnet_source_path=p2pnet_source,
            device='cuda',
            max_capacity=max_capacity,
            roi_polygon=None,  # 필요시 설정
            alert_threshold=50
        )
        
        # 4. Supabase 연결 확인 및 DB 초기화
        db = get_db()
        if db.is_enabled():
            logger.info("✅ Supabase 연결 완료!")
        else:
            logger.warning("⚠️ Supabase 미연결 (DB 기능 비활성화)")
        
        logger.info("✅ M3 P2PNet API 초기화 완료! (분석 대기 중: /control/start 호출 필요)")
        
    except Exception as e:
        logger.error(f"❌ 서버 시작 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise


@app.post("/control/start")
async def start_analysis(cctv_idx: str, video_path: Optional[str] = None):
    """
    특정 CCTV 분석 시작 (On-Demand)
    Args:
        cctv_idx: CCTV 식별자 (DB의 cctv_idx 예: "CCTV_01")
        video_path: 영상 경로 (선택)
    """
    if m3_api is None:
        raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
    
    # CCTV ID 매핑 및 영상 주소 조회 (DB 조회)
    mapped_cctv_no = cctv_idx
    
    # UUID 형식이 아닌 경우(예: CCTV_01) DB에서 조회 시도
    if len(cctv_idx) < 30:  # UUID는 36자
        db = get_db()
        if db.is_enabled():
            cctv_info = await db.get_cctv_info_by_idx(cctv_idx)
            if cctv_info:
                mapped_cctv_no = cctv_info['cctv_no']
                # DB에 저장된 영상 주소가 있고, 요청 파라미터로 video_path가 안 왔다면 DB 값 사용
                if not video_path and cctv_info.get('stream_url'):
                    video_path = cctv_info['stream_url']
                    logger.info(f"✅ DB 영상 주소 사용: {video_path}")
                
                logger.info(f"✅ CCTV ID 매핑 성공: {cctv_idx} -> {mapped_cctv_no}")
            else:
                logger.warning(f"⚠️ CCTV ID 매핑 실패: {cctv_idx} (DB에 해당 cctv_idx가 없습니다)")
                # 실패해도 일단 진행 (혹시 사용자가 UUID를 보냈을 수도 있으므로)

    # 임시: video_path가 없으면 기본 테스트 영상 사용 (DB에도 없을 경우)
    if not video_path:
        # EC2 환경에 맞는 절대 경로로 수정
        video_path = "/home/ubuntu/storage/m3/IMG_3577.mov"
        if not os.path.exists(video_path):
             # 로컬 테스트용 백업 경로 (윈도우 등)
             video_path = "./video/IMG_3544.mov"
        logger.info(f"⚠️ 기본 영상 경로 사용: {video_path}")
    
    m3_api.start_background_task(video_path=video_path, cctv_no=mapped_cctv_no)
    
    # 더미 데이터 생성기 시작 (최초 1회만, 분석 시작과 함께 활성화)
    # global dummy_thread_started
    # if not dummy_thread_started:
    #     logger.info("ℹ️ 더미 데이터 생성기 시작 (분석되지 않는 나머지 CCTV용)")
    #     dummy_thread = threading.Thread(target=run_dummy_generator, daemon=True)
    #     dummy_thread.start()
    #     dummy_thread_started = True

    logger.info(f"▶️ 분석 시작 요청: {cctv_idx} -> {mapped_cctv_no} (Source: {video_path})")
    return {"status": "started", "cctv_idx": cctv_idx, "mapped_id": mapped_cctv_no, "source": video_path}


@app.post("/control/stop")
async def stop_analysis(cctv_idx: str):
    """
    분석 중지 (On-Demand)
    """
    if m3_api and hasattr(m3_api, 'processor'):
        m3_api.processor.stop()
        logger.info(f"⏹️ 분석 중지 요청: {cctv_idx}")
        return {"status": "stopped", "cctv_idx": cctv_idx}
    
    return {"status": "error", "message": "Processor not active"}


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행"""
    logger.info("M3 P2PNet API 서버 종료 중...")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "M3 P2PNet API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    if m3_api is None:
        raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": True
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    cctv_no: Optional[str] = "CCTV-01"
):
    """
    이미지 분석 API
    
    Args:
        file: 이미지 파일 (jpg, png 등)
        cctv_no: CCTV 식별자
    
    Returns:
        분석 결과 (인원, 혼잡도, 위험 등급 등)
    """
    try:
        logger.info(f"📸 이미지 분석 요청: {file.filename} (CCTV: {cctv_no})")
        
        if m3_api is None:
            raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
        
        # 파일 읽기
        contents = await file.read()
        
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다.")
        
        # 이미지 디코딩
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 디코딩할 수 없습니다.")
        
        logger.info(f"  이미지 크기: {image.shape}")
        
        # M3 분석
        result = m3_api.analyze_image_bytes(contents)
        
        # 응답 데이터 구성
        response = AnalysisResponse(
            count=result['count'],
            density=result['density'],
            pct=result['pct'],
            risk_level=result['risk_level'],
            risk_level_en=result['risk_level_en'],
            alert=result['alert'],
            alert_message=result.get('alert_message'),
            timestamp=datetime.now().isoformat(),
            cctv_no=cctv_no
        )
        
        logger.info(f"✅ 분석 완료: {result['count']}명, {result['pct']}%, {result['risk_level']}")
        
        # risk_level 문자열을 숫자로 변환 (1:안전, 2:주의, 3:경고, 4:위험)
        risk_level_map = {
            '안전': 1,
            '주의': 2,
            '경고': 3,
            '위험': 4
        }
        risk_level_int = risk_level_map.get(result['risk_level'], 1)
        
        # CCTV ID 매핑 적용
        mapped_cctv_no = CCTV_MAPPING.get(cctv_no, cctv_no)

        # Supabase DAT_Crowd_Detection 테이블에 저장
        await save_detection(
            cctv_no=mapped_cctv_no,
            person_count=result['count'],
            congestion_level=int(result['pct']),
            risk_level_int=risk_level_int
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 이미지 분석 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


@app.post("/analyze/video")
async def analyze_video_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    cctv_no: Optional[str] = "CCTV-01",
    frame_interval: int = 30
):
    """
    영상 분석 API (파일 업로드)
    
    Args:
        file: 영상 파일 (mp4, avi 등)
        cctv_no: CCTV 식별자
        frame_interval: N프레임마다 분석 (기본 30)
    
    Returns:
        job_id와 분석 시작 메시지
    """
    try:
        logger.info(f"🎬 영상 분석 요청: {file.filename} (CCTV: {cctv_no})")
        
        if m3_api is None:
            raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
        
        # 임시 파일로 저장
        temp_path = f"temp_{datetime.now().timestamp()}_{file.filename}"
        
        with open(temp_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        logger.info(f"  임시 파일 저장: {temp_path}")
        
        # TODO: video_processor.py 완성 후 비동기 처리
        # job_id = str(uuid.uuid4())
        # background_tasks.add_task(process_video_async, temp_path, cctv_no, frame_interval, job_id)
        
        # 현재는 간단한 응답만
        return {
            "status": "accepted",
            "message": "영상 분석이 시작되었습니다. (구현 예정)",
            "cctv_no": cctv_no,
            "filename": file.filename,
            "note": "video_processor.py 완성 후 실제 처리됩니다."
        }
        
    except Exception as e:
        logger.error(f"❌ 영상 분석 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


@app.post("/analyze/video-url")
async def analyze_video_url(request: VideoAnalysisRequest):
    """
    영상 분석 API (URL 방식)
    
    Args:
        request: 영상 URL 및 분석 옵션
    
    Returns:
        job_id와 분석 시작 메시지
    """
    try:
        logger.info(f"🎬 영상 URL 분석 요청: {request.video_url}")
        
        if m3_api is None:
            raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
        
        if not request.video_url:
            raise HTTPException(status_code=400, detail="video_url이 필요합니다.")
        
        # TODO: video_processor.py 완성 후 구현
        return {
            "status": "accepted",
            "message": "영상 URL 분석이 시작되었습니다. (구현 예정)",
            "video_url": request.video_url,
            "cctv_no": request.cctv_no,
            "note": "video_processor.py 완성 후 실제 처리됩니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 영상 URL 분석 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


@app.get("/logs")
async def get_recent_logs(limit: int = 10, cctv_no: Optional[str] = None):
    """
    최근 분석 결과 조회
    
    Args:
        limit: 조회할 개수 (기본 10개)
        cctv_no: CCTV 필터 (선택)
    
    Returns:
        최근 분석 결과 목록
    """
    try:
        from database import get_logs
        
        logs = await get_logs(limit=limit, cctv_no=cctv_no)
        
        return {
            "status": "success",
            "count": len(logs),
            "data": logs
        }
        
    except Exception as e:
        logger.error(f"❌ 로그 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"조회 중 오류 발생: {str(e)}")


@app.get("/alerts")
async def get_alert_history(limit: int = 10, cctv_no: Optional[str] = None):
    """
    경보 이력 조회 (현재 비활성화)
    
    Args:
        limit: 조회할 개수 (기본 10개)
        cctv_no: CCTV 필터 (선택)
    
    Returns:
        경보 이력 목록
    """
    return {
        "status": "not_implemented",
        "message": "경보 이력은 별도 테이블에서 관리됩니다 (다른 담당자)",
        "note": "DAT_Crowd_Detection 테이블에서 risk_level >= 3 (경고/위험) 데이터를 조회하세요."
    }


# 에러 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 에러 핸들러"""
    logger.error(f"예상치 못한 오류: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": "서버 내부 오류가 발생했습니다.",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # 서버 실행
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8003,
        reload=True,  # 개발 모드
        log_level="info"
    )
