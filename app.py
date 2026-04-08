import streamlit as st
import pandas as pd
from data_processing import load_and_clean_data
import analysis
import plotly.express as px

# =====================================================================
# UI Ayarları & Sayfa Konfigürasyonu (Premium UI)
# =====================================================================
st.set_page_config(
    page_title="İhale Analiz Modülü",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        h1, h2, h3 { color: #2c3e50; }
        .stButton>button {
            background-color: #3498db;
            color: white;
            border-radius: 8px;
            font-weight: 600;
        }
        .stButton>button:hover { background-color: #2980b9; }
        div[data-testid="stSidebar"] { background-color: #1e293b; }
        div[data-testid="stSidebar"] * { color: #f8fafc; }
        section[data-testid="stSidebar"] h1 { color: #38bdf8 !important; }
        .metric-card { 
            background: white; border-radius: 10px; padding: 20px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;
        }
        .metric-title { font-size: 1rem; color: #64748b; font-weight: bold; }
        .metric-value { font-size: 1.8rem; color: #1e293b; font-weight: 900; }
    </style>
""", unsafe_allow_html=True)


import os

# =====================================================================
# Directory Setup & Persistence Prep
# =====================================================================
if not os.path.exists("data"):
    os.makedirs("data")

# =====================================================================
# State Management & Global Defaults (Initialize early)
# =====================================================================
if "processed_data" not in st.session_state:
    st.session_state["processed_data"] = None

if "p_values" not in st.session_state:
    st.session_state["p_values"] = {
        "Z-SKORU EŞİĞİ": 2.5, 
        "IQR ÇARPANI": 1.5, 
        "k DEĞERİ (Düşük Teklif)": 0.7,
        "KRİTİK CV EŞİĞİ (%)": 30.0
    }

if "firm_modifiers" not in st.session_state:
    st.session_state["firm_modifiers"] = pd.DataFrame(columns=["Firma Adı", "Avantaj/Dezavantaj (%)"])

if "chart_page" not in st.session_state:
    st.session_state["chart_page"] = 0

if "perf_page" not in st.session_state:
    st.session_state["perf_page"] = 0

# =====================================================================
# Disk-Based Persistence (Cache)
# =====================================================================
CACHE_PATH = "data/last_upload.xlsx"
CACHE_META = "data/cache_meta.txt"

def save_to_cache(file_bytes, filename):
    with open(CACHE_PATH, "wb") as f:
        f.write(file_bytes)
    with open(CACHE_META, "w", encoding="utf-8") as f:
        f.write(filename)

def clear_cache():
    if os.path.exists(CACHE_PATH): os.remove(CACHE_PATH)
    if os.path.exists(CACHE_META): os.remove(CACHE_META)
    st.session_state["processed_data"] = None
    st.session_state["firm_modifiers"] = pd.DataFrame(columns=["Firma Adı", "Avantaj/Dezavantaj (%)"])

# =====================================================================
# Sidebar: Dosya Yükleme ve Veri Okuma
# =====================================================================
st.sidebar.title("📊 İhale Yükleme")

uploaded_file = st.sidebar.file_uploader("Dosya Seç", type=["xlsx", "xls"])

# Dosya yüklenmemişse ama cach varsa, cache'i yükleyelim
active_file_input = uploaded_file
cached_filename = None
if os.path.exists(CACHE_META):
    with open(CACHE_META, "r", encoding="utf-8") as f:
        cached_filename = f.read()

if uploaded_file is None and os.path.exists(CACHE_PATH):
    st.sidebar.success(f"📦 Önbellekten Yüklendi: {cached_filename}")
    active_file_input = open(CACHE_PATH, "rb")

if active_file_input is not None:
    try:
        if hasattr(active_file_input, 'seek'): active_file_input.seek(0)
        xls = pd.ExcelFile(active_file_input)
        sheet_names = xls.sheet_names
        
        # 1. Öncelikli Sayfa: "Supplier Based Analysis"
        raw_data_sheet = next((s for s in sheet_names if "supplier based analysis" in s.lower()), None)
        
        # 2. Genel Anahtar Kelimeler (Eğer öncelikli yoksa)
        if not raw_data_sheet:
            matches = [s for s in sheet_names if any(kw in s.lower() for kw in ['raw', 'ham', 'teklif', 'veri', 'teklifler'])]
            if len(matches) == 1:
                raw_data_sheet = matches[0]
            elif len(sheet_names) == 1: # 3. Sadece Tek Sayfa Varsa
                raw_data_sheet = sheet_names[0]
            else:
                raw_data_sheet = None # Belirsiz durum

        # Belirsizse Kullanıcıya Seçtir (Fallback)
        if not raw_data_sheet:
            raw_data_sheet = st.sidebar.selectbox("Lütfen Veri Sayfasını Seçin", sheet_names)
        else:
            st.sidebar.write(f"📁 Kaynak Sayfa: `{raw_data_sheet}`")

        params_sheet = next((s for s in sheet_names if any(kw in s.lower() for kw in ['parametre', 'analiz', 'ayarlar'])), None)
        if params_sheet:
            st.sidebar.write(f"⚙️ Parametreler: `{params_sheet}`")

        # OTOMATİK BAŞLATMA MANTIĞI:
        # Veri yüklü (cache veya yeni) ama analiz edilmemişse otomatik başlat
        needs_auto_run = (st.session_state.get("processed_data") is None)
        
        if st.sidebar.button("⚙️ Analizi Başlat") or needs_auto_run:
            with st.spinner("İşleniyor..."):
                if hasattr(active_file_input, 'seek'): active_file_input.seek(0)
                file_bytes = active_file_input.read() if hasattr(active_file_input, 'read') else open(CACHE_PATH, "rb").read()
                from io import BytesIO
                data = load_and_clean_data(BytesIO(file_bytes), raw_data_sheet, params_sheet)
                st.session_state["processed_data"] = data
                
                if uploaded_file is not None:
                    save_to_cache(file_bytes, uploaded_file.name)
                
                st.rerun()
        
    except Exception as e:
        st.sidebar.error(f"Hata: {e}")
    finally:
        if hasattr(active_file_input, 'close'): active_file_input.close()

if st.session_state.get("processed_data") is not None:
    if st.sidebar.button("🗑️ Oturumu ve Önbelleği Temizle"):
         clear_cache()
         st.rerun()
else:
    if uploaded_file is None and not os.path.exists(CACHE_PATH):
        st.sidebar.info("💡 Analize başlamak için dosya yükleyin.")

# =====================================================================
# Ana Alan: Sekmeler (Tabs)
# =====================================================================
st.title("İhale Analiz Modülü")
st.markdown("Modern, dinamik ve akıllı ihale istatistik & analiz platformu.")

# Ana menü yapısı
tab_dashboard, tab_data, tab_params, tab_strategic, tab_stats, tab_outliers, tab_corr, tab_heatmap, tab_perf = st.tabs([
    "📈 Dashboard", 
    "🗂️ Organize Veri", 
    "⚙️ Parametreler",
    "🎯 Stratejik Ayarlar",
    "📊 İstatistikler", 
    "⚠️ Aykırı Değerler", 
    "🔗 Korelasyon", 
    "🔥 Isı Haritası", 
    "🏢 Firma Performansı"
])

# Mevcut veriyi session'dan al
data = st.session_state.get("processed_data")

if data:
    df_org = data['organized']
    meta_cols = data['meta_cols']
    firm_cols = data['firm_cols']
    
    # =====================================================================
    # Price Adjustment Logic (Evaluation Data)
    # =====================================================================
    df_eval = df_org.copy()
    for _, row in st.session_state["firm_modifiers"].iterrows():
        firm = row["Firma Adı"]
        mod = row["Avantaj/Dezavantaj (%)"]
        if mod != 0 and firm in df_eval.columns:
            # Formül: Değerlendirme_Fiyatı = Gerçek_Fiyat * (1 + (Mod / 100))
            df_eval[firm] = df_eval[firm] * (1 + (mod / 100))
else:
    df_org = None
    df_eval = None
    firm_cols = []

# Excel'den yeni veri yüklendiyse parametreleri bir kez güncelle
if data and uploaded_file and st.session_state.get("last_uploaded") != uploaded_file.name:
    df_p = data.get('params', pd.DataFrame())
    if not df_p.empty:
        for _, row in df_p.iterrows():
            if len(row) >= 2:
                p_name = str(row.iloc[0]).upper()
                p_val = row.iloc[1]
                if pd.notna(p_val):
                    try:
                        if "Z-SKORU" in p_name: st.session_state["p_values"]["Z-SKORU EŞİĞİ"] = float(p_val)
                        elif "IQR" in p_name: st.session_state["p_values"]["IQR ÇARPANI"] = float(p_val)
                        elif "k DEĞERİ" in p_name or "K DEĞERİ" in p_name: st.session_state["p_values"]["k DEĞERİ (Düşük Teklif)"] = float(p_val)
                    except: pass
    st.session_state["last_uploaded"] = uploaded_file.name

# Mevcut aktif parametreleri kısaltma olarak al
p_values = st.session_state["p_values"]

with tab_dashboard:
    st.header("Genel İhale Özeti")
    if data:
        excel_totals = data.get('excel_totals', None)
        curr = data.get('currency', '₺')
        kpis = analysis.create_dashboard_kpis(df_eval, firm_cols, excel_totals)
        
        # Premium KPI Layout
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"<div class='metric-card'><div class='metric-title'>Toplam Kalem</div><div class='metric-value'>{kpis['toplam_kalem']}</div></div>", unsafe_allow_html=True)
        col2.markdown(f"<div class='metric-card'><div class='metric-title'>Firma Sayısı</div><div class='metric-value'>{kpis['firma_sayisi']}</div></div>", unsafe_allow_html=True)
        col3.markdown(f"<div class='metric-card'><div class='metric-title'>Ort. İhale Bedeli (Düzeltilmiş)</div><div class='metric-value'>{curr} {kpis['ortalama_ihale_bedeli']:,.2f}</div></div>", unsafe_allow_html=True)
        col4.markdown(f"<div class='metric-card'><div class='metric-title'>En Düşük Toplam (Düzeltilmiş)</div><div class='metric-value'>{curr} {kpis['en_dusuk_tutar']:,.2f}</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        st.subheader("🏆 İhale En Düşük Teklif Sahibi (Düzeltilmiş): " + kpis['en_dusuk_teklif_firma'])
        
        # İhale Kıyaslama Grafiği (Tam Genişlik)
        chart_fig = analysis.generate_total_bids_chart(df_eval, firm_cols, excel_totals, curr)
        if chart_fig:
            st.write("### İhaleye Teklif Veren Firmaların Kıyaslaması (Düzeltilmiş Fiyatlar)")
            st.plotly_chart(chart_fig, width="stretch")
        else:
            st.warning("📊 Karşılaştırma grafiği için yeterli veri bulunamadı.")
            
        st.write("---")

        # Firma Başarı Tablosu (Tam Genişlik)
        st.markdown("#### 🥇 Firma Başarısı (Kalem Bazında En Düşük Düzeltilmiş Teklifler)")
        lowest_bid_stats = analysis.calculate_lowest_bid_stats(df_eval, firm_cols)
        # Yüksekliği firma sayısına göre dinamik hesapla
        dynamic_height = min((len(lowest_bid_stats) + 1) * 35 + 5, 500)
        st.dataframe(lowest_bid_stats, width="stretch", hide_index=True, height=dynamic_height)
        
    else:
        st.warning("Görünümleri açmak için lütfen sol menüden ihale dosyası yükleyin ve 'Verileri İşle' butonuna basın.")

with tab_data:
    if data:
        # Firma kolonlarını otomatik formatla (Birim fiyat gösterimi için)
        column_config = {}
        for col in firm_cols:
            column_config[col] = st.column_config.NumberColumn(
                col,
                format="%.2f",  # 2 ondalık basamak
                help=f"{col} firmasının birim fiyatı"
            )
            
        st.dataframe(df_org, width="stretch", hide_index=True, column_config=column_config, height=450)
        
        csv = df_org.to_csv(index=False).encode('utf-8-sig') # Excel uyumlu türkçe karakter için sig
        st.download_button("Excel Formatında İndir (CSV)", csv, "organized_data.csv", "text/csv")

with tab_params:
    st.markdown("<h2 style='text-align: center; color: #2c3e50;'>ANALİZ PARAMETRELERİ</h2>", unsafe_allow_html=True)
    st.markdown("<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; text-align: center; color: #856404; font-weight: bold;'>⚙️ PARAMETRELERİ AŞAĞIDAN GÜNCELLEYEBİLİRSİNİZ</div>", unsafe_allow_html=True)
    
    # Teknik Rehber İndirme Butonu
    with open("Ihale_Parametre_Rehberi.html", "rb") as file:
        st.download_button(
            label="📄 Teknik Parametre Rehberini İndir",
            data=file,
            file_name="Ihale_Parametre_Rehberi.html",
            mime="text/html"
        )
    
    st.write("")
    col_set1, col_set2, col_set3 = st.columns(3)
    
    with col_set1:
        st.subheader("1. Z-Skoru Eşiği")
        st.session_state["p_values"]["Z-SKORU EŞİĞİ"] = st.slider(
            "Hassasiyet Eşiği", 1.0, 5.0, float(st.session_state["p_values"]["Z-SKORU EŞİĞİ"]), 0.1, 
            help="Önerilen: 2.0 - 3.0. Not: 3 firmalı ihalelerde matematiksel limit 1.41'dir. Sistem bunu otomatik algılar."
        )
        st.info("🎯 **Önerilen: 2.50** (3 firmalı ihalelerde sistem eşiği otomatik olarak 1.35 civarına çeker)")

    with col_set2:
        st.subheader("2. IQR Çarpanı")
        st.session_state["p_values"]["IQR ÇARPANI"] = st.slider(
            "Çeyrek Mesafe Çarpanı", 1.0, 4.0, float(st.session_state["p_values"]["IQR ÇARPANI"]), 0.1, 
            help="Standart (Tukey): 1.5, Sert Sınır: 3.0"
        )
        st.info("🎯 **Önerilen: 1.50** (Standart İstatistiksel Eşik)")

    with col_set3:
        st.subheader("3. k-Değeri")
        st.session_state["p_values"]["k DEĞERİ (Düşük Teklif)"] = st.slider(
            "Düşük Teklif Faktörü", 0.1, 2.0, float(st.session_state["p_values"]["k DEĞERİ (Düşük Teklif)"]), 0.05, 
            help="Avrupa Birliği ve EBRD kriterlerine dayalı önerilen: 0.5 - 1.0"
        )
        st.info("🎯 **Önerilen: 0.70**")

    st.write("---")
    st.subheader("📊 Varyasyon (CV) Eşiği")
    st.session_state["p_values"]["KRİTİK CV EŞİĞİ (%)"] = st.slider(
        "Kritik Durum Eşiği (%)", 10.0, 60.0, float(st.session_state["p_values"]["KRİTİK CV EŞİĞİ (%)"]), 1.0, 
        help="Hangi varyasyon yüzdesinden sonrasının 'Kritik' (Kırmızı) kabul edileceğini belirler."
    )
    st.info(f"💡 Şu anki Kritik Sınır: **%{int(st.session_state['p_values']['KRİTİK CV EŞİĞİ (%)'])}**. Bu değerin altı 'Dikkat', yarısının altı ise 'Güvenli' sayılır.")

    st.write("---")
    st.markdown("### 🧮 ÖRNEK HESAPLAMALAR")
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    
    with calc_col1:
        st.markdown("**Z-Skoru:**")
        st.latex(r"Z = \frac{Teklif - \mu}{\sigma}")
        st.caption("Örnek: Ortalama=100, SS=15, Teklif=130 ise Z=2.0")
    
    with calc_col2:
        st.markdown("**IQR Sınırı:**")
        st.latex(r"Alt = Q1 - (K \times IQR)")
        st.latex(r"Üst = Q3 + (K \times IQR)")
        st.caption("Örnek: Q1=80, Q3=120, IQR=40 için Alt=20, Üst=180")
        
    with calc_col3:
        st.markdown("**Düşük Teklif:**")
        st.latex(r"Limit = \mu - (k \times \sigma)")
        st.caption("Örnek: Ortalama=100, SS=15, k=0.5 için Sınır=92.5")

with tab_strategic:
    st.markdown("<h2 style='text-align: center; color: #2c3e50;'>🎯 FİRMA AVANTAJ / DEZAVANTAJ TANIMLARI</h2>", unsafe_allow_html=True)
    st.markdown("""
        <div style='background-color: #e0f2fe; padding: 15px; border-radius: 10px; color: #0369a1; margin-bottom: 20px;'>
            <b>💡 Nasıl Çalışır?</b><br>
            • <b>Avantaj (Yerli Malı vb.):</b> Negatif değer girin (Örn: -15). Bu firmanın fiyatı kıyaslama yapılırken %15 düşük sayılır.<br>
            • <b>Dezavantaj:</b> Pozitif değer girin (Örn: 10). Bu firmanın fiyatı kıyaslama yapılırken %10 yüksek sayılır.<br>
            • <i>Not: Bu ayarlar sadece analizleri etkiler, dosyadaki orijinal birim fiyatları değiştirmez.</i>
        </div>
    """, unsafe_allow_html=True)

    if data:
        # Firmaları kolonlardan al
        current_firms = firm_cols
        
        # Eğer firma listesi değiştiyse veya henüz oluşmadıysa güncelle
        existing_firms = st.session_state["firm_modifiers"]["Firma Adı"].tolist()
        if set(current_firms) != set(existing_firms):
            st.session_state["firm_modifiers"] = pd.DataFrame({
                "Firma Adı": current_firms,
                "Avantaj/Dezavantaj (%)": 0.0
            })

        # Veri düzenleyici (Data Editor)
        st.session_state["firm_modifiers"] = st.data_editor(
            st.session_state["firm_modifiers"],
            column_config={
                "Firma Adı": st.column_config.Column(disabled=True),
                "Avantaj/Dezavantaj (%)": st.column_config.NumberColumn(
                    format="%d %%", min_value=-50.0, max_value=100.0, step=0.5
                )
            },
            hide_index=True, use_container_width=True
        )
        
        # Özet Bilgi
        active_mods = st.session_state["firm_modifiers"][st.session_state["firm_modifiers"]["Avantaj/Dezavantaj (%)"] != 0]
        if not active_mods.empty:
            st.success(f"✅ {len(active_mods)} firma için fiyat düzeltmesi aktif.")
        else:
            st.info("ℹ️ Şu an tüm firmalar için gerçek fiyatlar üzerinden analiz yapılıyor.")
    else:
        st.warning("Firmaları listelemek için lütfen önce veri yükleyin.")

# =====================================================================
# Price Adjustment Logic (Old position - cleared)
# =====================================================================

with tab_stats:
    st.header("📊 İş Kalemleri Bazında İstatistikler")
    if data:
        cv_limit = st.session_state["p_values"]["KRİTİK CV EŞİĞİ (%)"]
        stats_df = analysis.calculate_item_statistics(df_eval, firm_cols, cv_limit)
        
        # Dinamik Renklendirme Mantığı
        def style_stats_table(row):
            status = str(row['Pazar Durumu'])
            if 'Kritik' in status: return ['background-color: #ff4d4d; color: white'] * len(row)
            if 'Dikkat' in status: return ['background-color: #ffa500; color: black'] * len(row)
            if 'Güvenli' in status: return ['background-color: #2ecc71; color: white'] * len(row)
            if 'Rekabet Yok' in status: return ['background-color: #94a3b8; color: white'] * len(row)
            return [''] * len(row)

        # Sayısal formatlama (Gereksiz sıfırları temizle)
        numeric_cols = ['Min', 'Max', 'Ortalama', 'Standart Sapma', 'Medyan', 'IQR', 'CV(%)']
        
        # 'Item No' kolonunu tamsayı olarak, diğerlerini ise gereksiz sıfırsız formatlayalım
        styled_stats = stats_df.style.apply(style_stats_table, axis=1).format({
            "Item No": "{:d}",
            **{col: lambda x: f"{x:,.2f}".rstrip('0').rstrip('.') for col in numeric_cols}
        })
        
        st.dataframe(styled_stats, width="stretch", hide_index=True, height=450)
        
        # İstatistik Rehberi İndirme
        with open("Ihale_Parametre_Rehberi.html", "rb") as file:
            st.download_button(
                label="📄 İstatistiksel Parametre Reberini İndir",
                data=file,
                file_name="Ihale_Parametre_Rehberi.html",
                mime="text/html"
            )
        
        st.write("---")
        st.subheader("⚙️ Teklif Fiyat Uyumluluk Analizi")
        st.write("Bu bölümde ihale kalemlerindeki tekliflerin birbiriyle olan uyumu (Donut) ve yüksek fiyat farkı gösteren kritik kalemler (Histogram) analiz edilmiştir.")
        
        col_donut, col_scatter = st.columns([1, 2])
        with col_donut:
            donut_fig = analysis.generate_cv_donut_chart(stats_df)
            if donut_fig:
                st.plotly_chart(donut_fig, width="stretch")
                
        with col_scatter: # Histogram olarak değiştirdik
            hist_fig = analysis.generate_cv_histogram(stats_df)
            if hist_fig:
                st.plotly_chart(hist_fig, width="stretch")
            else:
                st.info("📉 Belirgin varyasyon içeren kalem bulunmadığından dağılım grafiği oluşturulmadı.")
        
        st.write("---")
        st.subheader("⚠️ Kritik Kalemler Fiyat Uyumluluk Listesi")
        st.write("Seçilen kritik eşiğin üzerinde sapma gösteren en riskli kalemleri inceler (Yüksekten Düşüğe).")
        
        # Kritik kalemleri bul (Label içinde 'Kritik' geçenler)
        critical_items = stats_df[stats_df['Pazar Durumu'].str.contains('Kritik', na=False)].sort_values('CV(%)', ascending=False)
        
        if not critical_items.empty:
            page_size = 10
            max_pages = (len(critical_items) - 1) // page_size
            
            # Sayfa sınır kontrolü
            if st.session_state["chart_page"] > max_pages:
                st.session_state["chart_page"] = max_pages
                
            start_idx = st.session_state["chart_page"] * page_size
            end_idx = start_idx + page_size
            current_subset = critical_items.iloc[start_idx:end_idx]
            
            # Grafik
            subset_fig = analysis.generate_cv_consistency_chart(current_subset)
            if subset_fig:
                st.plotly_chart(subset_fig, width="stretch")
                
            # Navigasyon Butonları
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ Önceki 10 Kalem", disabled=st.session_state["chart_page"] == 0):
                    st.session_state["chart_page"] -= 1
                    st.rerun()
            with col_page:
                st.markdown(f"<p style='text-align:center; color: gray;'>Sayfa {st.session_state['chart_page'] + 1} / {max_pages + 1} ({len(critical_items)} Kritik Kalem)</p>", unsafe_allow_html=True)
            with col_next:
                if st.button("Sonraki 10 Kalem ➡️", disabled=st.session_state["chart_page"] >= max_pages):
                    st.session_state["chart_page"] += 1
                    st.rerun()
        else:
            st.success("✅ Pazar çok tutarlı! %30 üzerinde varyasyon içeren kritik kalem bulunamadı.")
with tab_outliers:
    st.header("🔍 Gelişmiş Aykırı Değer ve Düşük Teklif Analizi")
    if data:
        # Metodoloji Rehberi
        with st.expander("ℹ️ Aykırı Değer Yöntemleri Neyi Araştırır?", expanded=False):
            st.markdown("""
            Aykırı değer analizi, pazardan tamamen kopmuş veya hatalı girilmiş olabilecek 'aykırı' teklifleri tespit eder.
            
            *   **📊 Z-Skoru:** Teklifin ortalamadan ne kadar uzaklaştığını ölçer. (Hatalı/Uçuk fiyat tespiti için idealdir).
            *   **📉 IQR (Çeyrekler):** Pazarın merkezindeki %50'lik grubun dışında kalanları bulur. (Birden fazla uç fiyat olsa bile yanılmaz).
            *   **⚠️ Aşırı Düşük (k-Faktörü):** Sadece 'tehlikeli derecede düşük' tekliflere odaklanır. (Sürdürülemez teklif tespiti).
            
            **💡 Akıllı Eşik:** Firma sayısı azaldığında (3-5 firma), sistem istatistiksel limitleri algılayarak hassasiyeti otomatik olarak optimize eder.
            """)
            
        params = st.session_state["p_values"]
        z_thresh = params.get("Z-SKORU EŞİĞİ", 2.5)
        iqr_fact = params.get("IQR ÇARPANI", 1.5)
        k_val = params.get("k DEĞERİ (Düşük Teklif)", 0.7)
        
        o_tab1, o_tab2, o_tab3 = st.tabs(["📊 Z-Skoru (Genel)", "📉 IQR (Çeyrekler)", "⚠️ Aşırı Düşük (k-Faktörü)"])
        
        with o_tab1:
            outliers_z = analysis.detect_outliers_zscore(df_eval, firm_cols, z_thresh)
            if not outliers_z.empty:
                st.dataframe(outliers_z, width="stretch", hide_index=True)
                st.caption("✨ 'Not' sütununda 'Akıllı Eşik' yazan kalemlerde, düşük katılımcı sayısı nedeniyle hassasiyet otomatik artırılmıştır.")
            else:
                st.success("✅ **Z-Skoru Analizi:** Pazar çok tutarlı. Belirlenen eşiğin dışında uç teklif bulunamadı.")
            
        with o_tab2:
            outliers_iqr = analysis.detect_outliers_iqr(df_eval, firm_cols, iqr_fact)
            if not outliers_iqr.empty:
                st.dataframe(outliers_iqr, width="stretch", hide_index=True)
            else:
                st.success("✅ **IQR Analizi:** Pazarın merkez dağılımı dışında kalan (çeyrek dışı) teklif tespit edilmedi.")
            
        with o_tab3:
            outliers_k = analysis.detect_low_bids_k_factor(df_eval, firm_cols, k_val)
            if not outliers_k.empty:
                st.dataframe(outliers_k, width="stretch", hide_index=True)
            else:
                st.success("✅ **Aşırı Düşük Analizi:** Pazar ortalamasının tehlikeli derecede altında bir teklif bulunamadı.")

with tab_corr:
    st.header("🔗 Firma Teklif Korelasyonları")
    if data:
        with st.expander("ℹ️ Korelasyon Analizi Nedir ve Nasıl Okunur?", expanded=True):
            st.markdown("""
            **Korelasyon Analizi**, iki firmanın ihale kalemlerine verdikleri tekliflerin birbirlerine ne kadar 'benzer' bir seyir izlediğini ölçen istatistiksel bir yöntemdir.
            
            ### 📉 Bu Tabloyu Nasıl Okumalısınız?
            - **Değerler -1 ile +1 arasındadır.**
            - **+1.00'a Yakın Değerler:** İki firma neredeyse aynı fiyatlama mantığına sahiptir. Bir firma fiyatını bir kalemde artırdıysa, diğeri de benzer oranda artırmıştır. Bu durum, ortak maliyet yapılarına veya benzer stratejilere işaret edebilir.
            - **0.00 Civarı Değerler:** İki firmanın teklifleri arasında hiçbir ilişki yoktur. Birbirlerinden tamamen bağımsız fiyatlar vermişlerdir.
            - **-1.00'a Yakın Değerler (Nadir):** Firmalar tam zıt hareket etmektedir (Biri pahalıyken diğeri hep ucuzdur).
            
            ### 🧮 Hesaplama Mantığı (Pearson Katsayısı)
            Bu analizde **Pearson Korelasyon Katsayısı** kullanılır. Formül, firmaların her bir kalemdeki tekliflerinin, kendi ortalamalarından ne kadar saptığını kıyaslar:
            $$ r = \\frac{\\sum (X_i - \\bar{X})(Y_i - \\bar{Y})}{\\sqrt{\\sum (X_i - \\bar{X})^2 \\sum (Y_i - \\bar{Y})^2}} $$
            
            *Basitçe ifade edersek;* Excel'deki her bir satır (kalem) bir veri noktasıdır ve grafiksel olarak iki firmanın teklifleri üst üste biniyorsa korelasyon yüksek çıkar.
            """)
        
        corr_matrix = analysis.create_correlation_matrix(df_eval, firm_cols)
        st.plotly_chart(analysis.generate_heatmap_figure(corr_matrix), width="stretch")
        st.info("💡 **İpucu:** Kırmızı bölgeler (1.00'a yakın) kuvvetli benzerliği, mavi bölgeler ise düşük benzerliği temsil eder. (Düzeltilmiş Fiyatlar üzerinden hesaplanmıştır)")

with tab_heatmap:
    st.header("🔥 Kalem Bazlı Teklif Isı Haritası (Trafik Işığı Analizi)")
    if data:
        st.write("Aşağıdaki tabloda her bir iş kalemi için firmaların teklifleri **satır bazında** (Excel stili) renklendirilmiştir. "
                 "**Yeşil** en ucuz, **Sarı** ortalama, **Kırmızı** ise en pahalı teklifi temsil eder.")
        
        display_df = df_eval.copy()
        for col in firm_cols:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce')
        
        # Arrow uyuşmazlığı ve format hatalarını önlemek için veri tiplerini sabitleyelim
        # Metin kolonlarını string yapalım
        for col in display_df.columns:
            if col not in firm_cols:
                display_df[col] = display_df[col].astype(str).replace('nan', '')

        # Excel stili 3 Renkli (Yeşil-Sarı-Kırmızı) Isı Haritası
        # axis=1: Her satırı kendi içinde (firmalar arası) renklendirir
        styled_df = display_df.style.background_gradient(
            axis=1, 
            subset=firm_cols, 
            cmap='RdYlGn_r'
        ).format(
            {col: lambda x: f"{x:,.2f}" if pd.notna(x) and isinstance(x, (int, float)) else "-" for col in firm_cols}
        )
        
        st.dataframe(styled_df, width="stretch", hide_index=True, height=600)
        st.info("💡 Her satır bir ihale kalemi için pazarın 'Trafik Işığı' analizidir. Yeşil=En Ucuz, Sarı=Ortalama, Kırmızı=Pahalı. (Düzeltilmiş Fiyatlar üzerinden)")

with tab_perf:
    st.header("🏢 Firma Rekabet Profili")
    if data:
        st.write("Firmaların ihale kalemlerindeki fiyat seyirlerini ve ortalamaya göre konumlarını analiz edin.")
        
        # Grafik Ayarları (Sayfa Boyutu, Sıralama vb.)
        col_cfg1, col_cfg2, col_cfg3 = st.columns([2, 2, 4])
        with col_cfg1:
             page_size = st.slider("Kalem Sayısı / Sayfa", 5, 20, 10, help="Ekranda aynı anda kaç kalem gösterileceğini belirler.")
        
        with col_cfg2:
             view_mode = st.radio("📈 Görünüm Modu", 
                                  options=["İhale Sırası (1, 2...)", "Fiyat Büyüklüğü (Artan)"],
                                  help="Sıralama yaparak benzer fiyatlı kalemleri bir araya toplar.")
             
        # Firma Seçimi
        with col_cfg3:
            st.write("") # Boşluk
            sub_col1, sub_col2 = st.columns([1, 4])
            with sub_col1:
                all_firms_cb = st.checkbox("Tümünü Seç", value=False)
            with sub_col2:
                default_val = firm_cols if all_firms_cb else (firm_cols[:5] if len(firm_cols) > 5 else firm_cols)
                selected_firms = st.multiselect("Kıyaslanacak Firmaları Seçin", firm_cols, default=default_val)
        
        # Seçilen moda göre veriyi hazırla
        plot_df = df_eval.copy()
        if view_mode == "Fiyat Büyüklüğü (Artan)":
            # Satır bazlı ortalama fiyatı bulup ona göre sırala (Gruplama etkisi yaratır)
            plot_df['avg_row_price'] = plot_df[firm_cols].mean(axis=1)
            plot_df = plot_df.sort_values('avg_row_price').reset_index(drop=True)
            plot_df = plot_df.drop(columns=['avg_row_price'])
        
        if selected_firms:
            # Sayfalama Mantığı
            max_perf_pages = (len(plot_df) - 1) // page_size
            
            if st.session_state["perf_page"] > max_perf_pages:
                st.session_state["perf_page"] = max_perf_pages
                
            start_idx = st.session_state["perf_page"] * page_size
            end_idx = start_idx + page_size
            perf_subset = plot_df.iloc[start_idx:end_idx].copy()
            
            # Verilerin sayısal olduğundan emin ol (Grafik hatasını önlemek için)
            for f in selected_firms:
                perf_subset[f] = pd.to_numeric(perf_subset[f], errors='coerce')
            
            # Ortalama hesapla (Tüm mevcut firmalar üzerinden, skipna=True varsayılandır)
            perf_subset['Ortalama Teklif'] = perf_subset[firm_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
            
            # X ekseni için kolon adı
            x_col = meta_cols[0] if meta_cols else 'Item No'
            
            # Grafik Çizimi
            y_cols = selected_firms + ['Ortalama Teklif']
            fig = px.line(
                perf_subset, 
                x=x_col, 
                y=y_cols, 
                markers=True,
                title=f"Birim Fiyat Karşılaştırması (Sayfa {st.session_state['perf_page'] + 1} / {max_perf_pages + 1})",
                labels={x_col: "İhale Kalemi", "value": "Birim Fiyat", "variable": "Firma/Ortalama"},
                line_shape="linear"
            )
            
            # Grafik düzenlemeleri (Hover temizliği ve X ekseni açısı)
            fig.update_layout(
                height=600,
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                xaxis=dict(type='category', tickangle=-45, categoryorder='trace'),
                hovermode="x unified",
                yaxis=dict(tickformat=',.2f', title=f"Fiyat ({data.get('currency', '₺')})")
            )
            
            # Ortalama çizgisini farklılaştır (Kalın ve siyah kesikli yapalım)
            fig.update_traces(
                selector=dict(name="Ortalama Teklif"),
                line=dict(color="black", width=5, dash="dot"),
                marker=dict(size=10, symbol="x")
            )
            
            st.plotly_chart(fig, width="stretch")
            
            # Navigasyon Butonları
            col_p, col_i, col_n = st.columns([1, 2, 1])
            with col_p:
                if st.button("⬅️ Önceki Sayfa", key="perf_prev", disabled=st.session_state["perf_page"] == 0):
                    st.session_state["perf_page"] -= 1
                    st.rerun()
            with col_i:
                st.markdown(f"<p style='text-align:center; font-weight: bold;'>Kalem {start_idx + 1} - {min(end_idx, len(df_org))} / Toplam {len(df_org)} Kalem</p>", unsafe_allow_html=True)
            with col_n:
                if st.button("Sonraki Sayfa ➡️", key="perf_next", disabled=st.session_state["perf_page"] >= max_perf_pages):
                    st.session_state["perf_page"] += 1
                    st.rerun()
        else:
            st.warning("⚠️ Lütfen analiz için en az bir firma seçin.")
    else:
        st.warning("Verileri görmek için lütfen dosya yükleyin.")
