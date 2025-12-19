"""
영상 처리 모듈

영상 파일에서 프레임을 추출하고 M3 모델로 분석
"""
# test
import cv2
import os
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import asyncio
import time
import statistics
from database import save_detection

logger = logging.getLogger(__name__)


class VideoProcessor:
    """영상 처리 및 분석 클래스"""
    
    def __init__(self, analyzer):
        """
        Args:
            analyzer: M3CongestionAPI 인스턴스
        """
        self.analyzer = analyzer
        self.stop_event = asyncio.Event()
    
    async def process_stream_simulation(
        self,
        video_path: str,
        cctv_no: str,
        # interval_seconds: int = 60
        interval_seconds: int = 20,
        roi_params: Optional[Dict[str, float]] = None,
        db_cctv_uuid: Optional[str] = None  # [추가] DB 저장용 ID
    ):
        """
        영상 스트리밍 시뮬레이션 (무한 루프 + 1분 주기 분석)
        
        Args:
            video_path: 영상 파일 경로
            cctv_no: CCTV 식별자 (ROI 조회용)
            interval_seconds: 분석 주기 (초)
            roi_params: CCTV별 맞춤 ROI 파라미터 (없으면 기본값)
            db_cctv_uuid: DB 저장에 사용할 UUID (없으면 cctv_no 사용)
        """
        # [중요] 재시작 시 멈춤 신호 초기화
        self.stop_event.clear()

        if not os.path.exists(video_path):
            logger.error(f"영상 파일을 찾을 수 없습니다: {video_path}")
            return
            
        logger.info(f"🚀 M3 시뮬레이션 시작: {cctv_no} ({interval_seconds}초 주기)")
        logger.info(f"📂 영상 소스: {video_path}")
        if roi_params:
            logger.info(f"🔧 [{cctv_no}] ROI 적용: {roi_params}")
        else:
            logger.info(f"🔧 [{cctv_no}] 기본 ROI 설정 사용")
        
        # DB 저장용 ID 결정 (uuid가 전달되면 그것을, 아니면 None)
        save_target_id = db_cctv_uuid
        if not save_target_id:
            logger.warning(f"⚠️ [{cctv_no}] DB 저장용 UUID가 없습니다. 분석 결과가 DB에 저장되지 않습니다.")
        else:
            logger.info(f"💾 DB 저장 타겟: {save_target_id}")

        cap = cv2.VideoCapture(video_path)
        
        # [추가] FPS 및 전체 프레임 수 확인 (Frame 단위 이동을 위해)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # 기본값 설정
            logger.warning(f"⚠️ FPS를 읽을 수 없어 기본값({fps})을 사용합니다.")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"🎞️ 영상 정보: {fps} FPS, 총 {total_frames} 프레임")

        last_risk_level_int = -1
        
        # [수정] 현재 프레임 위치를 직접 관리 (OpenCV 내부 상태 의존도 낮춤)
        current_frame_idx = 0.0

        try:
            while not self.stop_event.is_set():
                # 0. 목표 지점으로 이동 (Seek)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
                else:
                    logger.warning("⚠️ VideoCapture가 닫혀있어 재연결합니다.")
                    cap = cv2.VideoCapture(video_path)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)

                # 1. 프레임 캡처 (5프레임 연속 읽기)
                frames_data = []
                
                for _ in range(5):
                    ret, frame = cap.read()
                    
                    # 영상 끝 처리
                    if not ret:
                        logger.info("🔄 영상 끝 도달, 처음으로 루프")
                        current_frame_idx = 0
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret:
                            logger.error("영상을 읽을 수 없습니다.")
                            break
                    
                    # 분석
                    try:
                        result = self.analyzer.analyze_frame(frame, roi_params=roi_params)
                        frames_data.append(result)
                    except Exception as e:
                        logger.error(f"프레임 분석 실패: {e}")

                if not frames_data:
                    logger.warning("분석된 프레임이 없습니다. 다음 주기로 넘어갑니다.")
                    await asyncio.sleep(5)
                    continue

                # 2. 중앙값 계산 및 DB 저장 (기존 로직 유지)
                counts = [r['count'] for r in frames_data]
                median_count = statistics.median(counts)
                final_result = min(frames_data, key=lambda x: abs(x['count'] - median_count))
                
                risk_level_map = {'안전': 1, '주의': 2, '경고': 3, '위험': 4}
                current_risk_int = risk_level_map.get(final_result['risk_level'].korean, 1)
                
                is_status_changed = (current_risk_int != last_risk_level_int)
                if is_status_changed:
                    logger.info(f"🔄 상태 변경 감지 ({cctv_no}): {last_risk_level_int} -> {current_risk_int}")
                
                # [수정] UUID가 있을 때만 저장 시도
                if save_target_id:
                    try:
                        await save_detection(
                            cctv_no=save_target_id,
                            person_count=final_result['count'],
                            congestion_level=int(final_result['pct']),
                            risk_level_int=current_risk_int
                        )
                        last_risk_level_int = current_risk_int
                        logger.info(f"💾 DB 저장 완료 ({cctv_no}): {final_result['count']}명, {final_result['risk_level'].korean}")
                    except Exception as e:
                        logger.error(f"DB 저장 실패: {e}")
                else:
                    # 저장하지 않더라도 로그는 출력 (디버깅용)
                    logger.info(f"👀 분석 완료 (DB 미저장): {cctv_no} -> {final_result['count']}명, {final_result['risk_level'].korean}")
                
                # 3. 다음 분석 위치 계산 (현재 + 3초)
                prev_frame_idx = current_frame_idx
                frames_to_skip = int(interval_seconds * fps)
                current_frame_idx += frames_to_skip
                
                # 전체 프레임 초과 시 루프 처리
                if total_frames > 0 and current_frame_idx >= total_frames:
                    current_frame_idx = current_frame_idx % total_frames
                    logger.info("🔄 영상 루프 예정")

                # 시간 정보 로깅
                current_sec = prev_frame_idx / fps if fps else 0
                next_sec = current_frame_idx / fps if fps else 0
                logger.info(f"⏩ 다음 분석 대기: {current_sec:.1f}s -> {next_sec:.1f}s (Frame: {int(prev_frame_idx)} -> {int(current_frame_idx)})")

                # 4. 대기 (실제 시간 흐름 시뮬레이션)
                # 분석에 걸린 시간은 무시하고, 단순히 주기만큼 기다림 (요청사항 반영)
                wait_time = max(0, interval_seconds - 1.0) # 분석 시간 고려하여 조금 뺌
                logger.info(f"💤 {wait_time}초 대기...")
                await asyncio.sleep(wait_time)
                
        finally:
            cap.release()
            logger.info(f"🛑 M3 시뮬레이션 종료: {cctv_no}")

    def stop(self):
        """시뮬레이션 중지 신호"""
        self.stop_event.set()
