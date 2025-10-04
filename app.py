import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import json

# Uygulama ve veritabanı kurulumu
app = Flask(__name__)
app.config['SECRET_KEY'] = 'akil-zeka-kulubu-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///club_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmalısınız.'

# Dosya yükleme için izin verilen uzantılar
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Modeller
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # admin, veli
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # İlişkiler
    veli_profile = db.relationship('Veli', backref='user', uselist=False, lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Veli(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ad = db.Column(db.String(50), nullable=False)
    soyad = db.Column(db.String(50), nullable=False)
    telefon = db.Column(db.String(15))
    adres = db.Column(db.Text)
    
    # İlişkiler
    ogrenciler = db.relationship('Ogrenci', backref='veli', lazy=True)

class Ogrenci(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veli_id = db.Column(db.Integer, db.ForeignKey('veli.id'), nullable=False)
    ad = db.Column(db.String(50), nullable=False)
    soyad = db.Column(db.String(50), nullable=False)
    sinif = db.Column(db.String(10))
    okul = db.Column(db.String(100))
    dogum_tarihi = db.Column(db.Date)
    kayit_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    durum = db.Column(db.String(20), default='aktif')  # aktif, pasif
    
    # İlişkiler
    katilimlar = db.relationship('EtkinlikKatilim', backref='ogrenci', lazy=True)
    odemeler = db.relationship('Odeme', backref='ogrenci', lazy=True)

class Etkinlik(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(200), nullable=False)
    aciklama = db.Column(db.Text)
    baslangic_tarihi = db.Column(db.DateTime, nullable=False)
    bitis_tarihi = db.Column(db.DateTime, nullable=False)
    konum = db.Column(db.String(200))
    kapasite = db.Column(db.Integer)
    ucret = db.Column(db.Float, default=0.0)
    durum = db.Column(db.String(20), default='planlanıyor')  # planlanıyor, aktif, tamamlandı, iptal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # İlişkiler
    katilimlar = db.relationship('EtkinlikKatilim', backref='etkinlik', lazy=True)

class EtkinlikKatilim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    etkinlik_id = db.Column(db.Integer, db.ForeignKey('etkinlik.id'), nullable=False)
    ogrenci_id = db.Column(db.Integer, db.ForeignKey('ogrenci.id'), nullable=False)
    kayit_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    durum = db.Column(db.String(20), default='kayıtlı')  # kayıtlı, katıldı, katılmadı

class Odeme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ogrenci_id = db.Column(db.Integer, db.ForeignKey('ogrenci.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)
    odeme_tarihi = db.Column(db.Date)
    aciklama = db.Column(db.String(200))
    durum = db.Column(db.String(20), default='bekliyor')  # bekliyor, odendi, iptal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Yardımcı fonksiyonlar
def get_user_role():
    if current_user.is_authenticated:
        return current_user.role
    return None

# Ana Sayfalar
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/hakkimizda')
def hakkimizda():
    return render_template('hakkimizda.html')

@app.route('/iletisim')
def iletisim():
    return render_template('iletisim.html')

# Kimlik Doğrulama
@app.route('/giris', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('veli_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            flash('Başarıyla giriş yaptınız!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('veli_dashboard'))
        else:
            flash('E-posta veya şifre hatalı!', 'error')
    
    return render_template('auth/login.html')

@app.route('/kayit', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        telefon = request.form.get('telefon')
        adres = request.form.get('adres')
        
        # E-posta kontrolü
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanılıyor!', 'error')
            return render_template('auth/register.html')
        
        # Yeni kullanıcı oluştur
        new_user = User(email=email, role='veli')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # Veli profili oluştur
        new_veli = Veli(user_id=new_user.id, ad=ad, soyad=soyad, telefon=telefon, adres=adres)
        db.session.add(new_veli)
        db.session.commit()
        
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth_login'))
    
    return render_template('auth/register.html')
    
@app.route('/cikis')
@login_required
def auth_logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

# Admin Panel Routes
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    # İstatistikler
    ogrenci_sayisi = Ogrenci.query.count()
    veli_sayisi = Veli.query.count()
    aktif_etkinlikler = Etkinlik.query.filter(Etkinlik.durum == 'aktif').count()
    bekleyen_odemeler = Odeme.query.filter(Odeme.durum == 'bekliyor').count()
    
    return render_template('admin/dashboard.html',
                         ogrenci_sayisi=ogrenci_sayisi,
                         veli_sayisi=veli_sayisi,
                         aktif_etkinlikler=aktif_etkinlikler,
                         bekleyen_odemeler=bekleyen_odemeler)

@app.route('/admin/ogrenciler')
@login_required
def admin_ogrenciler():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    ogrenciler = Ogrenci.query.all()
    return render_template('admin/ogrenciler.html', ogrenciler=ogrenciler)

@app.route('/admin/veliler')
@login_required
def admin_veliler():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    veliler = Veli.query.all()
    return render_template('admin/veliler.html', veliler=veliler)

@app.route('/admin/etkinlikler')
@login_required
def admin_etkinlikler():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    etkinlikler = Etkinlik.query.all()
    return render_template('admin/etkinlikler.html', etkinlikler=etkinlikler)

@app.route('/admin/raporlar')
@login_required
def admin_raporlar():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin/raporlar.html')

# Veli Portal Routes
@app.route('/veli')
@login_required
def veli_dashboard():
    if current_user.role != 'veli':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    veli = Veli.query.filter_by(user_id=current_user.id).first()
    cocuklar = Ogrenci.query.filter_by(veli_id=veli.id).all()
    
    return render_template('veli/dashboard.html', veli=veli, cocuklar=cocuklar)

@app.route('/veli/cocuklarim')
@login_required
def veli_cocuklarim():
    if current_user.role != 'veli':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    veli = Veli.query.filter_by(user_id=current_user.id).first()
    cocuklar = Ogrenci.query.filter_by(veli_id=veli.id).all()
    
    return render_template('veli/cocuklarim.html', cocuklar=cocuklar)

@app.route('/veli/etkinlikler')
@login_required
def veli_etkinlikler():
    if current_user.role != 'veli':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    etkinlikler = Etkinlik.query.filter(Etkinlik.durum.in_(['planlanıyor', 'aktif'])).all()
    return render_template('veli/etkinlikler.html', etkinlikler=etkinlikler)

@app.route('/veli/odemeler')
@login_required
def veli_odemeler():
    if current_user.role != 'veli':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
    
    veli = Veli.query.filter_by(user_id=current_user.id).first()
    cocuklar = Ogrenci.query.filter_by(veli_id=veli.id).all()
    
    # Tüm çocukların ödemelerini al
    odemeler = []
    for cocuk in cocuklar:
        cocuk_odemeler = Odeme.query.filter_by(ogrenci_id=cocuk.id).all()
        odemeler.extend(cocuk_odemeler)
    
    return render_template('veli/odemeler.html', odemeler=odemeler)

# API Routes
@app.route('/api/ogrenci_ekle', methods=['POST'])
@login_required
def api_ogrenci_ekle():
    if current_user.role != 'veli':
        return jsonify({'success': False, 'message': 'Yetkisiz işlem!'})
    
    veli = Veli.query.filter_by(user_id=current_user.id).first()
    
    ad = request.form.get('ad')
    soyad = request.form.get('soyad')
    sinif = request.form.get('sinif')
    okul = request.form.get('okul')
    dogum_tarihi = request.form.get('dogum_tarihi')
    
    yeni_ogrenci = Ogrenci(
        veli_id=veli.id,
        ad=ad,
        soyad=soyad,
        sinif=sinif,
        okul=okul,
        dogum_tarihi=datetime.strptime(dogum_tarihi, '%Y-%m-%d') if dogum_tarihi else None
    )
    
    db.session.add(yeni_ogrenci)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Öğrenci başarıyla eklendi!'})
    
@app.route('/test')
def test_pages():
    return render_template('test.html')

# Hata sayfaları
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Varsayılan admin kullanıcısı oluştur
        if not User.query.filter_by(email='admin@akilzeka.com').first():
            admin_user = User(email='admin@akilzeka.com', role='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print('Varsayılan admin kullanıcısı oluşturuldu: admin@akilzeka.com / admin123')
    
    # BU SATIRI DEĞİŞTİRİN:
    app.run(debug=True, host='0.0.0.0', port=5000)