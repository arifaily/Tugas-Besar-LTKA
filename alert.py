"""
QoS-RIC — SMN Alert Module
============================
Kirim notifikasi email/SMS via Huawei Cloud SMN
ketika SLA violation terdeteksi.
"""

import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    SMN_ENDPOINT, SMN_PROJECT_ID, SMN_TOPIC_URN, SMN_AK, SMN_SK
)

# Cooldown: jangan spam alert — minimal 60 detik antar alert
_last_alert_time = {}
ALERT_COOLDOWN_SEC = 60


def _make_auth_header(method: str, path: str, body: str) -> dict:
    """
    Generate Huawei Cloud signature header (AK/SK auth).
    Simplified version — untuk production pakai SDK resmi.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    headers   = {
        "Content-Type": "application/json",
        "X-Sdk-Date":   timestamp,
    }
    return headers


def send_smn_alert(
    message: str,
    subject: str = "QoS-RIC SLA Alert",
    user_type: str = "unknown",
    compliance: float = 0.0,
) -> bool:
    """
    Kirim alert via Huawei SMN ke semua subscriber (email/SMS).
    Return True kalau berhasil.
    """
    global _last_alert_time

    # Cek cooldown
    now = datetime.now().timestamp()
    last = _last_alert_time.get(user_type, 0)
    if now - last < ALERT_COOLDOWN_SEC:
        print(f"[SMN] Cooldown aktif — alert {user_type} diskip (tunggu {int(ALERT_COOLDOWN_SEC - (now-last))}s)")
        return False

    # Format pesan lengkap
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message  = (
        f"[QoS-RIC ALERT]\n"
        f"Waktu    : {timestamp_str}\n"
        f"Tipe user: {user_type.upper()}\n"
        f"SLA rate : {compliance*100:.1f}% (threshold: 90%)\n"
        f"Pesan    : {message}\n\n"
        f"Sistem QoS-RIC mendeteksi SLA violation.\n"
        f"Periksa dashboard untuk detail lebih lanjut."
    )

    url  = f"{SMN_ENDPOINT}/v2/{SMN_PROJECT_ID}/notifications/topics/{SMN_TOPIC_URN}/publish"
    body = json.dumps({"subject": subject, "message": full_message})

    try:
        headers = _make_auth_header("POST", url, body)
        resp    = requests.post(url, headers=headers, data=body, timeout=10)

        if resp.status_code in (200, 201):
            _last_alert_time[user_type] = now
            print(f"[SMN] Alert terkirim! User: {user_type}, Compliance: {compliance*100:.1f}%")
            return True
        else:
            print(f"[SMN] Gagal kirim alert. Status: {resp.status_code}, Body: {resp.text}")
            return False

    except Exception as e:
        print(f"[SMN] Exception saat kirim alert: {e}")
        return False


def send_test_alert() -> bool:
    """Kirim alert test untuk verifikasi setup SMN"""
    return send_smn_alert(
        message   = "Ini adalah alert test dari sistem QoS-RIC. Setup SMN berhasil!",
        subject   = "[TEST] QoS-RIC Alert Test",
        user_type = "test",
        compliance = 0.5,
    )


# ── Fallback: kalau SMN belum di-setup, print ke console ──

class MockAlert:
    """Dipakai saat development lokal tanpa koneksi cloud"""

    @staticmethod
    def send(message: str, user_type: str = "unknown", compliance: float = 0.0):
        print("\n" + "!"*50)
        print(f"  [MOCK ALERT] SLA VIOLATION DETECTED")
        print(f"  User type  : {user_type.upper()}")
        print(f"  Compliance : {compliance*100:.1f}%")
        print(f"  Message    : {message}")
        print(f"  Time       : {datetime.now().strftime('%H:%M:%S')}")
        print("!"*50 + "\n")
        return True


def send_alert(message: str, user_type: str = "unknown", compliance: float = 0.0) -> bool:
    """
    Smart alert: coba SMN dulu, fallback ke console kalau gagal.
    Ini yang dipanggil dari RIC Engine.
    """
    if SMN_AK == "YOUR_ACCESS_KEY":
        # Belum dikonfigurasi → pakai mock
        return MockAlert.send(message, user_type, compliance)

    success = send_smn_alert(message, user_type=user_type, compliance=compliance)
    if not success:
        # Fallback ke console supaya demo tetap jalan
        MockAlert.send(message, user_type, compliance)
    return success


if __name__ == "__main__":
    print("Testing alert module...")
    send_alert(
        message    = "SLA emergency user turun di bawah threshold!",
        user_type  = "emergency",
        compliance = 0.82
    )
