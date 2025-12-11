"""
M3 경보 알림 시스템
"""

from datetime import datetime
from constants import DEFAULT_ALERT_THRESHOLD, DEFAULT_ALERT_COOLDOWN


class AlertSystem:
    """
    혼잡도 경보 알림 시스템
    """
    def __init__(self, alert_threshold=DEFAULT_ALERT_THRESHOLD, 
                 alert_cooldown=DEFAULT_ALERT_COOLDOWN):
        """
        Args:
            alert_threshold: 알림 발생 혼잡도 (%)
            alert_cooldown: 중복 알림 방지 대기 시간 (초)
        """
        self.alert_threshold = alert_threshold
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = None
    
    def check_alert(self, pct, risk_level):
        """
        경보 발생 여부 확인
        
        Args:
            pct: 혼잡도 비율 (%)
            risk_level: CongestionLevel
        
        Returns:
            tuple: (should_alert: bool, message: str or None)
        """
        current_time = datetime.now()
        
        # 쿨다운 체크
        if self.last_alert_time:
            elapsed = (current_time - self.last_alert_time).total_seconds()
            if elapsed < self.alert_cooldown:
                return False, None
        
        # 혼잡도 체크
        if pct >= self.alert_threshold:
            self.last_alert_time = current_time
            
            message = f"""
🚨 혼잡도 경보 🚨
━━━━━━━━━━━━━━━━━━━━━━
⏰ 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
📊 혼잡도: {pct:.1f}%
⚠️  위험 등급: {risk_level.korean}
━━━━━━━━━━━━━━━━━━━━━━
조치: 즉시 현장 확인 및 인원 통제 필요
"""
            return True, message
        
        return False, None
    
    def send_alert(self, message, method='console'):
        """
        실제 알림 발송
        
        Args:
            message: 알림 메시지
            method: 'console', 'email', 'sms', 'slack' 등
        """
        if method == 'console':
            print(message)
        
        # TODO: 실제 알림 구현
        # elif method == 'email':
        #     send_email(message)
        # elif method == 'sms':
        #     send_sms(message)
        # elif method == 'slack':
        #     send_slack_webhook(message)
        # elif method == 'db':
        #     save_to_database(message)

