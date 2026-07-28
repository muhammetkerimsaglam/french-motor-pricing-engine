# train_model.py
"""
FAZ 1: French Motor Claims Pricing Engine - Gerçek GLM Eğitimi
==================================================================

Bu script, mevcut pricing_logic.py'deki elle-atanmış RISK_FACTORS
sözlüğünün yerini alacak GERÇEK katsayıları üretir.

Veri: freMTPL2freq (frequency, data_id=41214) + freMTPL2sev (severity, data_id=41215)
      -> OpenML üzerinden çekilir (Noll, Salzmann & Wuthrich'in klasik
         "French Motor Third Party Liability" veri seti; P&C ratemaking
         literatüründe en çok kullanılan public benchmark veri setlerinden biri)

Metodoloji:
  - Frekans: Poisson GLM, log link, offset = log(Exposure)
             (sklearn'de bu, target=ClaimNb/Exposure, sample_weight=Exposure ile
             yapılır - bu, scikit-learn'ün resmi "Tweedie/Poisson insurance claims"
             örneğinde kullanılan standart tekniktir ve klasik offset yaklaşımıyla
             matematiksel olarak eşdeğerdir.)
  - Şiddet:  Gamma GLM, log link, target = ClaimAmount/ClaimNb (sadece ClaimNb>0),
             sample_weight = ClaimNb

Base (referans) kategoriler mevcut app ile birebir uyumlu tutuldu:
  - driver_age: 31-55
  - engine_power: Medium
  - region: Urban
  - claim_history: 1 Claim

ÖNEMLİ NOT (dürüst bir uyarı):
  freMTPL2'de app'teki kategorilere birebir karşılık gelen sütunlar yok.
  Bu yüzden şu proxy eşlemeleri kullanılıyor - bunlar veri setinin
  gerçek yapısına dayanan MAKUL yaklaşıklardır, birebir aynı değildir:
    - engine_power  <- VehPower (ordinal motor gücü skoru, gerçek HP değil)
    - region        <- Density (nüfus yoğunluğu) tercilleri; French "Region"
                        kodları (R11, R24, vs.) idari bölge olduğu için
                        "Metropolitan/Urban/Rural" ayrımına Density daha uygun
    - claim_history <- BonusMalus (Fransız bonus-malus sistemi, geçmiş hasar
                        durumunu zaten kodluyor: <=50 max bonus/temiz geçmiş,
                        >100 malus/sık hasar)
  Bunu README'de ve LinkedIn postunda AÇIKÇA belirtmen önerilir - şeffaflık
  bir demo projesini "ciddiye alınan" bir projeye dönüştürür.

Çalıştırma:
    pip install scikit-learn pandas numpy
    python train_model.py

Çıktı:
    model_coefficients.json  -> pricing_logic.py'nin okuyacağı gerçek katsayılar
"""

import json
import numpy as np
import pandas as pd
from sklearn.datasets import fetch_openml
from sklearn.linear_model import PoissonRegressor, GammaRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_poisson_deviance, mean_gamma_deviance

RANDOM_STATE = 42

# Uygulamadaki kategorilerle birebir aynı isimler (app.py'yi bozmamak için)
AGE_BASE = "31-55"
POWER_BASE = "Medium (75-120 HP)"
REGION_BASE = "Urban"
CLAIMS_BASE = "1 Claim"


def load_data():
    print("Veri OpenML'den çekiliyor (freMTPL2freq + freMTPL2sev)...")
    freq = fetch_openml(data_id=41214, as_frame=True, parser="auto").frame
    sev = fetch_openml(data_id=41215, as_frame=True, parser="auto").frame

    # Bir poliçede birden fazla hasar satırı olabilir -> IDpol bazında topla
    sev_agg = sev.groupby("IDpol", as_index=False)["ClaimAmount"].sum()

    df = freq.merge(sev_agg, on="IDpol", how="left")
    df["ClaimAmount"] = df["ClaimAmount"].fillna(0.0)

    print(f"Ham veri: {len(df):,} poliçe")
    return df


