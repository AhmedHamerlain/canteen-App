import os
import csv
from datetime import datetime
import cv2
import openpyxl

from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDFillRoundFlatIconButton, MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.toast import toast
from kivy.metrics import dp

# --- إعدادات الملفات ---
STUDENTS_FILE = 'students.csv'
ATTENDANCE_FILE = 'attendance.csv'

# دالة مساعدة لقراءة ملف CSV وإعادته كقائمة من القواميس
def read_csv_data(filename):
    data = []
    if os.path.exists(filename):
        with open(filename, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    return data

# دالة مساعدة لحفظ البيانات في ملف CSV
def write_csv_data(filename, fieldnames, data):
    with open(filename, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

# التأكد من وجود ملف التلاميذ
if not os.path.exists(STUDENTS_FILE):
    write_csv_data(STUDENTS_FILE, ['id', 'name', 'gender', 'dob', 'class_name'], [])

# ==========================================
# الشاشة الأولى: الماسح الضوئي
# ==========================================
class ScannerScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.capture = None
        self.is_camera_on = False
        self.qr_detector = cv2.QRCodeDetector()
        
        layout = MDBoxLayout(orientation='vertical', padding=20, spacing=20)
        
        self.image = Image(size_hint=(1, 0.7), allow_stretch=True)
        layout.add_widget(self.image)
        
        self.lbl_status = MDLabel(text="جاهز للمسح...", halign="center", theme_text_color="Primary", font_style="H5", size_hint=(1, 0.1))
        layout.add_widget(self.lbl_status)
        
        self.btn_toggle = MDFillRoundFlatIconButton(text="بدء الكاميرا", icon="camera", pos_hint={'center_x': 0.5}, on_release=self.toggle_camera)
        layout.add_widget(self.btn_toggle)
        self.add_widget(layout)

    def load_students_dict(self):
        students = read_csv_data(STUDENTS_FILE)
        return {row['id']: row['name'] for row in students}

    def toggle_camera(self, instance):
        if not self.is_camera_on:
            self.capture = cv2.VideoCapture(0)
            Clock.schedule_interval(self.update_frame, 1.0 / 30.0)
            self.is_camera_on = True
            self.btn_toggle.text = "إيقاف الكاميرا"
            self.btn_toggle.icon = "camera-off"
            self.btn_toggle.md_bg_color = (1, 0, 0, 1)
        else:
            self.stop_camera()

    def stop_camera(self):
        if self.capture:
            self.capture.release()
        Clock.unschedule(self.update_frame)
        self.is_camera_on = False
        self.btn_toggle.text = "بدء الكاميرا"
        self.btn_toggle.icon = "camera"
        self.btn_toggle.md_bg_color = None
        self.image.texture = None

    def update_frame(self, dt):
        ret, frame = self.capture.read()
        if ret:
            data, bbox, _ = self.qr_detector.detectAndDecode(frame)
            if data:
                students_db = self.load_students_dict()
                self.process_attendance(data, students_db)
            
            buf = cv2.flip(frame, 0).tobytes()
            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.image.texture = texture

    def process_attendance(self, student_id, db):
        if student_id in db:
            name = db[student_id]
            today = datetime.now().strftime('%Y-%m-%d')
            
            # قراءة الحضور الحالي
            att_data = read_csv_data(ATTENDANCE_FILE)
            if not att_data and not os.path.exists(ATTENDANCE_FILE):
                 with open(ATTENDANCE_FILE, 'w', encoding='utf-8-sig') as f:
                    f.write('id,name,time,date\n')
            
            # التحقق هل هو مسجل اليوم
            already_present = False
            for row in att_data:
                if row['id'] == student_id and row['date'] == today:
                    already_present = True
                    break
            
            if not already_present:
                now_time = datetime.now().strftime('%H:%M:%S')
                with open(ATTENDANCE_FILE, 'a', encoding='utf-8-sig') as f:
                    f.write(f'{student_id},{name},{now_time},{today}\n')
                
                self.lbl_status.text = f"تم التسجيل: {name}"
                self.lbl_status.text_color = (0, 0.8, 0, 1)
                toast(f"مرحباً {name}")
            else:
                self.lbl_status.text = f"مسجل مسبقاً: {name}"
                self.lbl_status.text_color = (0.9, 0.7, 0, 1)
        else:
            self.lbl_status.text = "طالب غير معروف!"

# ==========================================
# الشاشة الثانية: إدارة التلاميذ
# ==========================================
class StudentsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = MDBoxLayout(orientation='vertical', padding=10, spacing=10)
        
        btn_box = MDBoxLayout(size_hint_y=0.15, spacing=10)
        btn_box.add_widget(MDFillRoundFlatIconButton(text="استيراد Excel", icon="file-excel", on_release=self.open_file_manager))
        btn_box.add_widget(MDFillRoundFlatIconButton(text="إضافة يدوي", icon="account-plus", on_release=self.show_add_dialog))
        btn_box.add_widget(MDIconButton(icon="refresh", on_release=self.load_table))
        self.layout.add_widget(btn_box)

        self.data_table = MDDataTable(
            use_pagination=True, check=True,
            column_data=[("ID", dp(20)), ("الاسم", dp(35)), ("الجنس", dp(15)), ("الميلاد", dp(20)), ("القسم", dp(20))],
            row_data=[]
        )
        self.data_table.bind(on_check_press=self.on_row_check)
        self.layout.add_widget(self.data_table)
        
        self.layout.add_widget(MDRaisedButton(text="حذف المحدد", md_bg_color=(1, 0, 0, 1), size_hint_x=1, on_release=self.delete_selected))
        self.add_widget(self.layout)
        
        self.file_manager = MDFileManager(exit_manager=self.exit_manager, select_path=self.select_path, ext=['.xlsx', '.xls'])
        self.selected_rows = []

    def on_enter(self):
        self.load_table()

    def load_table(self, *args):
        data = read_csv_data(STUDENTS_FILE)
        # تحويل القائمة من القواميس إلى قائمة صفوف للجدول
        table_rows = []
        for row in data:
            table_rows.append((row.get('id'), row.get('name'), row.get('gender'), row.get('dob'), row.get('class_name')))
        self.data_table.row_data = table_rows

    def open_file_manager(self, *args):
        self.file_manager.show(os.path.expanduser("~"))

    def select_path(self, path):
        self.exit_manager()
        try:
            workbook = openpyxl.load_workbook(path, data_only=True)
            sheet = workbook.active
            new_data = []
            
            # تخطي الصف الأول (العناوين) والبدء من الصف الثاني
            for row in sheet.iter_rows(min_row=2, values_only=True):
                # التأكد من أن الصف ليس فارغاً
                if row[0]: 
                    new_data.append({
                        'id': str(row[0]), 'name': str(row[1]), 'gender': str(row[2]),
                        'dob': str(row[3]), 'class_name': str(row[4])
                    })
            
            write_csv_data(STUDENTS_FILE, ['id', 'name', 'gender', 'dob', 'class_name'], new_data)
            toast("تم استيراد القائمة بنجاح")
            self.load_table()
        except Exception as e:
            toast(f"حدث خطأ: {str(e)}")

    def exit_manager(self, *args):
        self.file_manager.close()

    def show_add_dialog(self, *args):
        self.tf_id = MDTextField(hint_text="ID")
        self.tf_name = MDTextField(hint_text="الاسم")
        self.tf_gender = MDTextField(hint_text="الجنس (ذكر/أنثى)")
        self.tf_dob = MDTextField(hint_text="تاريخ الميلاد")
        self.tf_class = MDTextField(hint_text="القسم")
        
        box = MDBoxLayout(orientation='vertical', size_hint_y=None, height=dp(320))
        box.add_widget(self.tf_id)
        box.add_widget(self.tf_name)
        box.add_widget(self.tf_gender)
        box.add_widget(self.tf_dob)
        box.add_widget(self.tf_class)
        
        self.dialog = MDDialog(title="إضافة تلميذ", type="custom", content_cls=box,
            buttons=[MDFlatButton(text="إلغاء", on_release=lambda x: self.dialog.dismiss()),
                     MDRaisedButton(text="حفظ", on_release=self.save_student)])
        self.dialog.open()

    def save_student(self, *args):
        new_row = {
            'id': self.tf_id.text, 'name': self.tf_name.text,
            'gender': self.tf_gender.text, 'dob': self.tf_dob.text,
            'class_name': self.tf_class.text
        }
        if new_row['id']:
            current_data = read_csv_data(STUDENTS_FILE)
            current_data.append(new_row)
            write_csv_data(STUDENTS_FILE, ['id', 'name', 'gender', 'dob', 'class_name'], current_data)
            self.dialog.dismiss()
            self.load_table()
            toast("تمت الإضافة")

    def on_row_check(self, instance_table, current_row):
        student_id = current_row[0]
        if student_id in self.selected_rows:
            self.selected_rows.remove(student_id)
        else:
            self.selected_rows.append(student_id)

    def delete_selected(self, *args):
        if not self.selected_rows: return
        current_data = read_csv_data(STUDENTS_FILE)
        # الاحتفاظ فقط بالطلاب الذين ليسوا في قائمة الحذف
        new_data = [row for row in current_data if row['id'] not in self.selected_rows]
        write_csv_data(STUDENTS_FILE, ['id', 'name', 'gender', 'dob', 'class_name'], new_data)
        self.selected_rows = []
        self.load_table()
        toast("تم الحذف")

# ==========================================
# الشاشة الثالثة: الإحصائيات
# ==========================================
class ReportScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll = ScrollView()
        self.main_layout = MDBoxLayout(orientation='vertical', padding=10, spacing=15, size_hint_y=None)
        self.main_layout.bind(minimum_height=self.main_layout.setter('height'))
        
        self.main_layout.add_widget(MDLabel(text="الإحصائيات العامة لليوم", halign="center", font_style="H6", size_hint_y=None, height=dp(30)))
        
        stats_card = MDCard(orientation='vertical', size_hint_y=None, height=dp(150), padding=10, elevation=2)
        self.grid_stats = MDGridLayout(cols=3, spacing=5, size_hint_y=None, height=dp(120))
        
        for h in ["البيان", "المسجلون", "الغائبون"]:
            self.grid_stats.add_widget(MDLabel(text=h, bold=True, halign='center', theme_text_color="Secondary"))
            
        self.stat_labels = {}
        for i, key in enumerate(['male', 'female', 'total']):
            self.grid_stats.add_widget(MDLabel(text=['ذكور', 'إناث', 'المجموع'][i], halign='center'))
            self.stat_labels[f'reg_{key}'] = MDLabel(text="0", halign='center')
            self.grid_stats.add_widget(self.stat_labels[f'reg_{key}'])
            self.stat_labels[f'abs_{key}'] = MDLabel(text="0", halign='center', theme_text_color="Error")
            self.grid_stats.add_widget(self.stat_labels[f'abs_{key}'])

        stats_card.add_widget(self.grid_stats)
        self.main_layout.add_widget(stats_card)

        self.male_table = self.create_report_table("قائمة الغائبين (ذكور)")
        self.female_table = self.create_report_table("قائمة الغائبات (إناث)")
        
        self.main_layout.add_widget(MDFillRoundFlatIconButton(text="تحديث البيانات", icon="reload", pos_hint={'center_x': 0.5}, size_hint_y=None, height=dp(50), on_release=self.calculate_stats))
        self.scroll.add_widget(self.main_layout)
        self.add_widget(self.scroll)

    def create_report_table(self, title):
        self.main_layout.add_widget(MDLabel(text=title, halign="right", font_style="Subtitle1", size_hint_y=None, height=dp(30), theme_text_color="Primary"))
        table = MDDataTable(size_hint_y=None, height=dp(300), use_pagination=True, rows_num=5, column_data=[("ID", dp(20)), ("الاسم", dp(40)), ("القسم", dp(20))], row_data=[])
        self.main_layout.add_widget(table)
        return table

    def on_enter(self):
        self.calculate_stats()

    def calculate_stats(self, *args):
        try:
            students = read_csv_data(STUDENTS_FILE)
            attendance = read_csv_data(ATTENDANCE_FILE)
            today = datetime.now().strftime('%Y-%m-%d')
            
            present_ids = [row['id'] for row in attendance if row.get('date') == today]
            
            # تقسيم الطلاب وتحديد الغائبين
            males = [s for s in students if s['gender'].strip() == 'ذكر']
            females = [s for s in students if s['gender'].strip() == 'أنثى']
            
            absent_males = [s for s in males if s['id'] not in present_ids]
            absent_females = [s for s in females if s['id'] not in present_ids]
            
            # تحديث الأرقام
            self.stat_labels['reg_male'].text = str(len(males))
            self.stat_labels['reg_female'].text = str(len(females))
            self.stat_labels['reg_total'].text = str(len(students))
            
            self.stat_labels['abs_male'].text = str(len(absent_males))
            self.stat_labels['abs_female'].text = str(len(absent_females))
            self.stat_labels['abs_total'].text = str(len(absent_males) + len(absent_females))

            # تحديث الجداول
            self.male_table.row_data = [(r['id'], r['name'], r['class_name']) for r in absent_males]
            self.female_table.row_data = [(r['id'], r['name'], r['class_name']) for r in absent_females]
            
            toast("تم تحديث الإحصائيات")
        except Exception as e:
            toast(f"خطأ: {e}")

class SchoolCanteenApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Teal"
        navbar = MDBottomNavigation(selected_color_background="Teal", text_color_active="Light")
        navbar.add_widget(MDBottomNavigationItem(ScannerScreen(name='scan'), name='screen1', text='المسح', icon='qrcode-scan'))
        navbar.add_widget(MDBottomNavigationItem(StudentsScreen(name='students'), name='screen2', text='التلاميذ', icon='account-group'))
        navbar.add_widget(MDBottomNavigationItem(ReportScreen(name='report'), name='screen3', text='الغياب', icon='chart-bar'))
        return navbar
    
    def on_stop(self):
        if hasattr(self, 'screen_scan'): self.screen_scan.stop_camera()

if __name__ == '__main__':
    SchoolCanteenApp().run()