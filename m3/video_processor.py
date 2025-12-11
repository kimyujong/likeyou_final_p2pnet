"""
영상 처리 모듈

영상 파일에서 프레임을 추출하고 M3 모델로 분석
"""

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
        interval_seconds: int = 60
    ):
        """
        영상 스트리밍 시뮬레이션 (무한 루프 + 1분 주기 분석)
        
        Args:
            video_path: 영상 파일 경로
            cctv_no: CCTV 식별자
            interval_seconds: 분석 주기 (초)
        """
        if not os.path.exists(video_path):
            logger.error(f"영상 파일을 찾을 수 없습니다: {video_path}")
            return
            
        logger.info(f"🚀 M3 시뮬레이션 시작: {cctv_no} ({interval_seconds}초 주기)")
        logger.info(f"📂 영상 소스: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        last_risk_level_int = -1
        
        try:
            while not self.stop_event.is_set():
                # 1. 5프레임 캡처 (0.5초 간격)
                frames_data = []
                
                for _ in range(5):
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(video_path)
                    
                    ret, frame = cap.read()
                    
                    # 영상 끝이면 처음으로 되감기 (무한 루프)
                    if not ret:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret:
                            logger.error("영상을 읽을 수 없습니다.")
                            break
                    
                    # 분석
                    try:
                        result = self.analyzer.analyze_frame(frame)
                        frames_data.append(result)
                    except Exception as e:
                        logger.error(f"프레임 분석 실패: {e}")
                    
                    # 0.5초 대기 (프레임 간 간격)
                    await asyncio.sleep(0.5)
                
                if not frames_data:
                    logger.warning("분석된 프레임이 없습니다. 다음 주기로 넘어갑니다.")
                    await asyncio.sleep(10)
                    continue
                
                # 2. 중앙값 계산 (안정화)
                # 인원수 기준으로 중앙값에 해당하는 결과 선택
                counts = [r['count'] for r in frames_data]
                median_count = statistics.median(counts)
                
                # 중앙값과 가장 가까운 결과 찾기
                final_result = min(frames_data, key=lambda x: abs(x['count'] - median_count))
                
                # 3. 위험 등급 확인
                # risk_level 문자열을 숫자로 변환 (1:안전, 2:주의, 3:경고, 4:위험)
                risk_level_map = {'안전': 1, '주의': 2, '경고': 3, '위험': 4}
                current_risk_int = risk_level_map.get(final_result['risk_level'].korean, 1)
                
                # 4. DB 저장 판단 (상태 변화 OR 주기적 갱신)
                # 여기서는 '주기적 갱신'이 기본이므로 무조건 저장하되, 
                # 상태가 변했을 때는 로그를 다르게 남길 수 있음.
                
                is_status_changed = (current_risk_int != last_risk_level_int)
                
                if is_status_changed:
                    logger.info(f"🔄 상태 변경 감지 ({cctv_no}): {last_risk_level_int} -> {current_risk_int}")
                
                # DB 저장
                try:
                    await save_detection(
                        cctv_no=cctv_no,
                        person_count=final_result['count'],
                        congestion_level=int(final_result['pct']),
                        risk_level_int=current_risk_int
                    )
                    last_risk_level_int = current_risk_int
                    logger.info(f"💾 DB 저장 완료 ({cctv_no}): {final_result['count']}명, {final_result['risk_level'].korean}")
                    
                except Exception as e:
                    logger.error(f"DB 저장 실패: {e}")
                
                # 5. 다음 주기까지 대기 (Sleep)
                # 5프레임 찍느라 2.5초 썼으므로 나머지만 대기
                wait_time = max(0, interval_seconds - 2.5)
                logger.info(f"💤 {wait_time}초 대기...")
                await asyncio.sleep(wait_time)
                
        finally:
            cap.release()
            logger.info(f"🛑 M3 시뮬레이션 종료: {cctv_no}")

    def stop(self):
        """시뮬레이션 중지 신호"""
        self.stop_event.set()
