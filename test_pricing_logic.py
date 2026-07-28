# test_pricing_logic.py
"""
pricing_logic.py icin birim testleri.

Calistirmak icin:
    pip install pytest
    pytest test_pricing_logic.py -v

Not: Bu testler model_coefficients.json'in ayni klasorde bulunmasini
gerektirir (train_model.py calistirildiginda otomatik uretilir).
"""

import pytest
import pricing_logic as pl


# ---------------------------------------------------------------------
# 1. Model dosyasinin dogru yuklendigini ve beklenen yapida oldugunu dogrula
# ---------------------------------------------------------------------

def test_risk_factors_has_all_categories():
    expected_categories = {"driver_age", "engine_power", "region", "claim_history"}
    assert set(pl.RISK_FACTORS.keys()) == expected_categories


def test_base_categories_have_relativity_of_one():
    """Referans (base) kategorilerin rolativitesi tanim geregi 1.0 olmali."""
    assert pl.RISK_FACTORS["driver_age"]["31-55"] == pytest.approx(1.0)
    assert pl.RISK_FACTORS["engine_power"]["Medium (75-120 HP)"] == pytest.approx(1.0)
    assert pl.RISK_FACTORS["region"]["Urban"] == pytest.approx(1.0)
    assert pl.RISK_FACTORS["claim_history"]["1 Claim"] == pytest.approx(1.0)


def test_all_relativities_are_positive():
    """GLM rolativiteleri exp(coef) oldugu icin matematiksel olarak her zaman > 0 olmali."""
    for category in pl.RISK_FACTORS.values():
        for relativity in category.values():
            assert relativity > 0


# ---------------------------------------------------------------------
# 2. calculate_premium() dogru hesapliyor mu?
# ---------------------------------------------------------------------

def _base_case():
    return pl.calculate_premium(
        age_group="31-55",
        power_group="Medium (75-120 HP)",
        region_group="Urban",
        claims_group="1 Claim",
        expense_loading=350,
        profit_margin=15,
    )


def test_base_case_matches_model_base_values():
    """
    Tum kategoriler referans (base) degerde ise, tahmin edilen frekans ve
    siddet, modelin intercept'inden gelen base_frequency / base_severity
    degerlerine esit olmali.
    """
    result = _base_case()
    assert result["frequency"] == pytest.approx(pl.BASE_FREQUENCY, rel=1e-3)
    assert result["severity"] == pytest.approx(pl.BASE_SEVERITY, rel=1e-3)


def test_pure_premium_equals_frequency_times_severity():
    result = _base_case()
    expected_pure = round(result["frequency"] * result["severity"], 2)
    assert result["pure_premium"] == pytest.approx(expected_pure, rel=1e-2)


def test_gross_premium_formula():
    """Gross Premium = (Pure Premium + Expense) / (1 - Margin)"""
    expense = 350
    margin = 15
    result = pl.calculate_premium(
        age_group="31-55",
        power_group="Medium (75-120 HP)",
        region_group="Urban",
        claims_group="1 Claim",
        expense_loading=expense,
        profit_margin=margin,
    )
    expected_gross = (result["pure_premium"] + expense) / (1 - margin / 100)
    assert result["gross_premium"] == pytest.approx(expected_gross, rel=1e-3)


def test_higher_expense_loading_increases_gross_premium():
    low_expense = pl.calculate_premium("31-55", "Medium (75-120 HP)", "Urban", "1 Claim", 100, 15)
    high_expense = pl.calculate_premium("31-55", "Medium (75-120 HP)", "Urban", "1 Claim", 900, 15)
    assert high_expense["gross_premium"] > low_expense["gross_premium"]
    # Saf prim, gider yuklemesinden etkilenmemeli
    assert low_expense["pure_premium"] == pytest.approx(high_expense["pure_premium"])


# ---------------------------------------------------------------------
# 3. Risk siralamasinin mantikli oldugunu dogrula (monotonluk testleri)
# ---------------------------------------------------------------------

def test_young_driver_is_riskier_than_base():
    """18-22 yas grubu, GLM'e gore 31-55'ten daha yuksek frekans/prim vermeli."""
    base = _base_case()
    young = pl.calculate_premium("18-22", "Medium (75-120 HP)", "Urban", "1 Claim", 350, 15)
    assert young["frequency"] > base["frequency"]
    assert young["gross_premium"] > base["gross_premium"]


def test_no_claim_bonus_reduces_premium():
    """Temiz gecmis (0 Claims), 1 Claim referansina gore daha dusuk prim vermeli."""
    base = _base_case()
    clean = pl.calculate_premium("31-55", "Medium (75-120 HP)", "Urban", "0 Claims (Max Discount)", 350, 15)
    assert clean["gross_premium"] < base["gross_premium"]


def test_worst_case_profile_gives_highest_premium():
    """
    En riskli kombinasyon (genc surucu + guclu arac + metropol + cok hasar),
    tum diger kombinasyonlardan daha yuksek brut prim vermeli.
    """
    worst_case = pl.calculate_premium(
        "18-22", "High (>120 HP)", "Metropolitan (Big City)", "2+ Claims", 350, 15
    )
    base = _base_case()
    best_case = pl.calculate_premium(
        "55+", "Low (<75 HP)", "Rural", "0 Claims (Max Discount)", 350, 15
    )
    assert worst_case["gross_premium"] > base["gross_premium"] > best_case["gross_premium"]


# ---------------------------------------------------------------------
# 4. Risk skoru 0-100 araliginda ve mantikli sinirlarda mi?
# ---------------------------------------------------------------------

def test_risk_score_is_within_bounds():
    for age in pl.RISK_FACTORS["driver_age"]:
        for power in pl.RISK_FACTORS["engine_power"]:
            for region in pl.RISK_FACTORS["region"]:
                for claims in pl.RISK_FACTORS["claim_history"]:
                    result = pl.calculate_premium(age, power, region, claims, 350, 15)
                    assert 0 <= result["risk_score"] <= 100


def test_worst_case_risk_score_is_100():
    result = pl.calculate_premium(
        "18-22", "High (>120 HP)", "Metropolitan (Big City)", "2+ Claims", 350, 15
    )
    assert result["risk_score"] == 100


# ---------------------------------------------------------------------
# 5. Gecersiz kategori ismi verilirse acikca hata vermeli (sessizce yanlis sonuc degil)
# ---------------------------------------------------------------------

def test_invalid_category_raises_key_error():
    with pytest.raises(KeyError):
        pl.calculate_premium("99-100", "Medium (75-120 HP)", "Urban", "1 Claim", 350, 15)