"""
영상 시각화 모듈

영상을 재생하면서 실시간으로 사람 디텍션 및 혼잡도 표시
"""

import cv2
import os
import numpy as np
from typing import Optional
from dotenv import load_dotenv

from api import M3CongestionAPI
from utils import put_korean_text

load_dotenv()


def visualize_video_analysis(
    video_path: str,
    m3_api: M3CongestionAPI,
    frame_skip: int = 1,
    save_output: bool = False,
    output_path: Optional[str] = None,
    use_motion_filter: bool = True  # 동작 인식 필터 옵션 추가
):
    """
    영상을 재생하면서 실시간 분석 결과 표시
    
    Args:
        video_path: 영상 파일 경로
        m3_api: M3CongestionAPI 인스턴스
        frame_skip: N프레임마다 분석
        save_output: 결과 영상 저장 여부
        output_path: 저장할 파일 경로
        use_motion_filter: 움직임이 없는 배경(돌의자 등) 오탐지 제거 활성화
    """
    if not os.path.exists(video_path):
        print(f"❌ 영상 파일을 찾을 수 없습니다: {video_path}")
        return
    
    # 영상 열기
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ 영상을 열 수 없습니다: {video_path}")
        return
    
    # 영상 정보
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"\n📹 영상 정보:")
    print(f"  해상도: {width}x{height}")
    print(f"  FPS: {fps}")
    print(f"  총 프레임: {total_frames}")
    
    # 표시용 해상도 설정 (화면에 맞게 축소)
    display_width = 1280  # HD 해상도로 표시
    display_height = int(height * (display_width / width))
    print(f"  📺 표시 크기: {display_width}x{display_height}\n")
    
    # 출력 영상 설정
    out = None
    if save_output:
        if not output_path:
            output_path = video_path.replace('.', '_analyzed.')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"💾 분석 영상 저장: {output_path}\n")
    
    # 동작 감지기 초기화 (배경 학습용)
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=500, 
        varThreshold=25, 
        detectShadows=False
    ) if use_motion_filter else None
    
    print("🎬 영상 재생 시작! (ESC 키로 종료)\n")
    
    frame_count = 0
    last_result = None
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # 동작 마스크 생성 (매 프레임 업데이트 필요)
            motion_mask = None
            if bg_subtractor:
                # 성능 최적화: 동작 감지는 축소된 이미지에서 수행 (CPU 부하 감소)
                motion_scale = 640 / width
                motion_w = 640
                motion_h = int(height * motion_scale)
                
                frame_small = cv2.resize(frame, (motion_w, motion_h), interpolation=cv2.INTER_NEAREST)
                
                # 배경 학습 및 마스크 생성
                mask_small = bg_subtractor.apply(frame_small)
                
                # 노이즈 제거
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask_small = cv2.morphologyEx(mask_small, cv2.MORPH_OPEN, kernel)
                
                # 다시 원본 크기로 복원 (좌표 매핑을 위해)
                motion_mask = cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_NEAREST)
            
            # 원본 프레임 복사 (그리기용)
            display_frame = frame.copy()
            
            # frame_skip마다 분석
            if frame_count % frame_skip == 0:
                try:
                    # 원본 해상도 그대로 분석 (M3_origin 방식)
                    result = m3_api.analyze_frame(frame)
                    
                    # [수정] 하이브리드 필터링 적용
                    # scores가 없는 경우를 대비해 안전하게 처리
                    scores = result.get('scores', np.ones(len(result['points'])))
                    
                    # 동작 필터 적용: 움직임이 없는 영역의 포인트 제거
                    if use_motion_filter and motion_mask is not None and len(result['points']) > 0:
                        filtered_points = []
                        
                        # 임계값 가져오기
                        from constants import MOTION_CONFIRM_THRESHOLD
                        
                        for i, p in enumerate(result['points']):
                            score = scores[i] if i < len(scores) else 1.0
                            
                            # 1. 고신뢰 객체 (확신 60% 이상) -> 무조건 통과 (가만히 있어도 인정)
                            if score >= MOTION_CONFIRM_THRESHOLD:
                                filtered_points.append(p)
                                continue
                                
                            # 2. 저신뢰 객체 (확신 20%~60%) -> 움직임 검증 필요 (돌의자 제거)
                            x, y = int(p[0]), int(p[1])
                            # 좌표 유효성 체크
                            if 0 <= x < width and 0 <= y < height:
                                # 해당 좌표 주변(5x5)에 움직임이 있었는지 확인
                                roi_motion = motion_mask[max(0, y-2):min(height, y+3), 
                                                         max(0, x-2):min(width, x+3)]
                                if np.sum(roi_motion) > 0:
                                    filtered_points.append(p)
                        
                        # 필터링된 결과로 업데이트 (numpy array로 변환)
                        result['points'] = np.array(filtered_points) if filtered_points else np.empty((0, 2))
                        result['count'] = len(result['points'])
                        
                        # 재계산
                        result['density'] = m3_api.analyzer.calculate_density(result['count'])
                        result['pct'] = m3_api.analyzer.calculate_pct(result['count'])
                        result['risk_level'] = m3_api.analyzer.get_risk_level(result['pct'])
                    
                    last_result = result
                    
                except Exception as e:
                    print(f"⚠️ 프레임 {frame_count} 분석 실패: {str(e)}")
            
            # 시각화 (마지막 분석 결과 사용)
            if last_result:
                display_frame = draw_analysis_result(
                    display_frame,
                    last_result,
                    frame_count,
                    total_frames
                )
            
            # 화면 표시용 프레임 (축소)
            display_frame_resized = cv2.resize(display_frame, (display_width, display_height))
            cv2.imshow('M3 P2PNet - CCTV Congestion Analysis', display_frame_resized)
            
            # 출력 영상 저장 (원본 크기)
            if out:
                out.write(display_frame)
            
            # ESC 키로 종료
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                print("\n⏸️ 사용자가 중지했습니다.")
                break
            
            frame_count += 1
            
            # 진행률 표시 (100프레임마다)
            if frame_count % 100 == 0:
                percent = (frame_count / total_frames) * 100
                print(f"  진행률: {percent:.1f}%")
    
    finally:
        cap.release()
        if out:
            out.release()
        cv2.destroyAllWindows()
    
    print(f"\n✅ 영상 처리 완료: {frame_count}/{total_frames} 프레임")
    if save_output:
        print(f"💾 저장 완료: {output_path}")


