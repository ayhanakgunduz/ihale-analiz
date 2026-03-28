import pandas as pd
import numpy as np
from scipy import stats
import plotly.express as px
import plotly.graph_objects as go

def calculate_item_statistics(df, firm_cols, cv_threshold=30.0):
    """
    Kullanıcının istediği spesifik istatistik kolonlarını hesaplar ve sıralar.
    cv_threshold: Kritik seviye eşiği (Varsayılan %30)
    """
    firm_data = df[firm_cols]
    
    item_no_col = df.columns[0] if len(df.columns) > 0 else 'Item No'
    desc_col = df.columns[1] if len(df.columns) > 1 else 'Aciklama'
    
    stats_df = pd.DataFrame()
    stats_df['Item No'] = df[item_no_col].fillna(pd.Series(range(1, len(df) + 1), index=df.index)).astype(int)
    stats_df['Aciklama'] = df[desc_col].fillna("Açıklama Yok")
    
    stats_df['Ortalama'] = firm_data.mean(axis=1).round(2)
    stats_df['Medyan'] = firm_data.median(axis=1).round(2)
    stats_df['Standart Sapma'] = firm_data.std(axis=1).round(2)
    
    stats_df['CV(%)'] = np.where(stats_df['Ortalama'] > 0, 
                                 ((stats_df['Standart Sapma'].fillna(0) / stats_df['Ortalama']) * 100).round(1), 
                                 0)
    
    stats_df['Min'] = firm_data.min(axis=1).round(2)
    stats_df['Max'] = firm_data.max(axis=1).round(2)
    stats_df['Aralik'] = (stats_df['Max'] - stats_df['Min']).round(2)
    
    stats_df['Q1'] = firm_data.quantile(0.25, axis=1).round(2)
    stats_df['Q2'] = stats_df['Medyan']
    stats_df['Q3'] = firm_data.quantile(0.75, axis=1).round(2)
    stats_df['IQR'] = (stats_df['Q3'] - stats_df['Q1']).round(2)
    
    stats_df['Teklif Sayısı'] = firm_data.notna().sum(axis=1)
    
    # Dinamik Eşik Etiketleri
    attention_limit = cv_threshold / 2
    
    def determine_status(row):
        count = row['Teklif Sayısı']
        cv = row['CV(%)']
        if count == 0: return 'Teklif Yok'
        if count == 1: return 'Rekabet Yok (Tek Teklif)'
        if cv <= attention_limit: return f'Güvenli (%0-{int(attention_limit)})'
        if cv <= cv_threshold: return f'Dikkat (%{int(attention_limit)}-{int(cv_threshold)})'
        return f'Kritik (>%{int(cv_threshold)})'
        
    stats_df['Pazar Durumu'] = stats_df.apply(determine_status, axis=1)
    
    cols_order = [
        'Item No', 'Aciklama', 'Pazar Durumu', 'Teklif Sayısı', 'CV(%)', 
        'Min', 'Max', 'Ortalama', 'Standart Sapma', 'Medyan', 'IQR'
    ]
    return stats_df[cols_order]

def detect_outliers_zscore(df, firm_cols, threshold=2.0):
    """
    İş kalemleri bazında teklifleri Z-Skoru ile değerlendirir ve aykırı değerleri bulur.
    Akıllı Eşik: Firma sayısına göre matematiksel limitleri göz önünde bulundurur.
    """
    outliers_list = []
    for _, row in df.iterrows():
        item_name = row.iloc[0] if len(row) > 0 else "Bilinmeyen Kalem"
        vals = pd.to_numeric(row[firm_cols], errors='coerce')
        valid_vals = vals.dropna()
        n = len(valid_vals)
        if n >= 3:
            # Matematiksel limit: sqrt(n-1). 3 firma için ~1.41.
            # Eğer eşik bu limitin üzerindeyse tespiti imkansızdır.
            # Bu durumda eşiği limitin %95'ine çekerek en uç değeri yakalarız.
            limit = np.sqrt(n - 1)
            eff_threshold = min(threshold, limit * 0.95)
            
            z_scores = stats.zscore(valid_vals)
            for firm_idx, z in zip(valid_vals.index, z_scores):
                if abs(z) > eff_threshold:
                    is_adapted = eff_threshold < threshold
                    outliers_list.append({
                        'İş Kalemi': item_name,
                        'Firma': firm_idx,
                        'Teklif': valid_vals[firm_idx],
                        'Yöntem': 'Z-Skoru',
                        'Durum': 'ÇOK YÜKSEK' if z > 0 else 'ÇOK DÜŞÜK',
                        'Değer': round(z, 2),
                        'Not': f"Akıllı Eşik ({eff_threshold:.2f})" if is_adapted else ""
                    })
    return pd.DataFrame(outliers_list)

