import subprocess
import time
import os
from datetime import datetime

LOG_FILE = os.path.expanduser("~/satwatch/scheduler.log")
PIPELINE = os.path.expanduser("~/satwatch/satwatch_pipeline.py")
PYTHON = os.path.expanduser("~/satwatch/venv/bin/python")
INTERVAL_HOURS = 6

def log(msg):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def run_pipeline():
    log("Pipeline başlatılıyor...")
    try:
        result = subprocess.run(
            [PYTHON, PIPELINE],
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                log(f"  {line}")
            log("Pipeline başarıyla tamamlandı.")
        else:
            log(f"Pipeline hatası: {result.stderr[-200:]}")
    except subprocess.TimeoutExpired:
        log("Pipeline zaman aşımına uğradı (10 dakika)")
    except Exception as e:
        log(f"Beklenmeyen hata: {e}")

if __name__ == "__main__":
    log(f"SatWatch Scheduler başlatıldı — her {INTERVAL_HOURS} saatte bir çalışacak")
    log(f"Log dosyası: {LOG_FILE}")
    log(f"Durdurmak için: Ctrl+C\n")

    # İlk çalıştırma
    run_pipeline()

    # Döngü
    while True:
        next_run = INTERVAL_HOURS * 3600
        log(f"Sonraki çalışma: {INTERVAL_HOURS} saat sonra")
        time.sleep(next_run)
        run_pipeline()
