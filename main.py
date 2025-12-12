%%writefile main.py
import os
import sqlite3
import csv
from datetime import datetime, timedelta
from kivy.lang import Builder
from kivy.utils import platform
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.button import MDRaisedButton

# مكاتب اللغة العربية
import arabic_reshaper
from bidi.algorithm import get_display

# مكاتب PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# استيراد واجهة الكاميرا (سنحاول استيرادها لتجنب الخطأ في الكمبيوتر)
try:
    from kivy_garden.zbarcam import ZBarCam
except ImportError:
    ZBarCam = None

# --- دالة معالجة النص العربي ---
def fix_text(text):
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# --- إعداد قاعدة البيانات ---
def init_db():
    db_path = os.path.join(os.getcwd(), "canteen.db")
    # في الاندرويد نستخدم مسار خاص للتطبيق
    if platform == 'android':
        from android.storage import app_storage_path
        app_root = app_storage_path()
        db_path = os.path.join(app_root, "canteen.db")
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        dob TEXT,
        gender TEXT,
        class_name TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        student_id TEXT,
        date TEXT,
        timestamp TEXT,
        PRIMARY KEY (student_id, date)
    )
    """)
    conn.commit()
    conn.close()
    return db_path

# --- تصميم الواجهة (KV) ---
KV = '''
#:import ZBarCam kivy_garden.zbarcam.ZBarCam

MDScreenManager:
    HomeScreen:
    ScanScreen:
    StatsScreen:

<HomeScreen>:
    name: 'home'
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: app.theme_cls.bg_light
        
        MDTopAppBar:
            title: app.fix_text("مطعم المدرسة")
            elevation: 4
            pos_hint: {"top": 1}
            right_action_items: [["file-import", lambda x: app.import_csv_dialog()]]

        MDBoxLayout:
            orientation: 'vertical'
            padding: dp(20)
            spacing: dp(20)
            
            MDLabel:
                text: app.fix_text("نظام تسجيل الحضور")
                halign: "center"
                font_style: "H5"
                theme_text_color: "Primary"

            MDFillRoundFlatIconButton:
                icon: "camera"
                text: app.fix_text("تسجيل الدخول (مسح QR)")
                font_size: "18sp"
                pos_hint: {"center_x": .5}
                size_hint_x: 0.8
                on_release: root.manager.current = 'scan'

            MDFillRoundFlatIconButton:
                icon: "chart-bar"
                text: app.fix_text("إحصائيات الغياب والحضور")
                font_size: "18sp"
                pos_hint: {"center_x": .5}
                size_hint_x: 0.8
                on_release: 
                    app.load_stats()
                    root.manager.current = 'stats'

            MDFillRoundFlatIconButton:
                icon: "alert"
                text: app.fix_text("الغائبون (15 يوم)")
                font_size: "18sp"
                pos_hint: {"center_x": .5}
                size_hint_x: 0.8
                md_bg_color: 1, 0, 0, 1
                on_release: app.show_15_days_absent()
            Widget:

<ScanScreen>:
    name: 'scan'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: app.fix_text("مسح الرمز")
            left_action_items: [["arrow-left", lambda x: app.change_screen('home')]]
        
        MDBoxLayout:
            id: zbarcam_container
            # سيتم إضافة الكاميرا هنا برمجياً لتجنب المشاكل
        
        MDLabel:
            text: app.fix_text("وجه الكاميرا نحو الرمز")
            halign: "center"
            size_hint_y: 0.1

<StatsScreen>:
    name: 'stats'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: app.fix_text("الإحصائيات")
            left_action_items: [["arrow-left", lambda x: app.change_screen('home')]]
            right_action_items: [["file-pdf-box", lambda x: app.export_pdf()]]

        ScrollView:
            MDBoxLayout:
                id: stats_container
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(10)
                adaptive_height: True

                MDTextField:
                    id: date_field
                    hint_text: "YYYY-MM-DD"
                    text: app.get_today_date()
                    on_text_validate: app.load_stats(self.text)
                
                MDLabel:
                    id: summary_label
                    text: "..."
                    halign: "center"
                    adaptive_height: True
                    font_style: "Subtitle1"
                
                MDLabel:
                    text: app.fix_text("قائمة الغياب")
                    halign: "right"
                    font_style: "H6"
                
                MDBoxLayout:
                    id: absent_box
                    orientation: 'vertical'
                    adaptive_height: True
'''

class CanteenApp(MDApp):
    dialog = None
    db_path = "canteen.db"
    is_processing_scan = False

    def build(self):
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.material_style = "M3"
        self.db_path = init_db()
        return Builder.load_string(KV)

    def on_start(self):
        # هذه الخطوة الأهم لمنع التوقف: طلب الأذونات
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA, 
                Permission.WRITE_EXTERNAL_STORAGE, 
                Permission.READ_EXTERNAL_STORAGE
            ])
        
        # إضافة الكاميرا برمجياً إذا كنا في شاشة المسح
        # (نقوم بذلك لتفادي تحميلها قبل الأذونات)
        Clock.schedule_once(self.setup_camera, 1)

    def setup_camera(self, dt):
        try:
            from kivy_garden.zbarcam import ZBarCam
            scan_screen = self.root.get_screen('scan')
            zbarcam = ZBarCam()
            zbarcam.ids.xcamera.play = True
            zbarcam.bind(symbols=self.on_symbols)
            scan_screen.ids.zbarcam_container.add_widget(zbarcam)
        except ImportError:
            print("ZBarCam not found (Expected in Colab simulation)")
        except Exception as e:
            print(f"Camera Error: {e}")

    def fix_text(self, text):
        return fix_text(text)

    def change_screen(self, screen_name):
        self.root.current = screen_name

    def get_today_date(self):
        return datetime.now().strftime("%Y-%m-%d")

    def on_symbols(self, instance, symbols):
        if self.is_processing_scan:
            return
            
        if not symbols:
            return

        # أخذ أول رمز يتم اكتشافه
        symbol = symbols[0]
        qr_content = symbol.data.decode('utf-8')
        
        self.is_processing_scan = True
        self.process_qr_code(qr_content)

    def process_qr_code(self, qr_content):
        today = self.get_today_date()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. البحث عن الطالب
        cursor.execute("SELECT * FROM students WHERE id=?", (qr_content,))
        student = cursor.fetchone()
        
        if not student:
            self.show_popup(fix_text("خطأ"), fix_text("التلميذ غير مسجل"), error=True)
        else:
            # 2. التحقق من الحضور
            cursor.execute("SELECT * FROM attendance WHERE student_id=? AND date=?", (qr_content, today))
            attendance = cursor.fetchone()
            
            if attendance:
                self.show_popup(fix_text("تنبيه"), fix_text("تم تسجيل الدخول سابقاً!"), error=True)
            else:
                cursor.execute("INSERT INTO attendance VALUES (?,?,?)", (qr_content, today, datetime.now().strftime("%H:%M:%S")))
                conn.commit()
                
                info = f"{student[1]} {student[2]}\n{fix_text('القسم')}: {student[5]}"
                self.show_popup(fix_text("تم التسجيل"), fix_text(info), error=False)
        
        conn.close()

    def show_popup(self, title, text, error=False):
        color = "#B71C1C" if error else "#1B5E20" # Red or Green
        
        # زر لإغلاق النافذة يدوياً
        close_btn = MDRaisedButton(
            text=fix_text("حسناً"),
            on_release=self.dismiss_dialog
        )

        self.dialog = MDDialog(
            title=title,
            text=text,
            buttons=[close_btn],
            md_bg_color=[0.9, 0.9, 0.9, 1]
        )
        # تخصيص لون النص يدوياً عبر KivyMD قد يتطلب widgets مخصصة، لكن MDDialog يفي بالغرض
        self.dialog.open()
        
        # إغلاق تلقائي بعد 4 ثواني
        Clock.schedule_once(self.dismiss_dialog, 4)

    def dismiss_dialog(self, *args):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None
        # السماح بالمسح مرة أخرى بعد اختفاء الرسالة
        self.is_processing_scan = False

    def import_csv_dialog(self):
        # لاستيراد الملفات، في الاندرويد يجب وضع الملف في مجلد التنزيلات او المستندات
        # للتبسيط هنا سنفترض وجود ملف في مسار التطبيق، لكن في التطبيق الحقيقي يفضل استخدام FileChooser
        # هنا سنضع كود تجريبي لإضافة بيانات
        self.seed_dummy_data()
        MDSnackbar(MDLabel(text=fix_text("تم تحميل بيانات تجريبية (للإختبار)"))).open()

    def seed_dummy_data(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        students = [
            ("1001", "Ahmad", "Ali", "2010", "M", "1A"),
            ("1002", "Sara", "Mounir", "2010", "F", "1A"),
            ("1003", "Omar", "Khaled", "2011", "M", "2B"),
        ]
        for s in students:
            cursor.execute("INSERT OR REPLACE INTO students VALUES (?,?,?,?,?,?)", s)
        conn.commit()
        conn.close()

    def load_stats(self, date_query=None):
        if not date_query:
            date_query = self.get_today_date()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM students")
        all_st = cursor.fetchall()
        
        cursor.execute("SELECT student_id FROM attendance WHERE date=?", (date_query,))
        present_ids = [r[0] for r in cursor.fetchall()]
        
        # حساب الإحصائيات
        total_m = sum(1 for s in all_st if s[4]=='M')
        total_f = sum(1 for s in all_st if s[4]=='F')
        
        present_m = sum(1 for s in all_st if s[0] in present_ids and s[4]=='M')
        present_f = sum(1 for s in all_st if s[0] in present_ids and s[4]=='F')
        
        absent_m = total_m - present_m
        absent_f = total_f - present_f
        
        summary = f"{fix_text('التاريخ')}: {date_query}\n" \
                  f"{fix_text('المسجلين')}: {len(present_ids)} ({fix_text('ذ')}:{present_m} | {fix_text('إ')}:{present_f})\n" \
                  f"{fix_text('الغائبين')}: {len(all_st)-len(present_ids)} ({fix_text('ذ')}:{absent_m} | {fix_text('إ')}:{absent_f})"
        
        self.root.get_screen('stats').ids.summary_label.text = summary
        
        box = self.root.get_screen('stats').ids.absent_box
        box.clear_widgets()
        
        # عرض الغائبين
        box.add_widget(MDLabel(text=fix_text("- الذكور:"), theme_text_color="Custom", text_color=(0,0,1,1)))
        for s in all_st:
            if s[0] not in present_ids and s[4] == 'M':
                box.add_widget(MDLabel(text=f"{s[1]} {s[2]} ({s[5]})", adaptive_height=True))

        box.add_widget(MDLabel(text=fix_text("- الإناث:"), theme_text_color="Custom", text_color=(1,0,1,1)))
        for s in all_st:
            if s[0] not in present_ids and s[4] == 'F':
                box.add_widget(MDLabel(text=f"{s[1]} {s[2]} ({s[5]})", adaptive_height=True))
                
        conn.close()

    def show_15_days_absent(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        
        query = "SELECT * FROM students WHERE id NOT IN (SELECT student_id FROM attendance WHERE date >= ?)"
        cursor.execute(query, (start_date,))
        absent = cursor.fetchall()
        
        text = ""
        for s in absent:
            text += f"- {s[1]} {s[2]} ({s[5]})\n"
        
        if not text: text = fix_text("لا يوجد")
        self.show_popup(fix_text("غياب 15 يوم"), text)
        conn.close()

    def export_pdf(self):
        # تصدير لمجلد التحميلات في الاندرويد
        file_path = "report.pdf"
        if platform == 'android':
            from android.storage import primary_external_storage_path
            dir_path = os.path.join(primary_external_storage_path(), 'Download')
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            file_path = os.path.join(dir_path, f"Canteen_{self.get_today_date()}.pdf")
            
        c = canvas.Canvas(file_path, pagesize=letter)
        c.drawString(100, 750, "Canteen Report - " + self.get_today_date())
        c.drawString(100, 700, "Please check the app for detailed arabic stats.")
        c.save()
        MDSnackbar(MDLabel(text=f"PDF Saved: {file_path}")).open()

if __name__ == '__main__':
    CanteenApp().run()
