# 🚗 French Motor Claims Actuarial Pricing Engine (v2)

**Live:** https://french-motor-pricing-engine-bdb7zdpmqdohp77mdnm42j.streamlit.app/

An interactive **Actuarial Motor Pricing Engine** built with **Python**, **Streamlit**, and **Plotly**, powered by **real Generalized Linear Models (GLM)** trained on the public French Motor Third-Party Liability (freMTPL2) dataset.

This project bridges predictive modeling and business decision-making: it trains a Poisson GLM (claim frequency) and a Gamma GLM (claim severity) on real insurance data, then turns the resulting coefficients into a dynamic, explainable commercial insurance quotation tool.

---

## 🆕 v2 Update

v1 of this project used manually assigned "actuarial-looking" multipliers to demonstrate the pricing logic and UI. **v2 replaces every coefficient with real relativities learned from data**, and adds model validation and explainability. Specifically:

- `train_model.py` fetches the real **freMTPL2freq / freMTPL2sev** dataset (OpenML, data_id 41214/41215) and fits a Poisson GLM (frequency, log-link, exposure-weighted) and a Gamma GLM (severity, log-link).
- All risk relativities in the app now come from these trained models (`model_coefficients.json`), not from hand-picked assumptions.
- A new **model validation section** shows a decile lift chart and a Gini coefficient computed on a held-out test set — this is the standard way actuaries check whether a pricing model actually discriminates between low- and high-risk policyholders.
- A new **"Why this premium?" waterfall chart** decomposes the final gross premium into the contribution of each risk factor, step by step.

Comparing the same policy profile between v1 and v2 showed the hand-picked v1 coefficients were meaningfully **underpricing** high-risk segments (dense urban region + prior claims) relative to what the real data supports — a concrete illustration of why data-driven pricing matters over intuition-based assumptions.

---

## 📊 Methodology

### 1. Model Training (`train_model.py`, run offline)
- **Data:** freMTPL2freq + freMTPL2sev (Noll, Salzmann & Wüthrich), ~670K policies after standard cleaning (exposure capping, claim count capping, outlier claim amounts capped).
- **Frequency model:** Poisson GLM, `target = ClaimNb / Exposure`, `sample_weight = Exposure` (equivalent to the standard offset-based Poisson GLM formulation).
- **Severity model:** Gamma GLM, `target = ClaimAmount / ClaimNb` (claims only), `sample_weight = ClaimNb`.
- Coefficients are exported as multiplicative relativities relative to a base policy (31-55 / Medium power / Urban / 1 Claim).

### 2. Proxy Variables (transparency note)
freMTPL2 doesn't contain columns that map 1:1 onto this app's UI categories. The following proxies are used, and should be read as reasonable approximations rather than exact matches:

| App category | freMTPL2 source | Rationale |
|---|---|---|
| Engine Power (Low/Medium/High) | `VehPower` (ordinal power score) tercile bins | No raw HP field exists; VehPower is the closest ordinal proxy |
| Region (Rural/Urban/Metropolitan) | `Density` (population density) tercile bins | French administrative region codes don't map to an urban/rural gradient; density does |
| Claim History (0/1/2+ claims) | `BonusMalus` (French no-claims bonus-malus score) | This score already encodes prior claims history by regulatory design |

### 3. Pricing Formulas
$$Pure\ Premium = Predicted\ Frequency \times Predicted\ Severity$$
$$Gross\ Premium = \frac{Pure\ Premium + Expense\ Loading}{1 - Profit\ Margin}$$

### 4. Model Validation Results (test set, ~134K held-out policies)
| Metric | Value | Interpretation |
|---|---|---|
| Gini coefficient | 0.254 | Within the typical 0.20–0.40 range for motor frequency GLMs; confirms the model meaningfully discriminates risk rather than ranking policies randomly |
| Poisson mean deviance | 0.467 | Held-out deviance, used to sanity-check the model isn't overfit |

The lift chart (in-app) groups test policies into 10 exposure-weighted risk deciles and plots actual vs. predicted average frequency per decile — the near-monotonic increase across deciles is the visual counterpart of the Gini result.

---

## ✨ Key Features

* **Data-driven risk profiling:** Frequency/severity predictions from trained Poisson/Gamma GLMs, not hardcoded assumptions.
* **Interactive actuarial controls:** Adjust expense loading and target profit margin dynamically via sliders.
* **Visual risk index (gauge chart):** Color-coded 0–100 risk meter, dynamically normalized to the model's actual max relativity.
* **"Why this premium?" waterfall:** Step-by-step decomposition of the gross premium by risk factor.
* **Model performance panel:** Gini coefficient, Poisson deviance, and a decile lift chart computed on a held-out test set.
* **Premium breakdown (pie chart + table):** Pure premium, expense loading, and profit margin.

---

## 🛠️ Tech Stack & Libraries

* **Frontend/Dashboard:** [Streamlit](https://streamlit.io/)
* **Visualization:** [Plotly Express & Graph Objects](https://plotly.com/)
* **Data manipulation:** [Pandas](https://pandas.pydata.org/) / [NumPy](https://numpy.org/)
* **Model training:** [scikit-learn](https://scikit-learn.org/) (`PoissonRegressor`, `GammaRegressor`)

---

## 📁 Repository Structure

```
motor-pricing-engine/
├── app.py                     # Streamlit UI
├── pricing_logic.py           # Loads model_coefficients.json, computes premiums
├── train_model.py             # Offline training script (Poisson + Gamma GLM)
├── model_coefficients.json    # Trained relativities (output of train_model.py)
├── validation_data.json       # Lift chart + Gini data (output of train_model.py)
└── requirements.txt
```

`model_coefficients.json` and `validation_data.json` are committed to the repo for reproducibility and fast app startup (no need to hit the OpenML API on every deploy). Re-run `train_model.py` to regenerate them from scratch.

---

## Not: pricing_logic.py vs pricing_logic_v1_rulebase.py
`pricing_logic.py` — aktif v2 kodu, model_coefficients.json'dan gerçek 
GLM katsayılarını okur, uygulama bunu kullanır.
`pricing_logic_v1_rulebase.py` — referans amaçlı saklanan orijinal v1 
(elle atanmış katsayılar), sadece "v1 vs v2" karşılaştırmasını 
göstermek için tutulmuştur, uygulama tarafından import edilmez.

## 💻 Local Installation & Usage

```bash
git clone https://github.com/muhammetkerimsaglam/motor-pricing-engine.git
cd motor-pricing-engine

pip install -r requirements.txt
pip install scikit-learn   # only needed to re-run train_model.py

# Optional: retrain the GLMs from scratch (fetches freMTPL2 from OpenML)
python train_model.py

# Run the app
streamlit run app.py
```
## Testing
pip install pytest
pytest test_pricing_logic.py -v

---

## 📚 Data Source

Loupiac, C., et al. — French Motor Third-Party Liability dataset (freMTPL2freq / freMTPL2sev), distributed via [OpenML](https://www.openml.org/) (data_id 41214, 41215). Widely used as a benchmark dataset in actuarial ratemaking research and teaching (e.g. Noll, Salzmann & Wüthrich tutorials).
