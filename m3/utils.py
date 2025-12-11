"""
M3 시스템 유틸리티 함수
"""

import cv2
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import torchvision.transforms as transforms


def put_korean_text(img, text, position, font_size=30, color=(255, 255, 255)):
    """
    OpenCV 이미지에 한글 텍스트 표시 (PIL 사용)
    
    Args:
        img: OpenCV BGR 이미지
        text: 표시할 텍스트
        position: (x, y) 위치
        font_size: 폰트 크기
        color: BGR 색상
    
    Returns:
        img: 텍스트가 추가된 이미지
    """
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 한글 폰트 (Windows 기본 폰트)
    try:
        font = ImageFont.truetype("malgun.ttf", font_size)  # 맑은 고딕
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", font_size)
        except:
            font = ImageFont.load_default()  # 폰트 없으면 기본 폰트
    
    # PIL은 RGB를 사용
    color_rgb = (color[2], color[1], color[0]) if len(color) == 3 else color
    draw.text(position, text, font=font, fill=color_rgb)
    
    # 다시 OpenCV로 변환
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    return img_cv


def preprocess_image(image_path):
    """
    이미지를 P2PNet 입력 형식으로 전처리
    P2PNet은 이미지 크기가 128의 배수여야 함
    
    Args:
        image_path: 이미지 파일 경로
    
    Returns:
        img_tensor: PyTorch 텐서
        img_resized: numpy 배열 (RGB)
    """
    # 한글 경로 지원
    with open(image_path, 'rb') as f:
        img_array = np.frombuffer(f.read(), np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    if img is None:
        raise ValueError(f"이미지 로드 실패: {image_path}")
    
    # BGR → RGB
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img)
    
    # 이미지 크기를 128의 배수로 조정 (P2PNet 요구사항)
    width, height = img_pil.size
    new_width = width // 128 * 128
    new_height = height // 128 * 128
    img_pil = img_pil.resize((new_width, new_height), Image.LANCZOS)
    
    # Transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
    img_tensor = transform(img_pil)
    
    # numpy 배열도 리사이즈된 크기로
    img_resized = np.array(img_pil)
    
    return img_tensor, img_resized


def preprocess_frame(frame):
    """
    비디오 프레임을 P2PNet 입력 형식으로 전처리
    
    Args:
        frame: OpenCV BGR 이미지
    
    Returns:
        img_tensor: PyTorch 텐서
    """
    # BGR → RGB
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    
    # 128 배수로 리사이즈
    width, height = img_pil.size
    new_width = width // 128 * 128
    new_height = height // 128 * 128
    img_pil = img_pil.resize((new_width, new_height), Image.LANCZOS)
    
    # Transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
    return transform(img_pil)