def clean_data(df):
    """
    Wuthrich ve arkadaşlarının tutorial'larında standart olan temizlik adımları.
    Veri setinde bilinen bazı anomaliler var (Exposure > 1 yıl, aşırı yüksek
    ClaimAmount, ClaimNb ile tutarsız hasar sayıları vb.)
    """
    df = df.copy()
    df["Exposure"] = df["Exposure"].clip(upper=1.0)
    df["ClaimNb"] = df["ClaimNb"].clip(upper=4)
    # ClaimAmount sıfır ama ClaimNb>0 olan (veya tersi) tutarsız satırları at
    df = df[~((df["ClaimNb"] == 0) & (df["ClaimAmount"] > 0))]
    df = df[~((df["ClaimNb"] > 0) & (df["ClaimAmount"] <= 0))]
    # Aşırı uç (outlier) hasar tutarlarını kırp (P&C ratemaking'de standart pratik)
    df["ClaimAmount"] = df["ClaimAmount"].clip(upper=200_000)
    df = df[df["Exposure"] > 0]
    print(f"Temizlik sonrası: {len(df):,} poliçe")
    return df


def bin_age(age):
    if age <= 22:
        return "18-22"
    elif age <= 30:
        return "23-30"
    elif age <= 55:
        return "31-55"
    else:
        return "55+"


def bin_bonus_malus(bm):
    if bm <= 50:
        return "0 Claims (Max Discount)"
    elif bm <= 100:
        return "1 Claim"
    else:
        return "2+ Claims"


def engineer_features(df):
    df = df.copy()
    df["age_group"] = df["DrivAge"].apply(bin_age)

    # VehPower ordinal bir skor (~4-15); terciller ile Low/Medium/High'a ayır
    p33, p66 = df["VehPower"].quantile([0.33, 0.66])
    df["power_group"] = pd.cut(
        df["VehPower"],
        bins=[-np.inf, p33, p66, np.inf],
        labels=["Low (<75 HP)", "Medium (75-120 HP)", "High (>120 HP)"],
    ).astype(str)

    # Density -> Rural / Urban / Metropolitan tercilleri
    d33, d66 = df["Density"].quantile([0.33, 0.66])
    df["region_group"] = pd.cut(
        df["Density"],
        bins=[-np.inf, d33, d66, np.inf],
        labels=["Rural", "Urban", "Metropolitan (Big City)"],
    ).astype(str)

    df["claims_group"] = df["BonusMalus"].apply(bin_bonus_malus)

    print("\n--- Kategori dağılımları (EDA kontrolü) ---")
    for col in ["age_group", "power_group", "region_group", "claims_group"]:
        print(f"\n{col}:")
        print(df[col].value_counts())

    return df


def build_dummies(df, col, base_level, prefix):
    dummies = pd.get_dummies(df[col], prefix=prefix)
    base_col = f"{prefix}_{base_level}"
    if base_col in dummies.columns:
        dummies = dummies.drop(columns=[base_col])
    return dummies


