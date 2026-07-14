# 🚗 French Motor Claims Actuarial Pricing Engine

An interactive, production-ready **Actuarial Motor Pricing Engine** built with **Python**, **Streamlit**, and **Plotly**. 

This project bridges the gap between predictive modeling and business decision-making. It takes the Generalized Linear Model (GLM) coefficients—specifically Poisson for claim frequency and Gamma for claim severity—derived from the **French Motor Claims** dataset and transforms them into a dynamic, user-friendly commercial insurance quotation tool.

---

## 📊 How It Works (Actuarial Methodology)

The pricing engine operates on core actuarial principles to calculate the final commercial premium from raw risk factors:

1. **Pure Premium Calculation:**
   Using a multiplicative tariff structure based on GLM coefficients:
   $$Pure\ Premium = Predicted\ Frequency \times Predicted\ Severity$$

2. **Gross Premium (Commercial Price) Calculation:**
   To transition from risk cost to commercial reality, the engine applies expense and profit loadings using the standard actuarial tariff formula:
   $$Gross\ Premium = \frac{Pure\ Premium + Expense\ Loading}{1 - Profit\ Margin}$$

---

## ✨ Key Features

* **Dynamic Risk Profiling:** Instantly calculates risk exposure based on Driver Age, Engine Power, Region, and No-Claim Bonus (NCB) history.
* **Interactive Actuarial Controls:** Allows underwriters or product managers to adjust expense loadings (fixed costs) and target profit margins dynamically via sliders.
* **Visual Risk Index (Gauge Chart):** Displays an interactive, color-coded risk meter (0-100) indicating the driver's risk tier (Low, Medium, High).
* **Premium Breakdown (Pie Chart):** Provides a clear, visual breakdown of the gross premium into its constituent parts: Pure Premium (Expected Losses), Expense Loading, and Profit Margin.
* **Underwriter's Table:** Renders a clean data table displaying exact monetary values for each pricing component.

---

## 🛠️ Tech Stack & Libraries

* **Frontend/Dashboard:** [Streamlit](https://streamlit.io/)
* **Visualization:** [Plotly Express & Graph Objects](https://plotly.com/)
* **Data Manipulation:** [Pandas](https://pandas.pydata.org/)
* **Backend Logic:** Pure Python

---

## 💻 Local Installation & Usage

To run this pricing engine on your local machine, follow these steps:

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/muhammetkerimsaglam/motor-pricing-engine.git](https://github.com/muhammetkerimsaglam/motor-pricing-engine.git)
   cd motor-pricing-engine