def detect_outliers_iqr(df, firm_cols, factor=1.5):
    """
    İş kalemleri bazında IQR (Çeyrekler arası mesafe) ile aykırı değerleri bulur.
    Sınır = Q1 - (factor * IQR) veya Q3 + (factor * IQR)
    """
    outliers_list = []
    for _, row in df.iterrows():
        item_name = row.iloc[0] if len(row) > 0 else "Bilinmeyen Kalem"
        vals = pd.to_numeric(row[firm_cols], errors='coerce').dropna()
        if len(vals) >= 4: # IQR için anlamlı veri sayısı
            q1 = vals.quantile(0.25)
            q3 = vals.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - (factor * iqr)
            upper_bound = q3 + (factor * iqr)
            
            for firm_idx, val in vals.items():
                if val < lower_bound or val > upper_bound:
                    outliers_list.append({
                        'İş Kalemi': item_name,
                        'Firma': firm_idx,
                        'Teklif': val,
                        'Yöntem': 'IQR',
                        'Durum': 'LİMİT DIŞI',
                        'Değer': f"Alt: {lower_bound:,.0f}, Üst: {upper_bound:,.0f}"
                    })
    return pd.DataFrame(outliers_list)

def detect_low_bids_k_factor(df, firm_cols, k=0.5):
    """
    Aşırı düşük teklif tespiti: Ortalama - (k * Standart Sapma)
    """
    outliers_list = []
    for _, row in df.iterrows():
        item_name = row.iloc[0] if len(row) > 0 else "Bilinmeyen Kalem"
        vals = pd.to_numeric(row[firm_cols], errors='coerce').dropna()
        if len(vals) >= 3:
            mean_val = vals.mean()
            std_val = vals.std()
            limit = mean_val - (k * std_val)
            
            for firm_idx, val in vals.items():
                if val < limit:
                    outliers_list.append({
                        'İş Kalemi': item_name,
                        'Firma': firm_idx,
                        'Teklif': val,
                        'Yöntem': 'k-Değeri',
                        'Durum': 'AŞIRI DÜŞÜK',
                        'Değer': round(val, 2)
                    })
    return pd.DataFrame(outliers_list)

def create_correlation_matrix(df, firm_cols):
    """
    Firmaların teklifleri arasındaki korelasyonu (Pearson) hesaplar.
    """
    firm_data = df[firm_cols].apply(pd.to_numeric, errors='coerce')
    corr_matrix = firm_data.corr(method='pearson')
    return corr_matrix

def generate_heatmap_figure(corr_matrix):
    """
    Korelasyon matrisinden interaktif Plotly Heatmap üretir.
    """
    fig = px.imshow(
        corr_matrix, 
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale="RdBu_r",
        title="Firma Teklif Korelasyon Matrisi (Benzerlikler)",
        labels=dict(color="Korelasyon")
    )
    return fig

def generate_bids_heatmap(df, firm_cols, meta_col):
    """
    Tüm iş kalemlerindeki teklif büyüklüklerini gösteren ısı haritası.
    """
    # İlk 50 kalemi alalım (çok büyükse donmaması için)
    plot_df = df.head(50).copy()
    
    # y ekseni iş kalemleri
    y_labels = plot_df[meta_col].astype(str).tolist()
    
    z_data = plot_df[firm_cols].values
    
    fig = px.imshow(
        z_data,
        x=firm_cols,
        y=y_labels,
        aspect="auto",
        color_continuous_scale="Viridis",
        title="İş Kalemleri Bazında Teklif Büyüklükleri (İlk 50 Kalem)",
        labels=dict(x="Firmalar", y="İş Kalemleri", color="Tutar")
    )
    return fig

