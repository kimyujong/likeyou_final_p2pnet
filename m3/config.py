"""
M3 시스템 설정
"""

import os


class M3Config:
    """M3 시스템 설정 클래스"""
    
    # 경로 설정
    ORIGINAL_BASE_DIR = 'C:/Users/user/m3_p2pnet'
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    P2PNET_SOURCE = os.path.join(ORIGINAL_BASE_DIR, 'p2pnet_source')
    
    # [복구] 원래의 Best 모델로 원복
    MODEL_PATH = os.path.join(ORIGINAL_BASE_DIR, 'output/org_from_scratch/ckpt/best_mae.pth')
    
    DEPLOYMENT_DIR = os.path.join(BASE_DIR, 'deployment')
    
    # 모델 설정
    DEVICE = 'cuda'
    BACKBONE = 'vgg16_bn'
    
    # [재조정] 오탐을 줄이기 위해 Threshold를 조금 높임 (0.35 -> 0.5)
    THRESHOLD = 0.5
    
    # [요구사항 2] Y축 영역 필터링 비율 (0.0 ~ 1.0)
    IGNORE_TOP_RATIO = 0.01      # 상단 1%만 무시
    IGNORE_BOTTOM_RATIO = 0.99   # 하단 1%만 무시
    
    # [요구사항 3] 적응형 ROI 사용 여부
    USE_ADAPTIVE_ROI = True
    
    # [튜닝] Auto ROI 기본 비율 설정
    DEFAULT_ROI_PARAMS = {
        'top_y_ratio': 0.3,      # 상단 높이 (0.0 ~ 1.0)
        'top_w_ratio': 0.2,      # 상단 폭 비율
        'bottom_w_ratio': 0.6    # 하단 폭 비율
    }
    
    # [호환성 유지] 기존 코드에서 ROI_PARAMS를 참조하는 경우를 위해 남겨둠
    ROI_PARAMS = DEFAULT_ROI_PARAMS

    # [개별 설정] CCTV ID별 맞춤 ROI 설정
    ROI_SETTINGS_MAP = {
        'CCTV_01': {'top_y_ratio': 0.63, 'top_w_ratio': 0.12, 'bottom_w_ratio': 0.50},
        'CCTV_02': {'top_y_ratio': 0.15, 'top_w_ratio': 0.09, 'bottom_w_ratio': 0.66}
    }

    @classmethod
    def get_roi_params(cls, cctv_id):
        """CCTV ID에 맞는 ROI 설정을 반환 (없으면 기본값)"""
        return cls.ROI_SETTINGS_MAP.get(cctv_id, cls.DEFAULT_ROI_PARAMS)
    
    # [요구사항 4] 구역별 가중치 (Near, Mid, Far)
    ZONE_WEIGHTS = {
        'near': 0.5,  # 근거리 (화면 하단)
        'mid': 0.3,   # 중거리
        'far': 0.2    # 원거리 (화면 상단)
    }
    
    # 혼잡도 설정
    MAX_CAPACITY = 200  # 최대 수용 인원 (참고용)
    ALERT_THRESHOLD = 50  # 경보 발생 임계값 (%)
    ALERT_COOLDOWN = 60  # 경보 쿨다운 (초)
    
    # 기본 ROI (Adaptive ROI 실패 시 사용)
    ROI_POLYGON = None  # Adaptive ROI 사용 시 None
    EXCLUDE_POLYGONS = []
    
    # 정적 필터 미사용
    USE_STATIC_FILTER = False
    STATIC_THRESHOLD = 0.85
    
    # 비디오 처리 설정
    PROCESS_EVERY_N_FRAMES = 5
    
    # 출력 설정
    OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    
    # 테스트 비디오 경로
    TEST_VIDEO_DIR = 'C:/Users/user/M3/video/'
    
    @classmethod
    def get_model_config(cls):
        return {
            'model_path': cls.MODEL_PATH,
            'p2pnet_source': cls.P2PNET_SOURCE,
            'device': cls.DEVICE,
            'backbone': cls.BACKBONE,
            'threshold': cls.THRESHOLD
        }
    
    @classmethod
    def get_congestion_config(cls):
        return {
            'max_capacity': cls.MAX_CAPACITY,
            'alert_threshold': cls.ALERT_THRESHOLD,
            'alert_cooldown': cls.ALERT_COOLDOWN,
            'roi_polygon': cls.ROI_POLYGON,
            'exclude_polygons': cls.EXCLUDE_POLYGONS,
            'process_every_n_frames': cls.PROCESS_EVERY_N_FRAMES,
            'use_static_filter': cls.USE_STATIC_FILTER,
            'static_threshold': cls.STATIC_THRESHOLD,
            'ignore_top': cls.IGNORE_TOP_RATIO,
            'ignore_bottom': cls.IGNORE_BOTTOM_RATIO,
            'use_adaptive_roi': cls.USE_ADAPTIVE_ROI,
            'zone_weights': cls.ZONE_WEIGHTS,
            'roi_params': cls.ROI_PARAMS
        }
