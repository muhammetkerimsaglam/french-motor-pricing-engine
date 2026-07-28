# pricing_logic.py
"""
FAZ 2: Artık bu dosyadaki katsayılar elle atanmış değil.
Katsayılar train_model.py tarafından freMTPL2 verisi üzerinde eğitilen
Poisson (frekans) ve Gamma (şiddet) GLM modellerinden geliyor ve
model_coefficients.json içinden okunuyor.

app.py bu dosyayı DEĞİŞTİRMEDEN kullanmaya devam edebilir çünkü:
  - RISK_FACTORS sözlüğü aynı yapıda dışa açılıyor (driver_age/engine_power/
    region/claim_history -> kategori -> katsayı)
  - calculate_premium() fonksiyonunun imzası ve dönüş sözlüğü aynı kaldı
"""

import json
from pathlib import Path

_COEF_PATH = Path(__file__).parent / "model_coefficients.json"

if not _COEF_PATH.exists():
    raise FileNotFoundError(
        "model_coefficients.json bulunamadı. Once train_model.py'yi calistirip "
        "cikan JSON dosyasini bu klasore (pricing_logic.py ile ayni yere) koy."
    )

with open(_COEF_PATH, "r", encoding="utf-8") as f:
    _MODEL = json.load(f)

# app.py'nin beklediği görüntüleme/seçim sırası (orijinal UI davranışını korumak için)
_AGE_ORDER = ["18-22", "23-30", "31-55", "55+"]
_POWER_ORDER = ["Low (<75 HP)", "Medium (75-120 HP)", "High (>120 HP)"]
_REGION_ORDER = ["Metropolitan (Big City)", "Urban", "Rural"]
_CLAIMS_ORDER = ["0 Claims (Max Discount)", "1 Claim", "2+ Claims"]


def _ordered(relativities, order):
    return {k: relativities[k] for k in order}


# --- Modelden gelen GERÇEK rölativiteler (elle atanmış değil) ---
RISK_FACTORS = {
    "driver_age": _ordered(_MODEL["frequency_relativities"]["driver_age"], _AGE_ORDER),
    "engine_power": _ordered(_MODEL["frequency_relativities"]["engine_power"], _POWER_ORDER),
    "region": _ordered(_MODEL["frequency_relativities"]["region"], _REGION_ORDER),
    "claim_history": _ordered(_MODEL["frequency_relativities"]["claim_history"], _CLAIMS_ORDER),
}

# Şiddet modeli sadece yaş ve motor gücüne bağlı (GLM'de anlamlı bulunan değişkenler)
SEVERITY_FACTORS = {
    "driver_age": _ordered(_MODEL["severity_relativities"]["driver_age"], _AGE_ORDER),
    "engine_power": _ordered(_MODEL["severity_relativities"]["engine_power"], _POWER_ORDER),
}

BASE_FREQUENCY = _MODEL["base_frequency"]
BASE_SEVERITY = _MODEL["base_severity"]

# Faz 3'te "model kartı" bölümünde göstermek için (app.py henüz kullanmıyor)
MODEL_META = _MODEL["meta"]

# Risk skorunu 0-100'e normalize etmek için, mümkün olan EN YÜKSEK frekans
# çarpanını (tüm kategorilerin en riskli seçenekleri) dinamik olarak hesapla.
# Bu sayede model yeniden eğitilip katsayılar değişse bile skala bozulmaz.
_MAX_FREQ_MULTIPLIER = (
    max(RISK_FACTORS["driver_age"].values())
    * max(RISK_FACTORS["engine_power"].values())
    * max(RISK_FACTORS["region"].values())
    * max(RISK_FACTORS["claim_history"].values())
)


def calculate_premium(age_group, power_group, region_group, claims_group, expense_loading, profit_margin):
    """
    Kullanıcı girdilerine ve aktüeryal parametrelere göre prim hesabı yapar.
    Katsayılar artık gerçek Poisson/Gamma GLM modellerinden geliyor.
    """
    # Frekans için rölativiteler
    f_age = RISK_FACTORS["driver_age"][age_group]
    f_power = RISK_FACTORS["engine_power"][power_group]
    f_region = RISK_FACTORS["region"][region_group]
    f_claims = RISK_FACTORS["claim_history"][claims_group]

    # 1. Frekans Tahmini (Poisson GLM'den gelen çarpımsal model)
    predicted_frequency = BASE_FREQUENCY * f_age * f_power * f_region * f_claims

    # 2. Şiddet Tahmini (Gamma GLM'den gelen çarpımsal model)
    # Not: v1'de sadece "18-22" ve "High power" için ikili (0/1) bir bonus
    # uygulanıyordu. v2'de artık her kategori için modelin öğrendiği
    # gerçek, sürekli rölativiteler kullanılıyor.
    s_age = SEVERITY_FACTORS["driver_age"][age_group]
    s_power = SEVERITY_FACTORS["engine_power"][power_group]
    predicted_severity = BASE_SEVERITY * s_age * s_power

    # 3. Saf Prim (Pure Premium)
    pure_premium = predicted_frequency * predicted_severity

    # 4. Brüt Prim (Gross Premium)
    gross_premium = (pure_premium + expense_loading) / (1 - (profit_margin / 100))

    # Risk Skoru: gerçek maksimum frekans çarpanına göre 0-100'e normalize edilir
    total_multiplier = f_age * f_power * f_region * f_claims
    risk_score = min(int((total_multiplier / _MAX_FREQ_MULTIPLIER) * 100), 100)

    return {
        "frequency": round(predicted_frequency, 4),
        "severity": round(predicted_severity, 2),
        "pure_premium": round(pure_premium, 2),
        "gross_premium": round(gross_premium, 2),
        "risk_score": risk_score,
    }