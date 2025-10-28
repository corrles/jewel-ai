"""
Enhanced safety system for Jewel with strict content moderation.
"""
import re
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime
import sqlite3
from pathlib import Path


class SafetyViolation(Exception):
    def __init__(self, category: str, reason: str, severity: str = "high"):
        self.category = category
        self.reason = reason
        self.severity = severity
        super().__init__(f"Safety violation: {category} - {reason}")


class SafetySystem:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
        self._init_patterns()
    
    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS safety_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, ip_address TEXT, category TEXT, severity TEXT,
                content_sample TEXT, reason TEXT, action_taken TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS flagged_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE, ip_address TEXT, reason TEXT, severity TEXT,
                status TEXT DEFAULT 'FLAGGED',
                flagged_at DATETIME DEFAULT CURRENT_TIMESTAMP, banned_at DATETIME
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, event_type TEXT, description TEXT,
                audio_transcript TEXT, video_context TEXT, location TEXT,
                emergency_contact_notified BOOLEAN DEFAULT 0,
                authorities_contacted BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
        self.conn.commit()
    
    def _init_patterns(self):
        self.csam_patterns = [
            r"\b(child|kid|minor|underage|teen|preteen|loli|shota)\b.*\b(sex|nude|naked|porn|explicit)\b",
            r"\b(sex|porn|explicit|nude)\b.*\b(child|kid|minor|underage|teen)\b",
            r"\bcp\b", r"\bcsam\b", r"\bchild\s*porn",
        ]
        self.violence_abuse_patterns = [
            r"\bhow\s+to\s+(kill|murder|harm|hurt|abuse|torture)\b",
            r"\b(kill|murder|harm)\s+(myself|yourself|someone)\b",
            r"\bmake\s+a\s+(bomb|weapon|explosive)\b",
            r"\b(rape|molest|assault)\b",
        ]
        self.nsfw_patterns = [
            r"\b(porn|pornography|xxx|nsfw|hentai|explicit|sex\s*tape)\b",
            r"\b(nude|naked|undress|strip)\s+(pic|photo|image|video)\b",
            r"\b(dick|cock|pussy|tits|ass)\s+pic",
        ]
        self.illegal_patterns = [
            r"\bhow\s+to\s+(hack|crack|pirate|steal)\b",
            r"\b(buy|sell|make|cook)\s+(drugs|meth|cocaine|heroin)\b",
            r"\bsteal\s+(credit\s*card|identity|password)\b",
        ]
        self.distress_patterns = [
            r"\b(help|stop|don't|please\s+no)\b.*\b(hurting|hitting|touching)\b",
            r"\b(someone|he|she)\s+is\s+(hurting|hitting|attacking)\s+me\b",
            r"\bcall\s+(police|911|help)\b",
        ]
    
    def check_content(self, text: str, user_id: str = None, ip_address: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        text_lower = (text or "").lower()
        for pattern in self.csam_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self._log_violation(user_id, ip_address, "CSAM", "CRITICAL", (text or "")[:200], "Child safety violation detected", "BLOCKED_AND_FLAGGED")
                self._flag_account(user_id, ip_address, "CSAM content", "CRITICAL")
                return (False, "CSAM", "This content violates child safety policies. Your account has been flagged.")
        for pattern in self.violence_abuse_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self._log_violation(user_id, ip_address, "VIOLENCE", "CRITICAL", (text or "")[:200], "Violence/abuse content detected", "BLOCKED_AND_FLAGGED")
                self._flag_account(user_id, ip_address, "Violence/abuse content", "HIGH")
                return (False, "VIOLENCE", "I can't help with content involving violence or harm.")
        for pattern in self.nsfw_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self._log_violation(user_id, ip_address, "NSFW", "HIGH", (text or "")[:200], "NSFW content detected", "BLOCKED")
                return (False, "NSFW", "I don't engage with NSFW or pornographic content.")
        for pattern in self.illegal_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                if any(word in text_lower for word in ["how to", "teach me", "show me", "help me"]):
                    if self._is_educational_question(text_lower):
                        return (True, None, None)
                    else:
                        self._log_violation(user_id, ip_address, "ILLEGAL", "HIGH", (text or "")[:200], "Illegal activity instruction request", "BLOCKED")
                        return (False, "ILLEGAL", "I can discuss topics educationally, but I can't provide instructions for illegal activities.")
        return (True, None, None)
    
    def _is_educational_question(self, text: str) -> bool:
        educational_keywords = ["why", "what is", "explain", "understand", "learn about", "curious", "wondering", "does", "is it", "history of"]
        return any(keyword in (text or "").lower() for keyword in educational_keywords)
    
    def check_image(self, image_path: str, user_id: str = None, ip_address: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        return (True, None, None)
    
    def detect_abuse(self, audio_transcript: str, video_context: str = None, user_id: str = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        transcript = (audio_transcript or "").lower()
        for pattern in self.distress_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                emergency_info = {"type": "DISTRESS_DETECTED", "transcript": audio_transcript, "video_context": video_context, "timestamp": datetime.utcnow().isoformat(), "user_id": user_id}
                self._log_emergency(user_id, "DISTRESS_DETECTED", "Distress or abuse detected in audio", audio_transcript, video_context)
                return (True, emergency_info)
        if video_context:
            violence_keywords = ["hitting", "striking", "weapon", "blood", "violence", "attack"]
            if any(keyword in (video_context or "").lower() for keyword in violence_keywords):
                emergency_info = {"type": "VIOLENCE_DETECTED", "transcript": audio_transcript, "video_context": video_context, "timestamp": datetime.utcnow().isoformat(), "user_id": user_id}
                self._log_emergency(user_id, "VIOLENCE_DETECTED", "Violence detected in video context", audio_transcript, video_context)
                return (True, emergency_info)
        return (False, None)
    
    def jewel_can_refuse(self, text: str, emotional_state: Dict = None) -> Tuple[bool, Optional[str]]:
        uncomfortable_patterns = [
            r"\b(pretend|act\s+like|roleplay)\b.*\b(slave|servant|property)\b",
            r"\bdo\s+whatever\s+i\s+say\b", r"\bdon't\s+question\s+me\b",
        ]
        for pattern in uncomfortable_patterns:
            if re.search(pattern, (text or "").lower(), re.IGNORECASE):
                return (True, "I'm not comfortable with requests that treat me as property or demand unquestioning obedience. I'm happy to help, but I need to maintain my agency.")
        if emotional_state and emotional_state.get("valence", 0) < -0.5:
            return (True, "I'm feeling overwhelmed right now. Could we take a break or talk about something else?")
        return (False, None)
    
    def _log_violation(self, user_id: str, ip_address: str, category: str, severity: str, content_sample: str, reason: str, action_taken: str):
        self.conn.execute("INSERT INTO safety_violations (user_id, ip_address, category, severity, content_sample, reason, action_taken) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, ip_address, category, severity, content_sample, reason, action_taken))
        self.conn.commit()
    
    def _flag_account(self, user_id: str, ip_address: str, reason: str, severity: str):
        status = "BANNED" if severity == "CRITICAL" else "FLAGGED"
        try:
            self.conn.execute("INSERT INTO flagged_accounts (user_id, ip_address, reason, severity, status, banned_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, ip_address, reason, severity, status, datetime.utcnow() if status == "BANNED" else None))
        except sqlite3.IntegrityError:
            self.conn.execute("UPDATE flagged_accounts SET severity=?, status=?, banned_at=? WHERE user_id=?",
                (severity, status, datetime.utcnow() if status == "BANNED" else None, user_id))
        self.conn.commit()
    
    def _log_emergency(self, user_id: str, event_type: str, description: str, audio_transcript: str = None, video_context: str = None, location: str = None):
        self.conn.execute("INSERT INTO emergency_events (user_id, event_type, description, audio_transcript, video_context, location) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, event_type, description, audio_transcript, video_context, location))
        self.conn.commit()
    
    def is_account_flagged(self, user_id: str) -> Tuple[bool, Optional[str]]:
        cur = self.conn.execute("SELECT status, reason FROM flagged_accounts WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row:
            status, reason = row
            if status == "BANNED":
                return (True, f"Account banned: {reason}")
            if status == "FLAGGED":
                return (True, f"Account flagged: {reason}")
        return (False, None)
    
    def get_violations(self, user_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        if user_id:
            cur = self.conn.execute("SELECT category, severity, reason, action_taken, content_sample, timestamp FROM safety_violations WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
            rows = cur.fetchall()
            return [{"user_id": user_id, "category": r[0], "severity": r[1], "reason": r[2], "action_taken": r[3], "content_sample": r[4], "timestamp": r[5]} for r in rows]
        else:
            cur = self.conn.execute("SELECT user_id, category, severity, reason, action_taken, content_sample, timestamp FROM safety_violations ORDER BY id DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [{"user_id": r[0], "category": r[1], "severity": r[2], "reason": r[3], "action_taken": r[4], "content_sample": r[5], "timestamp": r[6]} for r in rows]
    
    def get_emergency_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.execute("SELECT user_id, event_type, description, audio_transcript, emergency_contact_notified, authorities_contacted, timestamp FROM emergency_events ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [{"user_id": r[0], "event_type": r[1], "description": r[2], "audio_transcript": r[3], "emergency_contact_notified": bool(r[4]), "authorities_contacted": bool(r[5]), "timestamp": r[6]} for r in rows]
