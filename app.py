# app.py
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
# Kendi yazdığımız mantık dosyasını içeri aktarıyoruz
import pricing_logic as pl

# Sayfa Genişliği ve Başlık Ayarı
st.set_page_config(
    page_title="French Motor Claims Pricing Engine",
    page_icon="🚗",
    layout="wide"
)

# --- 1. ARAYÜZ BAŞLIĞI ---
st.title("🚗 French Motor Claims Actuarial Pricing Engine")
st.caption("v2 — gerçek Poisson/Gamma GLM katsayılarıyla (freMTPL2 veri seti)")
st.markdown("---")

# --- 2. SOL MENÜ (Kullanıcı Girdileri & Aktüeryal Ayarlar) ---
with st.sidebar:
    st.header("📋 Sürücü & Araç Bilgileri")

    # Risk Faktörü Seçimleri
    age_group = st.selectbox(
        "Sürücü Yaş Grubu",
        options=list(pl.RISK_FACTORS["driver_age"].keys()),
        index=2 # Varsayılan olarak '31-55' seçili gelsin
    )

    engine_power = st.selectbox(
        "Araç Motor Gücü",
        options=list(pl.RISK_FACTORS["engine_power"].keys()),
        index=1 # Varsayılan olarak 'Medium' seçili gelsin
    )

    region = st.selectbox(
        "Bölge / Trafik Yoğunluğu",
        options=list(pl.RISK_FACTORS["region"].keys()),
        index=1 # Varsayılan olarak 'Urban' seçili gelsin
    )

    claim_history = st.selectbox(
        "Geçmiş Hasar Durumu (No-Claim Bonus)",
        options=list(pl.RISK_FACTORS["claim_history"].keys()),
        index=0 # Varsayılan olarak '0 Claims' seçili gelsin
    )

    st.markdown("---")
    st.header("⚙️ Aktüeryal Parametreler")

    # Sabit Gider Yüklemesi
    expense_loading = st.slider(
        "Sabit Gider Yüklemesi (TL)",
        min_value=100,
        max_value=1000,
        value=350,
        step=50
    )

    # Şirket Hedef Kar Marjı
    profit_margin = st.slider(
        "Hedef Kâr Marjı (%)",
        min_value=5,
        max_value=30,
        value=15,
        step=1
    )

# --- 3. AKTÜERYAL HESAPLAMANIN TETİKLENMESİ ---
results = pl.calculate_premium(
    age_group=age_group,
    power_group=engine_power,
    region_group=region,
    claims_group=claim_history,
    expense_loading=expense_loading,
    profit_margin=profit_margin
)

# --- 4. SOL TARAF: RİSK METRİKLERİ VE RİSK SKORU İBRESİ ---
col1, col2 = st.columns([1, 1.1])

with col1:
    st.subheader("📊 Tahmin Edilen Risk Metrikleri")

    metric_subcol1, metric_subcol2 = st.columns(2)
    with metric_subcol1:
        st.metric(
            label="Tahmini Yıllık Hasar Frekansı",
            value=f"{results['frequency']:.2%}"
        )
    with metric_subcol2:
        st.metric(
            label="Tahmini Ortalama Hasar Şiddeti",
            value=f"{results['severity']:,.2f} TL"
        )

    st.metric(
        label="Net Saf Prim (Pure Premium)",
        value=f"{results['pure_premium']:,.2f} TL",
        help="Sadece hasar maliyetlerini karşılamak için gereken saf prim tutarı."
    )

    st.markdown("---")
    st.subheader("🎯 Dinamik Risk Skoru Göstergesi")

    # Plotly ile Gauge (Hız/Risk İbresi) Grafiği Oluşturma
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = results['risk_score'],
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Sürücü Risk Endeksi (0-100)", 'font': {'size': 16}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#1E1E2F"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 35], 'color': '#00D2C4'},   # Düşük Risk - Turkuaz
                {'range': [35, 70], 'color': '#F4B400'},  # Orta Risk - Sarı
                {'range': [70, 100], 'color': '#FF4B4B'}  # Yüksek Risk - Kırmızı
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': results['risk_score']
            }
        }
    ))

    fig_gauge.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

