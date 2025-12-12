[app]

title = Canteen Pro
package.name = canteenpro
package.domain = org.school
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db,csv,ttf

version = 1.0.0

# المكتبات المطلوبة بدقة لتجنب الانهيار
requirements = python3,kivy==2.2.0,kivymd,sqlite3,reportlab,kivy-garden,zbarcam,pillow,arabic-reshaper,python-bidi,libzbar

# طلب صلاحيات الكاميرا والتخزين
android.permissions = CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, INTERNET

# إعدادات واجهة برمجة اندرويد
android.api = 33
android.minapi = 21
android.ndk = 25b

# منع التدوير التلقائي (اختياري)
orientation = portrait

# إظهار شاشة البداية باللون الأبيض
android.presplash_color = #FFFFFF

# إضافة مكتبات الكاميرا للنظام داخل التطبيق
android.add_libs_armeabi_v7a = /usr/lib/libzbar.so
android.add_libs_arm64_v8a = /usr/lib/libzbar.so

[buildozer]
log_level = 2
warn_on_root = 0
