"""
P2PNet 모델 로더
"""

import torch
import sys


class P2PNetModel:
    """
    P2PNet 모델 로더 및 관리 클래스
    """
    def __init__(self, model_path, p2pnet_source_path, device='cuda', use_fp16=True):
        """
        Args:
            model_path: 학습된 모델 파일 경로 (.pth)
            p2pnet_source_path: P2PNet 소스 코드 경로
            device: 'cuda' 또는 'cpu'
            use_fp16: 반정밀도(FP16) 사용 여부 (속도 향상)
        """
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        
        if self.device.type == 'cpu':
            print("\n" + "!"*50)
            print("⚠️  경고: GPU(CUDA)를 사용할 수 없어 CPU 모드로 실행됩니다.")
            print("    처리 속도가 매우 느릴 수 있습니다.")
            print("!"*50 + "\n")
        
        self.model_path = model_path
        self.use_fp16 = use_fp16 and self.device.type == 'cuda'
        
        # P2PNet 소스 경로 추가
        if p2pnet_source_path not in sys.path:
            sys.path.insert(0, p2pnet_source_path)
        
        from models import build_model
        
        # Args 설정
        class Args:
            backbone = 'vgg16_bn'
            row = 2
            line = 2
        
        args = Args()
        
        # 모델 생성 및 로드
        self.model = build_model(args, training=False)
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model'])
        self.model.to(self.device)
        
        if self.use_fp16:
            self.model.half()  # FP16 변환
            print("⚡ P2PNet: FP16(반정밀도) 모드 활성화")
            
        self.model.eval()
        
        # cuDNN 벤치마크 활성화 (속도 최적화)
        if self.device.type == 'cuda':
            torch.backends.cudnn.benchmark = True
        
        print(f"✅ P2PNet 모델 로드 완료 (device: {self.device})")
    
    def get_model(self):
        """모델 객체 반환"""
        return self.model
    
    def predict(self, img_tensor):
        """
        추론 실행
        
        Args:
            img_tensor: 전처리된 이미지 텐서 (1, 3, H, W)
        
        Returns:
            outputs: 모델 출력 (dict)
        """
        with torch.no_grad():
            outputs = self.model(img_tensor)
        return outputs

