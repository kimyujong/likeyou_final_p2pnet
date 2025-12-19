"""
M3 통합 API (FastAPI 연동용)
"""

import torch
import cv2
import numpy as np
import sys
import asyncio
import os

from model import P2PNetModel
from analyzer import M3CongestionAnalyzer
from alert import AlertSystem
from constants import DEFAULT_MAX_CAPACITY
from database import save_detection
from video_processor import VideoProcessor


class M3CongestionAPI:
    """
    FastAPI 서버에서 사용할 M3 혼잡도 분석 API
    """
    def __init__(self, model_path, p2pnet_source_path, 
                 device='cuda', max_capacity=DEFAULT_MAX_CAPACITY,
                 roi_polygon=None, alert_threshold=50, use_fp16=True, **kwargs):
        """
        Args:
            model_path: P2PNet 모델 파일 경로
            p2pnet_source_path: P2PNet 소스 코드 경로
            device: 'cuda' 또는 'cpu'
            max_capacity: 최대 수용 인원
            roi_polygon: ROI 다각형 좌표 (선택)
            alert_threshold: 경보 발생 임계값 (%)
            use_fp16: FP16 가속 사용 여부
            **kwargs: 추가 설정 (threshold, use_adaptive_roi, zone_weights, roi_params 등)
        """
        # P2PNet 소스 경로 추가
        if p2pnet_source_path not in sys.path:
            sys.path.insert(0, p2pnet_source_path)
        
        from models import build_model
        from model import P2PNetModel  # P2PNetModel 클래스 활용 권장
        
        # 모델 로드
        if device == 'cuda' and not torch.cuda.is_available():
            print("\n" + "!"*60)
            print("❌ [치명적 경고] GPU(CUDA)를 요청했으나 사용할 수 없습니다!")
            print("   -> CPU 모드로 강제 전환됩니다. 속도가 매우 느릴 것입니다.")
            print("   -> 해결책: PyTorch CUDA 버전을 설치해주세요.")
            print("!"*60 + "\n")
            device_obj = torch.device('cpu')
        else:
            device_obj = torch.device(device)
            
        # [디버깅] 현재 사용 중인 디바이스 출력
        if device_obj.type == 'cuda':
            print(f"✅ GPU 가속 활성화: {torch.cuda.get_device_name(0)}")
        else:
            print(f"⚠️ CPU 모드로 실행 중 (느림)")
        
        class Args:
            backbone = 'vgg16_bn'
            row = 2
            line = 2
        
        args = Args()
        model = build_model(args, training=False)
        checkpoint = torch.load(model_path, map_location=device_obj)
        model.load_state_dict(checkpoint['model'])
        model.to(device_obj)
        
        # FP16 적용
        if use_fp16 and device_obj.type == 'cuda':
            model.half()
            print("⚡ M3CongestionAPI: FP16 모드 활성화")
            torch.backends.cudnn.benchmark = True
            
        model.eval()
        
        # M3 분석기 (개선된 파라미터 적용)
        self.analyzer = M3CongestionAnalyzer(
            model=model,
            device=device_obj,
            roi_polygon=roi_polygon,
            max_capacity=max_capacity,
            # [신규] Adaptive ROI 활성화 (고정 ROI가 없을 때만)
            use_adaptive_roi=kwargs.get('use_adaptive_roi', (roi_polygon is None)),
            zone_weights=kwargs.get('zone_weights', {'near': 0.5, 'mid': 0.3, 'far': 0.2}),
            threshold=kwargs.get('threshold', 0.45),
            roi_params=kwargs.get('roi_params')
        )
        
        # 알림 시스템
        self.alert_system = AlertSystem(alert_threshold=alert_threshold)
        
        # 백그라운드 프로세서 초기화
        self.processor = VideoProcessor(self.analyzer)
        
        print(f"✅ M3CongestionAPI 초기화 완료")
        
    def start_background_task(self, video_path, cctv_no, interval_seconds=10, db_cctv_uuid=None):
        """
        백그라운드 분석 시작
        Args:
            video_path: 영상 경로
            cctv_no: ROI 조회용 ID (예: CCTV_01)
            interval_seconds: 분석 주기
            db_cctv_uuid: DB 저장용 UUID (없으면 cctv_no 사용)
        """
        if not os.path.exists(video_path):
            print(f"⚠️ 영상 파일 없음: {video_path}")
            return
            
        # [수정] 1. Config에서 CCTV ID에 맞는 ROI 설정 가져오기
        from config import M3Config
        custom_roi_params = M3Config.get_roi_params(cctv_no)
        
        print(f"✅ [{cctv_no}] 맞춤 ROI 설정 로드: {custom_roi_params}")

        asyncio.create_task(
            self.processor.process_stream_simulation(
                video_path=video_path,
                cctv_no=cctv_no,
                interval_seconds=interval_seconds,
                roi_params=custom_roi_params,
                db_cctv_uuid=db_cctv_uuid  # [추가] DB 저장용 ID 전달
            )
        )
    
    def analyze_image_bytes(self, image_bytes):
        """
        바이트 데이터에서 혼잡도 분석 (FastAPI용)
        
        Args:
            image_bytes: 이미지 바이너리 데이터
        
        Returns:
            dict: 분석 결과
        """
        # 이미지 디코딩
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 분석
        result = self.analyzer.analyze_frame(frame)
        
        # 경보 체크
        should_alert, alert_msg = self.alert_system.check_alert(
            result['pct'], 
            result['risk_level']
        )
        
        return {
            'count': result['count'],
            'density': float(result['density']),
            'pct': float(result['pct']),
            'risk_level': result['risk_level'].korean,
            'risk_level_en': result['risk_level'].name,
            'alert': should_alert,
            'alert_message': alert_msg if should_alert else None,
            'points': result['points'].tolist()
        }
    
    def analyze_frame(self, frame):
        """
        OpenCV 프레임에서 혼잡도 분석
        
        Args:
            frame: OpenCV BGR 이미지
        
        Returns:
            dict: 분석 결과
        """
        return self.analyzer.analyze_frame(frame)