def calculate_lowest_bid_stats(df, firm_cols):
    """
    Her iş kalemi için en düşük teklifi veren firmayı bulur.
    Firma bazında: kazanılan kalem sayısı ve oranını döndürür.
    """
    firm_data = df[firm_cols].apply(pd.to_numeric, errors='coerce')
    
    # Sadece en az bir teklif içeren satırları alalım (All-NA hatasını önlemek için)
    valid_rows = firm_data.dropna(how='all')
    
    if valid_rows.empty:
        return pd.DataFrame(columns=['Firma', 'Kazanılan Kalem', 'Başarı Oranı (%)'])

    # En düşük teklifi veren firmayı bul (idxmin artık güvenli)
    winners = valid_rows.idxmin(axis=1)
    total_items = len(valid_rows)
    
    # Firma bazında sayı ve oran
    win_counts = winners.value_counts()
    
    result = []
    for firm in firm_cols:
        count = int(win_counts.get(firm, 0))
        pct = (count / total_items * 100) if total_items > 0 else 0
        result.append({
            'Firma': firm,
            'En Düşük Teklif Sayısı': count,
            'Oran (%)': f"%{pct:.1f}"
        })
    
    result_df = pd.DataFrame(result).sort_values(by='En Düşük Teklif Sayısı', ascending=False).reset_index(drop=True)
    return result_df


def create_dashboard_kpis(df, firm_cols, excel_totals=None):
    """
    Dashboard için temel KPI'ları hesaplar.
    Eğer excel_totals varsa ve firmaları içeriyorsa onları kullanır, yoksa miktarlı hesaplama yapar.
    """
    # Excel'den gelen toplamların geçerli olup olmadığını kontrol et
    use_manual = True
    if excel_totals:
        # Pivot sonrası firma isimleri = supplier isimleri olmalı
        matched = {f: excel_totals[f] for f in firm_cols if f in excel_totals}
        if matched:
            total_bids_series = pd.Series(matched)
            use_manual = False
    
    if use_manual:
        # Miktar kolonunu tespit et ve hesapla (Manuel Fallback)
        qty_col = next((c for c in df.columns if any(kw in str(c).lower() for kw in ['miktar', 'quantity', 'qty', 'adet'])), None)
        total_bids = {}
        for firm in firm_cols:
            prices = pd.to_numeric(df[firm], errors='coerce').fillna(0)
            if qty_col:
                qtys = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
                total_bids[firm] = (prices * qtys).sum()
            else:
                total_bids[firm] = prices.sum()
        total_bids_series = pd.Series(total_bids)
    
    if total_bids_series.empty or total_bids_series.sum() == 0:
        return {
            'toplam_kalem': len(df),
            'firma_sayisi': len(firm_cols),
            'en_dusuk_teklif_firma': "Yok",
            'en_dusuk_tutar': 0,
            'en_yuksek_teklif_firma': "Yok",
            'ortalama_ihale_bedeli': 0
        }

    min_firm = total_bids_series.idxmin()
    max_firm = total_bids_series.idxmax()
    
    kpis = {
        'toplam_kalem': len(df),
        'firma_sayisi': len(firm_cols),
        'en_dusuk_teklif_firma': min_firm,
        'en_dusuk_tutar': total_bids_series.min(),
        'en_yuksek_teklif_firma': max_firm,
        'ortalama_ihale_bedeli': total_bids_series.mean()
    }
    return kpis