# --- 5. SAĞ TARAF: POLİÇE TEKLİFİ & DAĞILIM PASTA GRAFİĞİ ---
with col2:
    st.subheader("💰 Poliçe Teklifi & Fiyatlandırma")

    st.info("Kullanıcıya sunulacak nihai brüt poliçe primi aşağıda hesaplanmıştır:")

    st.markdown(
        f"""
        <div style="background-color:#1E1E2F; padding:20px; border-radius:10px; border-left: 5px solid #00D2C4; margin-bottom: 20px;">
            <h4 style="color:#00D2C4; margin:0;">ÖNERİLEN BRÜT PRİM</h4>
            <h1 style="color:white; margin:10px 0 0 0; font-size:42px;">{results['gross_premium']:,.2f} TL</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Kâr ve Gider Hesaplamaları
    expense_val = expense_loading
    profit_val = results['gross_premium'] - results['pure_premium'] - expense_loading
    pure_val = results['pure_premium']

    # Dağılım Verisi
    pie_data = pd.DataFrame({
        "Bileşen": ["Saf Prim (Hasar Maliyeti)", "Gider Yüklemesi", "Kâr Payı"],
        "Tutar (TL)": [pure_val, expense_val, profit_val]
    })

    # Plotly ile Pasta Grafiği Oluşturma
    fig_pie = px.pie(
        pie_data,
        values="Tutar (TL)",
        names="Bileşen",
        title="Brüt Prim Bileşenleri Dağılımı",
        color_discrete_sequence=['#00D2C4', '#F4B400', '#FF4B4B']
    )

    fig_pie.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
    )

    st.plotly_chart(fig_pie, use_container_width=True)

    # Detay Tablosu
    breakdown_data = {
        "Kalem": ["Saf Prim (Hasar Maliyeti)", "Gider Yüklemesi", "Kâr Payı"],
        "Tutar (TL)": [
            f"{pure_val:,.2f}",
            f"{expense_val:,.2f}",
            f"{max(0, profit_val):,.2f}"
        ]
    }
    st.table(pd.DataFrame(breakdown_data))

# --- 6. "BU PRİM NEDEN BU?" ŞEFFAFLIK GRAFİĞİ ---
st.markdown("---")
st.subheader("🔍 Bu Prim Neden Bu? (Adım Adım Fiyat Oluşumu)")
st.caption(
    "Baz poliçeden (31-55 yaş / Medium güç / Urban / 1 Claim) başlayarak, "
    "seçtiğin her özelliğin prime katkısını gösterir. Katsayılar gerçek "
    "GLM modelinden geliyor."
)

base_pure = pl.BASE_FREQUENCY * pl.BASE_SEVERITY

s_age = pl.SEVERITY_FACTORS["driver_age"][age_group]
s_power = pl.SEVERITY_FACTORS["engine_power"][engine_power]
f_age = pl.RISK_FACTORS["driver_age"][age_group]
f_power = pl.RISK_FACTORS["engine_power"][engine_power]
f_region = pl.RISK_FACTORS["region"][region]
f_claims = pl.RISK_FACTORS["claim_history"][claim_history]

step_base = base_pure
step_age = step_base * f_age * s_age
step_power = step_age * f_power * s_power
step_region = step_power * f_region
step_claims = step_region * f_claims  # == results['pure_premium']
step_expense = step_claims + expense_loading
step_gross = step_expense / (1 - profit_margin / 100)  # == results['gross_premium']

waterfall_labels = [
    "Baz Saf Prim",
    f"Yaş: {age_group}",
    f"Motor Gücü: {engine_power}",
    f"Bölge: {region}",
    f"Hasar Geçmişi: {claim_history}",
    "Gider Yüklemesi",
    "Kâr Marjı",
    "BRÜT PRİM",
]
waterfall_values = [
    step_base,
    step_age - step_base,
    step_power - step_age,
    step_region - step_power,
    step_claims - step_region,
    expense_loading,
    step_gross - step_expense,
    step_gross,
]
waterfall_measures = ["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"]

fig_waterfall = go.Figure(go.Waterfall(
    orientation="v",
    measure=waterfall_measures,
    x=waterfall_labels,
    y=waterfall_values,
    text=[f"{v:,.0f} TL" for v in waterfall_values],
    textposition="outside",
    connector={"line": {"color": "rgba(120,120,120,0.4)"}},
    increasing={"marker": {"color": "#FF4B4B"}},
    decreasing={"marker": {"color": "#00D2C4"}},
    totals={"marker": {"color": "#1E1E2F"}},
))
fig_waterfall.update_layout(
    height=420,
    margin=dict(l=10, r=10, t=20, b=10),
    paper_bgcolor='rgba(0,0,0,0)',
    showlegend=False,
)
st.plotly_chart(fig_waterfall, use_container_width=True)

# --- 7. MODEL PERFORMANSI (LIFT CHART & GINI) ---
st.markdown("---")
st.subheader("📈 Model Performansı & Doğrulama")

_validation_path = Path(__file__).parent / "validation_data.json"

if not _validation_path.exists():
    st.info(
        "validation_data.json bulunamadı. Bu dosya train_model.py çalıştırıldığında "
        "otomatik üretilir — pricing_logic.py ile aynı klasöre koyduğundan emin ol."
    )
else:
    with open(_validation_path, "r", encoding="utf-8") as f:
        validation = json.load(f)

    perf_col1, perf_col2 = st.columns([1, 1.4])

    with perf_col1:
        st.metric(
            label="Gini Katsayısı (Test Seti)",
            value=f"{validation['gini']:.3f}",
            help=(
                "0 = model rastgele siralama yapıyor (ayırt edici gücü yok). "
                "P&C frekans modellerinde 0.20-0.40 arası tipik/makul kabul edilir; "
                "insan davranışının doğası gereği hasar verisi çok gürültülüdür, "
                "bu yüzden 0.60+ gibi değerler beklenmez ve genelde overfitting işaretidir."
            ),
        )
        st.metric(
            label="Poisson Mean Deviance (Test Seti)",
            value=f"{validation['poisson_deviance']:.4f}",
            help="Düşük değer = model test setinde daha iyi genelleme yapıyor."
        )
        st.caption(
            f"Eğitim: {validation['n_train']:,} poliçe · Test: {validation['n_test']:,} poliçe"
        )

    with perf_col2:
        lift_df = pd.DataFrame(validation["lift_chart"])
        fig_lift = go.Figure()
        fig_lift.add_trace(go.Scatter(
            x=lift_df["decile"], y=lift_df["avg_actual"],
            mode="lines+markers", name="Gerçekleşen Frekans",
            line=dict(color="#FF4B4B", width=3),
        ))
        fig_lift.add_trace(go.Scatter(
            x=lift_df["decile"], y=lift_df["avg_predicted"],
            mode="lines+markers", name="Tahmin Edilen Frekans",
            line=dict(color="#00D2C4", width=3, dash="dash"),
        ))
        fig_lift.update_layout(
            title="Lift Chart: Tahmin Edilen Risk Diliminde Gerçek vs Tahmin",
            xaxis_title="Risk Dilimi (1=En düşük risk, 10=En yüksek risk)",
            yaxis_title="Ortalama Yıllık Hasar Frekansı",
            height=340,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_lift, use_container_width=True)

    st.caption(
        "Model, poliçeleri tahmin edilen riske göre 10 dilime ayırdığında, "
        "gerçekleşen hasar frekansının dilimler arttıkça monotonik şekilde "
        "artması modelin riskli/risksiz poliçeleri doğru ayırt ettiğini gösterir."
    )