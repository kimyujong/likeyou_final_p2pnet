"""
Supabase 데이터베이스 연동 모듈

분석 결과 및 경보 이력을 Supabase에 저장/조회
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

logger = logging.getLogger(__name__)


class SupabaseDB:
    """Supabase 데이터베이스 클라이언트"""
    
    def __init__(self):
        """Supabase 클라이언트 초기화"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            logger.warning("⚠️ Supabase 환경변수가 설정되지 않았습니다. DB 기능이 비활성화됩니다.")
            self.client = None
            self.enabled = False
            return
        
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
            self.enabled = True
            logger.info("✅ Supabase 연결 성공!")
        except Exception as e:
            logger.error(f"❌ Supabase 연결 실패: {str(e)}")
            self.client = None
            self.enabled = False
    
    def is_enabled(self) -> bool:
        """DB 연결 상태 확인"""
        return self.enabled and self.client is not None
    
    async def save_analysis_result(
        self,
        cctv_no: str,
        person_count: int,
        congestion_level: int,
        risk_level_int: int
    ) -> Optional[Dict[str, Any]]:
        """
        분석 결과를 DAT_Crowd_Detection 테이블에 저장
        
        Args:
            cctv_no: CCTV 식별자 (UUID) - COM_CCTV 테이블에 존재해야 함
            person_count: 감지된 인원 수
            congestion_level: 혼잡도 (0-100%)
            risk_level_int: 위험 등급 (1:안전, 2:주의, 3:경고, 4:위험)
        
        Returns:
            저장된 데이터 또는 None
        """
        if not self.is_enabled():
            logger.warning("DB가 비활성화되어 있습니다. 데이터를 저장하지 않습니다.")
            return None
        
        try:
            # DAT_Crowd_Detection 테이블 스키마에 맞춰 데이터 구성
            data = {
                'cctv_no': cctv_no,
                'detected_at': datetime.now(timezone.utc).isoformat(),
                'person_count': person_count,
                'congestion_level': congestion_level,
                'risk_level': risk_level_int,
                'status': 'NEW',     # 기본값: 미처리(NEW)
                'cleared_by': None   # 초기값: NULL
            }
            
            response = self.client.table('DAT_Crowd_Detection').insert(data).execute()
            
            logger.info(f"✅ 분석 결과 저장 완료: CCTV={cctv_no}, Count={person_count}, Level={congestion_level}%")
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"❌ 분석 결과 저장 실패: {str(e)}")
            return None
    
    async def get_test_cctv_no(self) -> Optional[str]:
        """
        테스트용 CCTV 번호(UUID) 조회 (COM_CCTV 테이블에서 1개)
        
        Returns:
            cctv_no (UUID) 또는 None
        """
        if not self.is_enabled():
            return None
        
        try:
            response = self.client.table('COM_CCTV').select('cctv_no').limit(1).execute()
            if response.data:
                return response.data[0]['cctv_no']
            return None
        except Exception as e:
            logger.error(f"❌ CCTV 조회 실패: {str(e)}")
            return None

    async def get_recent_logs(
        self,
        limit: int = 10,
        cctv_no: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        최근 분석 결과 조회
        
        Args:
            limit: 조회할 개수
            cctv_no: CCTV 필터 (선택)
        
        Returns:
            분석 결과 목록
        """
        if not self.is_enabled():
            return []
        
        try:
            query = self.client.table('DAT_Crowd_Detection').select('*')
            
            if cctv_no:
                query = query.eq('cctv_no', cctv_no)
            
            response = query.order('detected_at', desc=True).limit(limit).execute()
            
            logger.info(f"✅ 분석 결과 조회 완료: {len(response.data)}건")
            return response.data
            
        except Exception as e:
            logger.error(f"❌ 분석 결과 조회 실패: {str(e)}")
            return []
    
    async def get_statistics(
        self,
        cctv_no: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        통계 데이터 조회
        
        Args:
            cctv_no: CCTV 필터 (선택)
            start_date: 시작 날짜 (선택)
            end_date: 종료 날짜 (선택)
        
        Returns:
            통계 데이터
        """
        if not self.is_enabled():
            return {}
        
        try:
            query = self.client.table('DAT_Crowd_Detection').select('person_count, congestion_level, risk_level')
            
            if cctv_no:
                query = query.eq('cctv_no', cctv_no)
            
            if start_date:
                query = query.gte('detected_at', start_date)
            
            if end_date:
                query = query.lte('detected_at', end_date)
            
            response = query.execute()
            data = response.data
            
            if not data:
                return {}
            
            # 통계 계산
            counts = [d['person_count'] for d in data]
            levels = [d['congestion_level'] for d in data]
            
            stats = {
                'total_records': len(data),
                'avg_count': sum(counts) / len(counts),
                'max_count': max(counts),
                'min_count': min(counts),
                'avg_level': sum(levels) / len(levels),
                'max_level': max(levels),
                'min_level': min(levels),
                'risk_distribution': {
                    '1_safe': 0,
                    '2_caution': 0,
                    '3_warning': 0,
                    '4_danger': 0
                }
            }
            
            # 위험 등급 분포 (1:안전, 2:주의, 3:경고, 4:위험)
            for d in data:
                level = d['risk_level']
                if level == 1:
                    stats['risk_distribution']['1_safe'] += 1
                elif level == 2:
                    stats['risk_distribution']['2_caution'] += 1
                elif level == 3:
                    stats['risk_distribution']['3_warning'] += 1
                elif level == 4:
                    stats['risk_distribution']['4_danger'] += 1
            
            logger.info(f"✅ 통계 조회 완료: {len(data)}건")
            return stats
            
        except Exception as e:
            logger.error(f"❌ 통계 조회 실패: {str(e)}")
            return {}


# 전역 인스턴스
_db_instance = None


def get_db() -> SupabaseDB:
    """
    Supabase DB 인스턴스 반환 (싱글톤)
    
    Returns:
        SupabaseDB 인스턴스
    """
    global _db_instance
    
    if _db_instance is None:
        _db_instance = SupabaseDB()
    
    return _db_instance


# 편의 함수들
async def save_detection(
    cctv_no: str,
    person_count: int,
    congestion_level: int,
    risk_level_int: int
) -> Optional[Dict[str, Any]]:
    """분석 결과 저장 (간편 함수)"""
    db = get_db()
    return await db.save_analysis_result(
        cctv_no=cctv_no,
        person_count=person_count,
        congestion_level=congestion_level,
        risk_level_int=risk_level_int
    )


async def get_logs(limit: int = 10, cctv_no: Optional[str] = None) -> List[Dict[str, Any]]:
    """분석 로그 조회 (간편 함수)"""
    db = get_db()
    return await db.get_recent_logs(limit=limit, cctv_no=cctv_no)


async def get_test_cctv_no() -> Optional[str]:
    """테스트용 CCTV 번호 조회 (간편 함수)"""
    db = get_db()
    return await db.get_test_cctv_no()


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    import sys
    
    async def test_with_real_image():
        """실제 이미지로 테스트 (M3 모델 + DB 저장)"""
        print("\n" + "="*60)
        print("📸 실제 이미지 분석 + DB 저장 테스트")
        print("="*60 + "\n")
        
        # 테스트 이미지 경로 (환경에 맞게 수정 필요)
        # test_image_path = "C:/Users/user/m3_p2pnet/data/aihub_p2pnet/test/Indoor_EXCO001_479.jpg"
        # 위 경로가 없을 수 있으므로 현재 디렉토리 등에서 찾거나 예외 처리 필요
        # 여기서는 파일 경로를 사용자가 직접 설정해야 함을 가정하거나 더미 데이터로 테스트
        
        # DB 연결 확인
        db = get_db()
        if not db.is_enabled():
            print("❌ Supabase가 설정되지 않았습니다.")
            return
        
        try:
            # 1. 테스트할 CCTV ID 확보 (COM_CCTV 테이블에서 조회)
            print("🔄 COM_CCTV 테이블에서 테스트용 CCTV ID 조회 중...")
            cctv_query = db.client.table('COM_CCTV').select('cctv_no').limit(1).execute()
            
            if not cctv_query.data:
                print("❌ COM_CCTV 테이블이 비어있습니다. 테스트를 진행할 수 없습니다.")
                print("💡 먼저 COM_CCTV 테이블에 데이터를 채워주세요.")
                return
            
            test_cctv_no = cctv_query.data[0]['cctv_no']
            print(f"✅ 테스트용 CCTV ID 확보: {test_cctv_no}")
            
            # 2. 임의의 분석 결과 데이터 생성 (이미지가 없어도 DB 테스트 가능하도록)
            print("\n📊 임의의 분석 데이터 생성 중...")
            person_count = 42
            congestion_level = 20
            risk_level_int = 1 # 안전
            
            print(f"  👥 인원 수: {person_count}명")
            print(f"  📈 혼잡도: {congestion_level}%")
            print(f"  🛡️ 위험 등급: {risk_level_int}")
            
            # 3. Supabase에 저장
            print("\n💾 Supabase에 저장 중...")
            
            db_result = await db.save_analysis_result(
                cctv_no=test_cctv_no,
                person_count=person_count,
                congestion_level=congestion_level,
                risk_level_int=risk_level_int
            )
            
            if db_result:
                print("✅ DB 저장 완료!")
                print(f"\n📝 저장된 데이터:")
                print(f"  - detection_id: {db_result.get('detection_id')}")
                print(f"  - cctv_no: {db_result.get('cctv_no')}")
                print(f"  - person_count: {db_result.get('person_count')}")
                print(f"  - congestion_level: {db_result.get('congestion_level')}%")
                print(f"  - risk_level: {db_result.get('risk_level')}")
                print(f"  - status: {db_result.get('status')}")
                print(f"  - detected_at: {db_result.get('detected_at')}")
            else:
                print("❌ DB 저장 실패")
            
            print("\n" + "="*60)
            print("✅ 테스트 완료!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # 실행
    print("\n🧪 DB 테스트 시작...\n")
    asyncio.run(test_with_real_image())