def generate_total_bids_chart(df, firm_cols, excel_totals=None, currency="₺"):
    """
    Firmaların toplam ihale bedellerini Bar Chart olarak döndürür.
    En düşük teklif en yukarıda olacak şekilde sıralanır.
    Her çubukta tutar etiketi gösterilir.
    """
    plot_data = []
    
    # excel_totals varsa ve firma isimleri pivot kolonlarıyla eşleşiyorsa kullan
    if excel_totals:
        # Önce direkt eşleşme dene (pivot sonrası firm_cols == supplier names)
        matched = {f: excel_totals[f] for f in firm_cols if f in excel_totals}
        if matched:
            plot_data = [{'Firma': f, 'Toplam İhale Bedeli': v} for f, v in matched.items()]
    
    # Eşleşme yoksa veya excel_totals boşsa, manuel hesapla
    if not plot_data:
        qty_col = next((c for c in df.columns if any(kw in str(c).lower() for kw in ['miktar', 'quantity', 'qty', 'adet'])), None)
        for firm in firm_cols:
            prices = pd.to_numeric(df[firm], errors='coerce').fillna(0)
            if qty_col:
                qtys = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
                total = (prices * qtys).sum()
            else:
                total = prices.sum()
            if total > 0:
                plot_data.append({'Firma': firm, 'Toplam İhale Bedeli': total})
    
    if not plot_data:
        return None
        
    total_df = pd.DataFrame(plot_data).sort_values(by='Toplam İhale Bedeli', ascending=True)
    
    # Renk paleti: her firmaya ayrı renk
    colors = ['#2ecc71', '#3498db', '#e67e22', '#e74c3c', '#9b59b6', '#1abc9c', '#f39c12', '#d35400']
    
    fig = go.Figure()
    for i, row in total_df.iterrows():
        color = colors[len(fig.data) % len(colors)]
        fig.add_trace(go.Bar(
            x=[row['Toplam İhale Bedeli']],
            y=[row['Firma']],
            orientation='h',
            name=row['Firma'],
            marker_color=color,
            text=[f"{currency} {row['Toplam İhale Bedeli']:,.2f}"],
            textposition='outside',
            textfont=dict(size=13, color='#1e293b'),
        ))
    
    max_val = total_df['Toplam İhale Bedeli'].max() if not total_df.empty else 0
    
    fig.update_layout(
        title=f'Firma Toplam İhale Bedelleri Karşılaştırması ({currency})',
        xaxis_title=f"Toplam Tutar ({currency})",
        yaxis_title="Katılımcı Firmalar",
        yaxis=dict(autorange="reversed"),
        xaxis=dict(
            tickformat=',',
            range=[0, max_val * 1.25] # Etiketlere yer bırakmak için %25 genişlet
        ),
        showlegend=False,
        height=max(400, len(plot_data) * 60 + 100),
        margin=dict(r=250, l=150, t=80, b=50),  # Sağ boşluğu artırdık
        bargap=0.3,
    )
    
    return fig

def generate_cv_consistency_chart(stats_df):
    """
    Fiyat tutarlılığını (CV%) gösteren profesyonel bir bar grafik.
    """
    if stats_df is None or stats_df.empty:
        return None
        
    # Eğer tüm CV değerleri 0 veya NaN ise (tek firma durumu vb.)
    if stats_df['CV(%)'].max() == 0:
        # Boş bir figür yerine bilgi veren bir figür döndürebiliriz
        fig = go.Figure()
        fig.add_annotation(text="Yeterli veri yok veya tüm teklifler birebir aynı.<br>Pazar tutarlılığı analizi için en az 2 farklı teklif gereklidir.", 
                           showarrow=False, font=dict(size=16, color="gray"))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), height=300)
        return fig

    plot_df = stats_df.copy()
    
    # Çok fazla kalem varsa grafiği okunabilir kılmak için ilk 50 veya en değişken 50 kalemi alabiliriz
    # Şimdilik hepsini gösterelim ama x eksenini 'category' yaparak çakışmayı önleyelim.
    
    # Renk koşulu: Eşik altı Güvenli (Yeşil), Eşik üstü Riskli (Kırmızı)
    # Burada eşiği stats_df'deki 'Kritik' etiketinden çıkarabiliriz veya parametre alabiliriz.
    # Şimdilik 30 varsayılan, ama dinamik yapmak için:
    limit_str = [s for s in plot_df['Pazar Durumu'].unique() if 'Kritik' in s]
    current_limit = 30.0
    if limit_str:
        try:
            current_limit = float(re.search(r'\d+', limit_str[0]).group())
        except: pass

    plot_df['Renk'] = plot_df['CV(%)'].apply(lambda x: '#ff4b4b' if x > current_limit else '#2ecc71')
    
    # Item No null ise index kullan
    plot_df['Item_Label'] = plot_df['Item No'].astype(str)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=plot_df['Item_Label'],
        y=plot_df['CV(%)'],
        marker=dict(
            color=plot_df['Renk'],
            line=dict(color='white', width=0.5)
        ),
        hovertemplate="<b>Kalem: %{x}</b><br>Varyasyon: %{y:.1f}%<extra></extra>",
        name='CV (%)'
    ))
    
    # Kritik Eşik Çizgisi
    max_cv = plot_df['CV(%)'].max()
    y_limit = max(current_limit + 10, max_cv + 10)
    
    fig.add_shape(
        type="line", x0=-0.5, x1=len(plot_df)-0.5, y0=current_limit, y1=current_limit,
        line=dict(color="rgba(30, 58, 138, 0.8)", width=3, dash="dash"),
    )
    
    # Eşik Label - Dinamik Konum
    fig.add_annotation(
        x=len(plot_df)*0.02, y=current_limit + 1,
        text=f"⚠️ Kritik Eşik (%{int(current_limit)})",
        showarrow=False,
        xanchor="left",
        font=dict(color="blue", size=12, family="Arial Black")
    )
    
    fig.update_layout(
        title=dict(
            text="🚨 Teklif Fiyat Uyumluluk Analizi (Varyasyon Katsayısı - CV)",
            font=dict(size=20, color='#1f2937')
        ),
        xaxis_title="İş Kalemleri",
        yaxis_title="Varyasyon (%)",
        template="plotly_white",
        height=500,
        margin=dict(l=50, r=20, t=80, b=80),
        xaxis=dict(
            type='category', 
            tickangle=-45,
            tickfont=dict(size=10),
            showgrid=False
        ),
        yaxis=dict(
            range=[0, y_limit],
            gridcolor='#f0f0f0',
            ticksuffix="%"
        ),
        hoverlabel=dict(bgcolor="white", font_size=13)
    )
    
    return fig

