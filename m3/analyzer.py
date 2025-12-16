"""
M3 혼잡도 분석기
"""

import cv2
import numpy as np
import torch
from PIL import Image
import torchvision.transforms as transforms

from constants import CongestionLevel, DEFAULT_THRESHOLD, DEFAULT_ZONE_WEIGHTS, DEFAULT_ROI_PARAMS

# [신규] develop 버전의 헬퍼 함수들 추가
def filter_by_confidence(points, scores, threshold=0.45):
    """신뢰도 기반 필터링"""
    filtered = []
    for (x, y), s in zip(points, scores):
        if s >= threshold:
            filtered.append((x, y))
    return np.array(filtered) if filtered else np.empty((0, 2))

def filter_by_perspective(points, frame_height):
    """Y축 위치 기반 필터링: 원근 왜곡 및 오탐 보정"""
    if len(points) == 0: return points
    filtered = []
    for p in points:
        x, y = p[0], p[1]
        if y < frame_height * 0.10: continue  # 너무 상단(멀리) 제외
        if y > frame_height * 0.95: continue  # 너무 하단(가까이) 제외
        filtered.append((x, y))
    return np.array(filtered) if filtered else np.empty((0, 2))

def auto_roi(frame, top_y_ratio=0.3, top_w_ratio=0.2, bottom_w_ratio=0.6):
    """중앙 고정 Auto ROI 생성"""
    h, w = frame.shape[:2]
    center_x = w // 2
    
    top_y = int(h * top_y_ratio)
    bottom_y = h
    
    bottom_w = w * bottom_w_ratio
    top_w = w * top_w_ratio
    
    roi = np.array([
        (int(center_x - bottom_w/2), bottom_y),
        (int(center_x + bottom_w/2), bottom_y),
        (int(center_x + top_w/2), top_y),
        (int(center_x - top_w/2), top_y)
    ], dtype=np.int32)
    return roi

def calculate_scene_density(points, roi_area, scene_weights, frame_height):
    """구역별(Near/Mid/Far) 가중치 적용 밀도 계산"""
    if frame_height is None or roi_area <= 0: return 0.0, 0.0
    
    near, mid, far = 0, 0, 0
    for p in points:
        y = p[1]
        if y > frame_height * 0.66: near += 1
        elif y > frame_height * 0.33: mid += 1
        else: far += 1
        
    weighted_count = (near * scene_weights[0] + mid * scene_weights[1] + far * scene_weights[2])
    weighted_density = weighted_count / roi_area * 1000
    
    # PCT 기준: 1000px당 0.15명을 100%로 가정
    pct = min(100, (weighted_density / 0.15) * 100)
    return weighted_density, pct


