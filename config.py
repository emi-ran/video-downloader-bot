import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'emiran_admin_secret_key_2024'
    DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
    
    # Production ayarları
    DEBUG = False
    TESTING = False
    
    # Güvenlik ayarları
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Dosya yükleme limitleri
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    pass

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 