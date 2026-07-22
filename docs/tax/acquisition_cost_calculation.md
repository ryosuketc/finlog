# Acquisition Cost Calculation & Audit Guide (総平均法)

This document explains how each column in the `Acquisition Cost Audit` sheet is calculated and the mathematical rules under Japanese Tax Law (国税庁 総平均法).

---

## 1. Column Computation Formulas

Each row in the `Acquisition Cost Audit` sheet represents a chronological inventory event (`CARRYOVER`, `VEST`, `REINVESTMENT`, or `SALE`).

| Column Name | Formula / Logic | Description |
| :--- | :--- | :--- |
| `date` | Event Date (`YYYY-MM-DD`) | Date of vesting, dividend reinvestment, or stock sale. |
| `event_type` | `CARRYOVER`, `VEST`, `REINVESTMENT`, `SALE` | Type of inventory event. |
| `description` | Summary String | Brief event description (e.g. `GSU Vest (10 shares)`). |
| `shares_change` | $\Delta S$ | Change in share count. Positive for acquisitions (+), negative for sales (-). |
| `price_usd` | $P_{\text{USD}}$ | Fair Market Value or execution price in USD per share. |
| `tts_ttb` | $R_{\text{FX}}$ | Applied exchange rate: **TTS** ($TTM + 1.0$) for acquisitions; **TTB** ($TTM - 1.0$) for sales. |
| `event_val_jpy` | $V_{\text{JPY}}$ | Total JPY value of event: <br> • **Acquisition**: $\text{round}(\Delta S \times P_{\text{USD}} \times \text{TTS})$ <br> • **Sale**: $\text{round}(|\Delta S| \times P_{\text{USD}} \times \text{TTB})$ |
| `fee_usd` | $\text{Fee}_{\text{USD}}$ | Sales fee / brokerage expense in USD ($0.00$ for Vests/Reinvestments/Carryover). |
| `fee_jpy` | $\text{Fee}_{\text{JPY}}$ | Sales fee converted to JPY using Sale Date TTB rate: $\text{round}(\text{Fee}_{\text{USD}} \times \text{TTB})$. Subtracted from capital gains. |
| `running_total_shares` | $S_{\text{running}} = S_{\text{prev}} + \Delta S$ | Cumulative total shares held immediately after event. |
| `running_total_cost_jpy` | $C_{\text{running}}$ | Cumulative total JPY acquisition cost of held stock. <br> • **Acquisition**: $C_{\text{prev}} + V_{\text{JPY}}$ <br> • **Sale**: $C_{\text{prev}} - (\Delta S_{\text{sold}} \times \text{AvgCost}_{\text{prev}})$ |
| `running_avg_cost_jpy_per_share` | $\text{AvgCost}_{\text{running}}$ | Average acquisition cost per share in JPY. <br> • **Acquisition** ($S_{\text{running}} > 0$): $\frac{C_{\text{running}}}{S_{\text{running}}}$ <br> • **Sale**: **Unchanged** ($\text{AvgCost}_{\text{running}} = \text{AvgCost}_{\text{prev}}$). |

---

## 2. Handling Carryover Data

To ensure accurate capital gains calculations:
- Always pass the previous year's carryover JSON file via `--carryover user_data/carryover_2023.json`.
- The carryover file specifies initial `shares` and `average_cost_per_share` from prior years, preventing `running_total_shares` from going negative during early sales.
