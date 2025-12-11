"""
M3 Dummy Data Generator
-----------------------
실제 AI 분석이 돌지 않는 나머지 CCTV들에 대해
가짜(Dummy) 인구 혼잡도 데이터를 주기적으로 생성하여 DB에 주입합니다.

동작 방식:
1. 전체 CCTV 목록 조회 (COM_CCTV)
2. 최근 30초 내 활동이 있었던 CCTV 조회 (DAT_Crowd_Detection) -> Real Mode로 간주
3. (전체 - 활동중) = 비활성 CCTV 목록 추출
4. 비활성 CCTV들에 대해 가짜 데이터 INSERT
"""

import os
import time
import random
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Set

from dotenv import load_dotenv
from supabase import create_client, Client

# 환경변수 로드
load_dotenv()

# 로깅 설정 (간단히 print 사용)
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class DummyGenerator:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in .env")
            
        self.supabase: Client = create_client(url, key)
        self.interval = 60 # 10초 주기
        
    def get_all_cctvs(self) -> Set[str]:
        """모든 CCTV ID 조회"""
        try:
            res = self.supabase.table("COM_CCTV").select("cctv_no").execute()
            return {row['cctv_no'] for row in res.data}
        except Exception as e:
            log(f"❌ Error fetching all CCTVs: {e}")
            return set()

    def get_active_cctvs(self) -> Set[str]:
        """최근 30초 내 데이터가 들어온 CCTV ID 조회"""
        try:
            # Supabase-js 스타일의 필터링이 파이썬 클라이언트에서 제한적일 수 있어
            # 최근 100건을 가져와서 파이썬에서 필터링
            res = self.supabase.table("DAT_Crowd_Detection") \
                .select("cctv_no, detected_at") \
                .order("detected_at", desc=True) \
                .limit(100) \
                .execute()
                
            active_ids = set()
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(seconds=30)
            
            for row in res.data:
                detected_at_str = row['detected_at']
                # ISO format parsing (Handle Z)
                detected_at_str = detected_at_str.replace('Z', '+00:00')
                detected_at = datetime.fromisoformat(detected_at_str)
                
                if detected_at > threshold:
                    active_ids.add(row['cctv_no'])
            
            return active_ids
        except Exception as e:
            log(f"❌ Error fetching active CCTVs: {e}")
            return set()

    def generate_density(self) -> int:
        """랜덤 밀집도 생성 (시연용 패턴)"""
        # 기본적으로 10~40 사이 (한산~보통)
        # 10% 확률로 70~90 (혼잡) 발생
        if random.random() < 0.1:
            return random.randint(70, 95)
        return random.randint(10, 40)

    def insert_dummy_data(self, cctv_ids: List[str]):
        """가짜 데이터 일괄 삽입"""
        if not cctv_ids:
            return

        payload = []
        now_str = datetime.now(timezone.utc).isoformat()
        
        for cctv_no in cctv_ids:
            density = self.generate_density()
            
            # Risk Level 계산 (단순화)
            # 0~20: 1(안전), 21~50: 2(주의), 51~80: 3(경고), 81~100: 4(위험)
            if density <= 20: risk = 1
            elif density <= 50: risk = 2
            elif density <= 80: risk = 3
            else: risk = 4
            
            payload.append({
                "cctv_no": cctv_no,
                "detected_at": now_str,
                "person_count": int(density * 1.5), # 대략적인 인원수
                "congestion_level": density,
                "risk_level": risk,
                "status": "NEW",
                "cleared_by": None
            })
            
        try:
            # 청크 단위로 insert (너무 많으면 에러 날 수 있음)
            chunk_size = 50
            for i in range(0, len(payload), chunk_size):
                batch = payload[i:i+chunk_size]
                self.supabase.table("DAT_Crowd_Detection").insert(batch).execute()
                
            log(f"✅ Inserted dummy data for {len(cctv_ids)} CCTVs.")
        except Exception as e:
            log(f"❌ Error inserting dummy data: {e}")

    def run(self):
        log("🚀 Starting M3 Dummy Data Generator...")
        log("   (Generates data for inactive CCTVs only)")
        
        while True:
            try:
                # 1. 전체 목록
                all_ids = self.get_all_cctvs()
                if not all_ids:
                    log("⚠️ No CCTVs found in DB. Retrying...")
                    time.sleep(self.interval)
                    continue
                
                # 2. 활성 목록
                active_ids = self.get_active_cctvs()
                
                # 3. 대상 선정 (Target = All - Active)
                target_ids = list(all_ids - active_ids)
                
                log(f"📊 Stats: All={len(all_ids)}, Active={len(active_ids)}, Dummy-Target={len(target_ids)}")
                
                # 4. 데이터 삽입
                if target_ids:
                    self.insert_dummy_data(target_ids)
                
            except Exception as e:
                log(f"❌ Unexpected error: {e}")
            
            # 대기
            time.sleep(self.interval)

if __name__ == "__main__":
    generator = DummyGenerator()
    generator.run()

