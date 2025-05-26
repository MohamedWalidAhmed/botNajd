from flask import Flask
import os
from dotenv import load_dotenv # لملف .env

# استيراد الـ Blueprint من ملف الويب هوك
from routes.webhook import webhook_bp # <--- هنا الـ import المهم

# تحميل متغيرات البيئة من .env (مهم للتطوير المحلي)
load_dotenv()

app = Flask(__name__)

# إعدادات الـ App (لو عندك أي config خاص ممكن تضيفه هنا)
# app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key')

# تسجيل الـ Blueprint
# لو الـ webhook بتاعك المفروض يكون على المسار الرئيسي (مثلاً /webhook)
app.register_blueprint(webhook_bp)
# لو عايز الـ webhook يكون تحت مسار معين (مثلاً /api/webhook)
# app.register_blueprint(webhook_bp, url_prefix='/api')


if __name__ == "__main__":
    # تأكد إن الـ debug mode مقفول في الإنتاج على Render
    # Render بيستخدم الـ PORT environment variable
    port = int(os.getenv("PORT", 5000))
    # لما تشغل على Render، هو بيستخدم Gunicorn أو ما شابه، فـ app.run() دي بتكون للتطوير المحلي أكتر
    # بس لو Render بيشغل python app.py مباشرة، يبقى دي هتشتغل.
    # الأفضل لـ Render هو استخدام Procfile و gunicorn.
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
