from flask import Flask
import os
from dotenv import load_dotenv

# استيراد Blueprint للويب هوك (تأكد أن المسار صحيح في مشروعك)
from routes.webhook import webhook_bp

# تحميل متغيرات البيئة من .env (مطلوب للتطوير المحلي/الإنتاج)
load_dotenv()

def create_app():
    app = Flask(__name__)

    # إعدادات التطبيق الإضافية (ضع أي إعدادات إضافية هنا)
    # app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

    # تسجيل Blueprint الخاص بالويب هوك
    app.register_blueprint(webhook_bp)
    # إذا أردت استخدام url_prefix:
    # app.register_blueprint(webhook_bp, url_prefix='/api')

    # إعداد لوجينج افتراضي لو لم يكن معرف في ملفات أخرى (مفيد في Render/logs)
    import logging
    if not app.logger.handlers:
        logging.basicConfig(level=logging.INFO)

    return app

app = create_app()

if __name__ == "__main__":
    # إعدادات التشغيل المحلي فقط (Render يشغل Gunicorn غالباً تلقائياً)
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", 'False').lower() == 'true'
    # للتطوير المحلي فقط!
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