class M3CongestionAnalyzer:
    """
    M3 혼잡도 분석 시스템 (orig + develop 성능 개선 병합)
    """
    def __init__(self, model, device, roi_polygon=None, max_capacity=None, 
                 use_adaptive_roi=True, zone_weights=DEFAULT_ZONE_WEIGHTS):
        """
        Args:
            model: P2PNet 모델 객체
            device: 디바이스 (cuda/cpu)
            roi_polygon: ROI 다각형 좌표 [(x1,y1), (x2,y2), ...] (None이면 전체 영역)
            max_capacity: 최대 수용 인원 (명)
        """
        self.model = model
        self.device = device
        self.roi_polygon = roi_polygon
        self.max_capacity = max_capacity
        
        # [신규] 성능 개선을 위한 설정
        self.use_adaptive_roi = use_adaptive_roi
        self.zone_weights = zone_weights
        self.scene_weights = (zone_weights['near'], zone_weights['mid'], zone_weights['far'])
        self.roi_params = DEFAULT_ROI_PARAMS
        self.cached_roi = None
        
        # ROI 면적 계산
        if roi_polygon:
            self.roi_area = cv2.contourArea(np.array(roi_polygon, dtype=np.int32))
        else:
            self.roi_area = 1920 * 1080  # 기본값 (Full HD)
        
        # Transform
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
        
        # [수정] 리사이징 제거 (사람이 작은 영상에서 탐지 실패 방지)
        # self.target_width = 1024  
        self.target_width = None 
        
        print(f"M3 Analyzer 초기화:")
        print(f"  ROI: {'사용자 정의' if roi_polygon else '전체 영역'}")
        print(f"  면적: {self.roi_area:,.0f} 픽셀")
        print(f"  최대 수용: {max_capacity}명" if max_capacity else "  최대 수용: 미설정")
        # print(f"  성능 최적화: Max Width {self.target_width}px")
    
    def is_point_in_roi(self, point):
        """점이 ROI 영역 내에 있는지 확인"""
        if self.roi_polygon is None:
            return True  # ROI 없으면 모든 점 허용
        
        x, y = point
        result = cv2.pointPolygonTest(
            np.array(self.roi_polygon, dtype=np.int32),
            (float(x), float(y)),
            False
        )
        return result >= 0  # 0 이상이면 내부 또는 경계
    
    def predict_count(self, frame):
        """
        프레임에서 사람 수 예측 (ROI 필터링 포함)
        
        Args:
            frame: OpenCV BGR 이미지
        
        Returns:
            count: 사람 수
            points: 점 좌표 배열
        """
        # [추가] 야간/저조도 대응을 위한 감마 보정 (Gamma Correction)
        # 이미지를 전체적으로 밝게 만듦 (gamma < 1.0 : 밝게, gamma > 1.0 : 어둡게)
        # 감마 1.5는 어두운 부분을 밝게 끌어올리면서 밝은 부분은 유지함
        gamma = 1.5
        look_up_table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255
                                  for i in np.arange(0, 256)]).astype("uint8")
        frame = cv2.LUT(frame, look_up_table)

        # 원본 크기 저장
        h, w = frame.shape[:2]
        
        # 1. 리사이징 (제거됨)
        # 원거리 영상에서 사람이 뭉개지는 문제로 인해 원본 해상도 유지
        scale_ratio = 1.0
        new_w, new_h = w, h
        
        # (선택 사항) 만약 너무 큰 이미지가 들어오면 여기서 제한 가능
        # if self.target_width and w > self.target_width: ...
            
        # 2. 128 배수 맞춤 (P2PNet 요구사항 - 필수)
        # 모델이 128의 배수 크기만 받을 수 있는 경우가 많음
        gw, gh = new_w, new_h
        if gw % 128 != 0:
            gw = ((gw // 128) + 1) * 128
        if gh % 128 != 0:
            gh = ((gh // 128) + 1) * 128
            
        # 패딩이 필요한 경우
        pad_w = gw - new_w
        pad_h = gh - new_h
        
        if pad_w > 0 or pad_h > 0:
            frame = cv2.copyMakeBorder(frame, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=(0,0,0))
            
        # BGR → RGB
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        
        # Transform
        img_tensor = self.transform(img_pil).unsqueeze(0).to(self.device)
        
        # FP16 지원
        if next(self.model.parameters()).dtype == torch.float16:
            img_tensor = img_tensor.half()
        
        # 추론
        with torch.no_grad():
            outputs = self.model(img_tensor)
        
        outputs_scores = torch.nn.functional.softmax(outputs['pred_logits'], -1)[:, :, 1][0]
        outputs_points = outputs['pred_points'][0]
        
        # 임계값
        threshold = DEFAULT_THRESHOLD
        
        # 마스크 생성
        mask = outputs_scores > threshold
        points = outputs_points[mask].cpu().numpy()
        scores = outputs_scores[mask].cpu().numpy()  # 점수도 함께 추출
        
        # 3. 좌표 복원 (패딩 제거)
        if len(points) > 0:
            # 패딩 영역에 찍힌 점 제거
            valid_mask = (points[:, 0] < new_w) & (points[:, 1] < new_h)
            points = points[valid_mask]
            scores = scores[valid_mask]
            
            # 좌표 클램핑
            if len(points) > 0:
                points[:, 0] = np.clip(points[:, 0], 0, w-1)
                points[:, 1] = np.clip(points[:, 1], 0, h-1)
        
        # ROI 필터링 (선택적)
        if self.roi_polygon is not None:
            # ROI 내부 점들만 필터링
            roi_mask = [self.is_point_in_roi(p) for p in points]
            points = points[roi_mask]
            scores = scores[roi_mask]
        
        return len(points), points, scores
    
    def calculate_density(self, count):
        """
        인원 밀도 계산
        
        Formula: D_current = Count / ROI_Area
        """
        return count / self.roi_area
    
    def calculate_pct(self, count):
        """
        혼잡도 비율(%) 계산
        
        Formula: PCT = min(100, round((Count / MAX_CAPACITY) × 100))
        """
        if self.max_capacity is not None:
            pct = (count / self.max_capacity) * 100
        else:
            # 기본값: 500명 가정
            pct = (count / 500) * 100
        
        return min(100, round(pct, 2))
    
    def get_risk_level(self, pct):
        """혼잡도 비율로 위험 등급 판단"""
        return CongestionLevel.get_level(pct)
    
    def analyze_frame(self, frame):
        """
        [업그레이드] 프레임 종합 분석
        """
        h, w = frame.shape[:2]

        # 1. P2PNet 예측 (orig의 predict_count 사용)
        count, points, scores = self.predict_count(frame)

        # 2. [신규] 신뢰도 및 원근 필터링
        points = filter_by_confidence(points, scores, threshold=DEFAULT_THRESHOLD)
        points = filter_by_perspective(points, h)

        # 3. [신규] ROI 설정 (Adaptive or Fixed)
        if self.use_adaptive_roi and self.roi_polygon is None:
            if self.cached_roi is None:
                self.cached_roi = auto_roi(frame, **self.roi_params)
            roi = self.cached_roi
        elif self.roi_polygon:
            roi = np.array(self.roi_polygon, dtype=np.int32)
        else:
            roi = np.array([[0, h], [w, h], [w, 0], [0, 0]], dtype=np.int32)

        # 4. ROI 내부 점 필터링
        roi_points = []
        for p in points:
            if cv2.pointPolygonTest(roi, (float(p[0]), float(p[1])), False) >= 0:
                roi_points.append(p)
        roi_points = np.array(roi_points) if roi_points else np.empty((0, 2))
        
        # 5. [신규] 가중치 기반 밀도 계산
        roi_area = cv2.contourArea(roi)
        density, pct = calculate_scene_density(roi_points, roi_area, self.scene_weights, h)
        risk_level = CongestionLevel.get_level(pct)

        return {
            'count': len(roi_points),
            'density': density,
            'pct': pct,
            'risk_level': risk_level,
            'points': roi_points,
            'roi_polygon': roi
        }