def fit_frequency_model(df):
    print("\n=== FREKANS MODELİ (Poisson GLM) ===")
    X = pd.concat(
        [
            build_dummies(df, "age_group", AGE_BASE, "age"),
            build_dummies(df, "power_group", POWER_BASE, "power"),
            build_dummies(df, "region_group", REGION_BASE, "region"),
            build_dummies(df, "claims_group", CLAIMS_BASE, "claims"),
        ],
        axis=1,
    ).astype(float)

    y = (df["ClaimNb"] / df["Exposure"]).values
    w = df["Exposure"].values

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, w, test_size=0.2, random_state=RANDOM_STATE
    )

    model = PoissonRegressor(alpha=1e-4, max_iter=500)
    model.fit(X_train, y_train, sample_weight=w_train)

    pred_test = model.predict(X_test)
    pred_test = np.clip(pred_test, 1e-6, None)  # deviance hesaplaması için
    dev = mean_poisson_deviance(y_test, pred_test, sample_weight=w_test)
    print(f"Test seti Poisson mean deviance: {dev:.5f}  (düşük = iyi)")

    base_frequency = float(np.exp(model.intercept_))
    print(f"Tahmini baz frekans (31-55 / Medium / Urban / 1 Claim): {base_frequency:.4f}")

    relativities = {"driver_age": {AGE_BASE: 1.0},
                     "engine_power": {POWER_BASE: 1.0},
                     "region": {REGION_BASE: 1.0},
                     "claim_history": {CLAIMS_BASE: 1.0}}

    for col_name, coef in zip(X.columns, model.coef_):
        rel = float(np.exp(coef))
        if col_name.startswith("age_"):
            relativities["driver_age"][col_name.replace("age_", "")] = rel
        elif col_name.startswith("power_"):
            relativities["engine_power"][col_name.replace("power_", "")] = rel
        elif col_name.startswith("region_"):
            relativities["region"][col_name.replace("region_", "")] = rel
        elif col_name.startswith("claims_"):
            relativities["claim_history"][col_name.replace("claims_", "")] = rel

    return base_frequency, relativities, model


def fit_severity_model(df):
    print("\n=== ŞİDDET MODELİ (Gamma GLM) ===")
    sev_df = df[df["ClaimNb"] > 0].copy()
    sev_df["avg_severity"] = sev_df["ClaimAmount"] / sev_df["ClaimNb"]

    # App'te şiddet sadece yaş ve motor gücüne bağlı (mevcut mantıkla tutarlı)
    X = pd.concat(
        [
            build_dummies(sev_df, "age_group", AGE_BASE, "age"),
            build_dummies(sev_df, "power_group", POWER_BASE, "power"),
        ],
        axis=1,
    ).astype(float)
    y = sev_df["avg_severity"].values
    w = sev_df["ClaimNb"].values

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, w, test_size=0.2, random_state=RANDOM_STATE
    )

    model = GammaRegressor(alpha=1e-4, max_iter=500)
    model.fit(X_train, y_train, sample_weight=w_train)

    pred_test = np.clip(model.predict(X_test), 1e-6, None)
    dev = mean_gamma_deviance(y_test, pred_test, sample_weight=w_test)
    print(f"Test seti Gamma mean deviance: {dev:.5f}  (düşük = iyi)")

    base_severity = float(np.exp(model.intercept_))
    print(f"Tahmini baz şiddet (31-55 / Medium): {base_severity:.2f}")

    sev_relativities = {"driver_age": {AGE_BASE: 1.0}, "engine_power": {POWER_BASE: 1.0}}
    for col_name, coef in zip(X.columns, model.coef_):
        rel = float(np.exp(coef))
        if col_name.startswith("age_"):
            sev_relativities["driver_age"][col_name.replace("age_", "")] = rel
        elif col_name.startswith("power_"):
            sev_relativities["engine_power"][col_name.replace("power_", "")] = rel

    return base_severity, sev_relativities


def main():
    df = load_data()
    df = clean_data(df)
    df = engineer_features(df)

    base_freq, freq_relativities, _ = fit_frequency_model(df)
    base_sev, sev_relativities = fit_severity_model(df)

    output = {
        "meta": {
            "source": "freMTPL2freq (data_id=41214) + freMTPL2sev (data_id=41215), OpenML",
            "frequency_model": "PoissonRegressor (sklearn), log link, weight=Exposure",
            "severity_model": "GammaRegressor (sklearn), log link, weight=ClaimNb",
            "note": "region ve claim_history proxy degiskenlerdir (Density, BonusMalus); "
                    "README'de belirtilmelidir.",
        },
        "base_frequency": base_freq,
        "base_severity": base_sev,
        "frequency_relativities": freq_relativities,
        "severity_relativities": sev_relativities,
    }

    with open("model_coefficients.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n✅ model_coefficients.json yazıldı. Faz 2'de pricing_logic.py bunu okuyacak.")


if __name__ == "__main__":
    main()