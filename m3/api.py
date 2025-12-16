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
                 roi_polygon=None, alert_threshold=50, use_fp16=True):
        """
        Args:
            model_path: P2PNet 모델 파일 경로
            p2pnet_source_path: P2PNet 소스 코드 경로
            device: 'cuda' 또는 'cpu'
            max_capacity: 최대 수용 인원
            roi_polygon: ROI 다각형 좌표 (선택)
            alert_threshold: 경보 발생 임계값 (%)
            use_fp16: FP16 가속 사용 여부
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
            use_adaptive_roi=(roi_polygon is None)
        )
        
        # 알림 시스템
        self.alert_system = AlertSystem(alert_threshold=alert_threshold)
        
        # 백그라운드 프로세서 초기화
        self.processor = VideoProcessor(self.analyzer)
        
        print(f"✅ M3CongestionAPI 초기화 완료")
        
    def start_background_task(self, video_path, cctv_no, interval_seconds=60):
        """백그라운드 분석 시작"""
        if not os.path.exists(video_path):
            print(f"⚠️ 영상 파일 없음: {video_path}")
            return
            
        asyncio.create_task(
            self.processor.process_stream_simulation(
                video_path=video_path,
                cctv_no=cctv_no,
                interval_seconds=interval_seconds
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

