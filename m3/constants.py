"""
M3 시스템 상수 정의
"""

from enum import Enum


class CongestionLevel(Enum):
    """혼잡도 등급"""
    SAFE = ("안전", 0, 25, (0, 255, 0))      # 녹색
    CAUTION = ("주의", 26, 50, (255, 255, 0))  # 노란색
    WARNING = ("경고", 51, 75, (255, 165, 0))  # 주황색
    DANGER = ("위험", 76, 100, (255, 0, 0))    # 빨간색
    
    def __init__(self, korean, min_pct, max_pct, color):
        self.korean = korean
        self.min_pct = min_pct
        self.max_pct = max_pct
        self.color = color  # BGR 색상
    
    @classmethod
    def get_level(cls, pct):
        """PCT 값에 따른 등급 반환"""
        for level in cls:
            if level.min_pct <= pct <= level.max_pct:
                return level
        return cls.DANGER  # 100% 초과 시 위험


# 기본 설정값
DEFAULT_MAX_CAPACITY = 200
DEFAULT_ALERT_THRESHOLD = 50
DEFAULT_ROI_AREA = 1920 * 1080
DEFAULT_THRESHOLD = 0.45  # [수정] 오탐 감소를 위해 0.1 -> 0.45로 상향 조정
MOTION_CONFIRM_THRESHOLD = 0.5  # [수정] 확신 구간도 소폭 하향 (0.6 -> 0.5)
DEFAULT_ALERT_COOLDOWN = 60  # 초

# [신규] 성능 개선을 위한 파라미터 (develop 버전에서 이식)
# 1. Y축 필터링 (상/하단 오탐 제거)
DEFAULT_IGNORE_TOP = 0.10     # 상단 10% 무시
DEFAULT_IGNORE_BOTTOM = 0.95  # 하단 5% 무시

# 2. 거리별 가중치 (Near/Mid/Far)
DEFAULT_ZONE_WEIGHTS = {'near': 0.5, 'mid': 0.3, 'far': 0.2}

# 3. Auto ROI 설정 (도로 형태)
DEFAULT_ROI_PARAMS = {
    'top_y_ratio': 0.3, 
    'top_w_ratio': 0.2, 
    'bottom_w_ratio': 0.6
}

