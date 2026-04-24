import sys
from pathlib import Path

# Импорт модулей из src/ без установки пакета
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
