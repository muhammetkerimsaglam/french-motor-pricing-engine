# pricing_logic.py

# 1. BAZ DEĞERLER (Intercepts)
BASE_FREQUENCY = 0.12  # Ortalama yıllık hasar sıklığı (Baz Sürücü için)
BASE_SEVERITY = 1500.0  # Ortalama hasar tutarı (Baz Sürücü için - EUR/TL)

# 2. RISK KATSAYILARI (GLM Modelinden Gelen Multipliers)
# Baz değer 1.00'dır. Risk arttıkça katsayı yükselir, azaldıkça düşer.

RISK_FACTORS = {
    "driver_age": {
        "18-22": 1.65,  # Genç sürücü riski yüksek
        "23-30": 1.25,
        "31-55": 1.00,  # Baz grup
        "55+": 0.90,
    },
    "engine_power": {
        "Low (<75 HP)": 0.85,
        "Medium (75-120 HP)": 1.00,  # Baz grup
        "High (>120 HP)": 1.35,      # Güçlü araçlar daha riskli
    },
    "region": {
        "Metropolitan (Big City)": 1.30, # Trafik yoğunluğu
        "Urban": 1.00,
        "Rural": 0.75,
    },
    "claim_history": {
        "0 Claims (Max Discount)": 0.60, # Hasarsızlık indirimi (No-Claim Bonus)
        "1 Claim": 1.00,
        "2+ Claims": 1.80,              # Sık kaza yapanlar için sürprim
    }
}

def calculate_premium(age_group, power_group, region_group, claims_group, expense_loading, profit_margin):
    """
    Kullanıcı girdilerine ve aktüeryal parametrelere göre prim hesabı yapar.
    """
    # Katsayıları sözlükten çekiyoruz
    f_age = RISK_FACTORS["driver_age"][age_group]
    f_power = RISK_FACTORS["engine_power"][power_group]
    f_region = RISK_FACTORS["region"][region_group]
    f_claims = RISK_FACTORS["claim_history"][claims_group]

    # 1. Frekans Tahmini (Multiplicative Poisson Model)
    predicted_frequency = BASE_FREQUENCY * f_age * f_power * f_region * f_claims

    # 2. Şiddet Tahmini (Sürücü yaşı ve araç gücünün hasar büyüklüğüne etkisi)
    # Genç sürücüler ve güçlü araçlar genellikle daha büyük hasar yapar.
    s_age = 1.20 if age_group == "18-22" else 1.00
    s_power = 1.30 if power_group == "High (>120 HP)" else 1.00
    predicted_severity = BASE_SEVERITY * s_age * s_power

    # 3. Saf Prim (Pure Premium)
    pure_premium = predicted_frequency * predicted_severity

    # 4. Brüt Prim (Gross Premium)
    # Formül: (Saf Prim + Sabit Giderler) / (1 - Kar Marjı)
    gross_premium = (pure_premium + expense_loading) / (1 - (profit_margin / 100))

    # Risk Skorunu Belirleme (0 - 100 arası bir endeks)
    # Frekans katsayılarının çarpımına göre normalize edilmiş bir risk puanı
    total_multiplier = f_age * f_power * f_region * f_claims
    risk_score = min(int((total_multiplier / 8.0) * 100), 100) # En yüksek çarpanlara göre oranlama

    return {
        "frequency": round(predicted_frequency, 4),
        "severity": round(predicted_severity, 2),
        "pure_premium": round(pure_premium, 2),
        "gross_premium": round(gross_premium, 2),
        "risk_score": risk_score
    }