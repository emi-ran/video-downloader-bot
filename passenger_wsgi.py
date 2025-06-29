import sys
import os

# Proje dizinini Python path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

# Doğrudan app.py'den import et
from app import app

# Passenger için application objesi
application = app 