def draw_analysis_result(
    frame: np.ndarray,
    result: dict,
    frame_number: int,
    total_frames: int
) -> np.ndarray:
    """
    프레임에 분석 결과 그리기
    """
    height, width = frame.shape[:2]
    
    # 1. 검출된 사람 위치에 점 표시
    points = result.get('points', [])
    if len(points) > 0:
        for point in points:
            x, y = int(point[0]), int(point[1])
            
            # 시각적 보정: 점을 약간 아래로 이동 (머리 위 → 얼굴/몸통)
            # 주의: 고정값(100)은 멀리 있는 사람에게 너무 큽니다. 일단 0으로 설정하여 정확한 위치를 확인하세요.
            y_offset = 0
            y = y + y_offset
            
            # 빨간색 원으로 표시 (크기 확대: 5 -> 8)
            cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)
            # 흰색 테두리 (크기 확대: 6 -> 10)
            cv2.circle(frame, (x, y), 10, (255, 255, 255), 2)
    
    # 2. 위험 등급에 따른 색상
    risk_level = result.get('risk_level')
    if hasattr(risk_level, 'color'):
        color = risk_level.color  # BGR
        level_text = risk_level.korean
    else:
        color = (0, 255, 0)  # 기본 녹색
        level_text = "안전"
    
    # 3. 상단 정보 패널 (반투명 배경)
    overlay = frame.copy()
    panel_height = 180
    cv2.rectangle(overlay, (0, 0), (width, panel_height), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
    
    # 4. 텍스트 정보 표시
    count = result.get('count', 0)
    pct = result.get('pct', 0)
    
    # 인원 수
    text1 = f"인원: {count}명"
    frame = put_korean_text(frame, text1, (30, 30), font_size=50, color=(255, 255, 255))
    
    # 혼잡도
    text2 = f"혼잡도: {pct:.1f}%"
    frame = put_korean_text(frame, text2, (30, 90), font_size=50, color=(255, 255, 255))
    
    # 등급
    text3 = f"등급: {level_text}"
    frame = put_korean_text(frame, text3, (30, 150), font_size=40, color=color)
    
    # 5. 혼잡도 게이지 바
    gauge_x = width - 350
    gauge_y = 30
    gauge_width = 300
    gauge_height = 30
    
    cv2.rectangle(frame, (gauge_x, gauge_y), (gauge_x + gauge_width, gauge_y + gauge_height), (100, 100, 100), -1)
    fill_width = int((pct / 100) * gauge_width)
    cv2.rectangle(frame, (gauge_x, gauge_y), (gauge_x + fill_width, gauge_y + gauge_height), color, -1)
    cv2.rectangle(frame, (gauge_x, gauge_y), (gauge_x + gauge_width, gauge_y + gauge_height), (255, 255, 255), 2)
    
    gauge_text = f"{pct:.0f}%"
    cv2.putText(frame, gauge_text, (gauge_x + gauge_width + 10, gauge_y + 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # 6. 진행률
    progress_text = f"Frame: {frame_number}/{total_frames}"
    cv2.putText(frame, progress_text, (30, height - 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # 7. 등급 아이콘
    icon_size = 100
    icon_x = width - icon_size - 30
    icon_y = height - icon_size - 30
    
    cv2.rectangle(frame, (icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size), color, -1)
    cv2.rectangle(frame, (icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size), (255, 255, 255), 3)
    frame = put_korean_text(frame, level_text, (icon_x + 10, icon_y + 30), font_size=35, color=(255, 255, 255))
    
    return frame


if __name__ == "__main__":
    # GPU 체크 로직 추가
    import torch
    import sys
    
    print("="*70)
    print("🔍 시스템 환경 점검")
    print(f"  - PyTorch 버전: {torch.__version__}")
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"  - ✅ GPU 감지됨: {gpu_name}")
        print(f"  - CUDA 버전: {torch.version.cuda}")
        print(f"  - cuDNN 버전: {torch.backends.cudnn.version()}")
    else:
        print("  - ❌ GPU(CUDA)를 찾을 수 없습니다! CPU로 실행됩니다.")
        print("  - ⚠️  속도가 매우 느릴 수 있습니다.")
        print("  - 해결책: PyTorch를 CUDA 버전으로 재설치하세요.")
        # 확인을 위해 잠시 대기하거나 종료
        # sys.exit(1) 
    print("="*70)

    # 시각화 테스트
    print("🎬 M3 P2PNet 영상 분석 시각화")
    print("="*70)
    
    # 테스트 영상 경로
    test_video = "C:/Users/user/m3_p2pnet/M3_dbtest/video/IMG_3579.mov"
    # test_video = "C:/Users/user/m3_p2pnet/M3_dbtest/video/IMG_3577.mov"
    # test_video = "C:/Users/user/m3_p2pnet/M3_dbtest/video/test_video.mp4"
    # test_video = "C:/Users/user/m3_p2pnet/M3_dbtest/video/IMG_3583_div.mp4"
    
    print("\n🔄 모델 로딩 중...")
    
    # ROI 설정 없이 순수 성능으로 탐지
    # Threshold 조정: 0.5 -> 0.35 (민감도 향상)
    from constants import DEFAULT_THRESHOLD
    m3_api = M3CongestionAPI(
        model_path=os.getenv('MODEL_PATH'),
        p2pnet_source_path=os.getenv('P2PNET_SOURCE'),
        device='cuda',
        max_capacity=200,
        alert_threshold=50,
        roi_polygon=None  # ROI 제거
    )
    
    # 강제로 임계값 조정 (필요시)
    # m3_api.analyzer.threshold = 0.35
    
    print("✅ 모델 로드 완료!\n")
    
    if not os.path.exists(test_video):
        print(f"❌ 영상 파일을 찾을 수 없습니다: {test_video}")
        print("💡 경로를 확인하세요.")
    else:
        # 영상 시각화 실행
        visualize_video_analysis(
            video_path=test_video,
            m3_api=m3_api,
            frame_skip=10,  
            save_output=True,
            output_path="C:/Users/user/m3_p2pnet/M3_dbtest/video_test_result/test_analyzed_motion5.mp4",
            use_motion_filter=True  # 동작 필터 활성화
        )
        
        print("\n✅ 완료!")
        print("💡 분석된 영상이 저장되었습니다. 이것을 시연에 사용하세요!")
