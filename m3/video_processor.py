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
        # interval_seconds: int = 60
        interval_seconds: int = 3,
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
        if not os.path.exists(video_path):
            logger.error(f"영상 파일을 찾을 수 없습니다: {video_path}")
            return
            
        logger.info(f"🚀 M3 시뮬레이션 시작: {cctv_no} ({interval_seconds}초 주기)")
        logger.info(f"📂 영상 소스: {video_path}")
        if roi_params:
            logger.info(f"🔧 [{cctv_no}] ROI 적용: {roi_params}")
        else:
            logger.info(f"🔧 [{cctv_no}] 기본 ROI 설정 사용")
        
        # DB 저장용 ID 결정 (uuid가 전달되면 그것을, 아니면 cctv_no를 사용)
        save_target_id = db_cctv_uuid if db_cctv_uuid else cctv_no
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
        
        try:
            while not self.stop_event.is_set():
                # 1. 프레임 캡처 (CPU 환경 고려: 5 -> 1프레임으로 축소)
                frames_data = []
                
                # CPU 모드에서는 속도를 위해 1프레임만 분석
                # GPU 모드라면 range(3~5) 권장
                for _ in range(5):
                    # 객체가 닫혀있을 때만 다시 열기
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
                        result = self.analyzer.analyze_frame(frame, roi_params=roi_params)
                        frames_data.append(result)
                        
                        # [디버깅] 분석 화면 실시간 표시 (서버 환경에서는 주의)
                        # 필요한 경우 주석 해제하여 사용
                        try:
                            vis_frame = frame.copy()
                            # 점 찍기
                            if len(result['points']) > 0:
                                for p in result['points']:
                                    cv2.circle(vis_frame, (int(p[0]), int(p[1])), 3, (0, 0, 255), -1)
                            
                            # 정보 텍스트
                            text = f"Count: {result['count']} | Density: {result['pct']}% ({result['risk_level'].korean})"
                            cv2.putText(vis_frame, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                            
                            # 창 띄우기 (제목에 CCTV ID 표시)
                            # cv2.namedWindow(f"Monitor-{cctv_no}", cv2.WINDOW_NORMAL) # 필요 시 활성화
                            # cv2.imshow(f"Monitor-{cctv_no}", vis_frame)
                            # if cv2.waitKey(1) & 0xFF == ord('q'):
                            #     self.stop_event.set()
                        except Exception as vis_e:
                            # GUI 없는 환경에서의 에러 방지
                            pass
                            
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
                        cctv_no=save_target_id,  # [수정] DB 저장용 ID 사용
                        person_count=final_result['count'],
                        congestion_level=int(final_result['pct']),
                        risk_level_int=current_risk_int
                    )
                    last_risk_level_int = current_risk_int
                    logger.info(f"💾 DB 저장 완료 ({cctv_no}): {final_result['count']}명, {final_result['risk_level'].korean}")
                    
                except Exception as e:
                    logger.error(f"DB 저장 실패: {e}")
                
                # 5. 다음 주기까지 대기 및 영상 건너뛰기
                # 분석에 걸린 시간(약 2.5초)을 고려하여 남은 시간만큼 대기
                wait_time = max(0, interval_seconds - 2.5)
                logger.info(f"💤 {wait_time}초 대기...")
                await asyncio.sleep(wait_time)
                
                # [중요] 현실 시간이 흐른 만큼 영상 위치도 강제로 이동 (Sync)
                # 현재 위치에서 interval_seconds 만큼 점프 (Frame 단위로 변경하여 정확도 향상)
                if cap.isOpened():
                    try:
                        current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
                        frames_to_skip = int(interval_seconds * fps)
                        next_frame = current_frame + frames_to_skip
                        
                        # 전체 프레임을 초과하면 처음으로 루프
                        if total_frames > 0 and next_frame >= total_frames:
                            next_frame = next_frame % total_frames
                            logger.info("🔄 영상 루프 (처음으로 이동)")

                        cap.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
                        
                        # 시간 정보 계산 (로깅용)
                        current_sec = current_frame / fps if fps else 0
                        next_sec = next_frame / fps if fps else 0
                        logger.info(f"⏩ 영상 점프: {current_sec:.1f}s -> {next_sec:.1f}s (Frame: {int(current_frame)} -> {int(next_frame)})")
                    except Exception as seek_e:
                        logger.error(f"영상 탐색 오류: {seek_e}")
                        # 오류 시 강제로 다음 프레임으로 조금만 이동
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame + 30)
                
        finally:
            cap.release()
            logger.info(f"🛑 M3 시뮬레이션 종료: {cctv_no}")

    def stop(self):
        """시뮬레이션 중지 신호"""
        self.stop_event.set()