def generate_cv_donut_chart(stats_df):
    """
    İstatistikler tablosundaki 'Pazar Durumu' verisini temel alarak donut grafik oluşturur.
    Kesin doğruluk için Plotly Express kullanır.
    """
    if stats_df is None or stats_df.empty:
        return None
        
    # 'Teklif Yok' olanları analiz dışı tutalım (Tablo ile senkronize)
    active_df = stats_df[stats_df['Pazar Durumu'] != 'Teklif Yok'].copy()
    if active_df.empty:
        return None

    # Dinamik Renk Haritası
    unique_statuses = active_df['Pazar Durumu'].unique()
    color_map = {}
    for status in unique_statuses:
        if 'Güvenli' in status: color_map[status] = '#2ecc71'
        elif 'Dikkat' in status: color_map[status] = '#f39c12'
        elif 'Kritik' in status: color_map[status] = '#e74c3c'
        elif 'Rekabet Yok' in status: color_map[status] = '#94a3b8'

    fig = px.pie(
        active_df, 
        names='Pazar Durumu',
        title=f"📊 Teklif Fiyat Uyumluluk Özeti (Toplam {len(active_df)} Kalem)",
        hole=0.5,
        color='Pazar Durumu',
        color_discrete_map=color_map
    )

    # Görünüm özelleştirmeleri
    fig.update_traces(
        textinfo='percent+value',
        textposition='inside',
        hovertemplate="<b>%{label}</b><br>Adet: %{value}<br>Oran: %{percent}<extra></extra>"
    )

    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=60, b=100),
        height=500,
        annotations=[dict(text=f'Verili<br>{len(active_df)}', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )

    return fig

def generate_cv_histogram(stats_df):
    """
    Sadece değişkenliği olan kalemlerin (CV >= 5) dağılımını gösteren histogram.
    Riskli bölgedeki yoğunluğu görmeyi sağlar.
    """
    if stats_df is None or stats_df.empty:
        return None
        
    # %5 ve üzeri varyasyonu olan tüm kalemleri "değişken" kabul edip histograma alalım
    plot_df = stats_df[stats_df['CV(%)'] >= 5].copy()
    
    if plot_df.empty:
        # Eğer hiç sapma yoksa (nadir), en üstteki 20 kalemi alalım veya bilgi verelim
        nonzero = stats_df[stats_df['CV(%)'] > 0]
        if not nonzero.empty:
            plot_df = nonzero.sort_values('CV(%)', ascending=False).head(20)
        else:
            return None

    fig = px.histogram(
        plot_df,
        x="CV(%)",
        nbins=15,
        title="⚠️ Riskli Kalemlerin Yoğunluk Dağılımı",
        labels={"CV(%)": "Varyasyon (Sapma %)", "count": "Kalem Sayısı"},
        color_discrete_sequence=['#e67e22'], # Turuncu-Kırmızı arası bir ton
        text_auto=True # Çubukların üzerine sayıları yaz
    )
    
    fig.update_layout(
        template="plotly_white",
        bargap=0.1,
        height=450,
        xaxis=dict(gridcolor='#f0f0f0', ticksuffix="%"),
        yaxis=dict(gridcolor='#f0f0f0', title="Kalem Sayısı"),
        hoverlabel=dict(bgcolor="white")
    )
    
    # Ortalama sapma çizgisini ekleyelim (Bu gruptaki ortalama)
    avg_cv = plot_df['CV(%)'].mean()
    fig.add_vline(x=avg_cv, line_dash="dash", line_color="red", 
                  annotation_text=f"Ort. Sapma: %{avg_cv:.1f}", 
                  annotation_position="top right")
    
    return fig
