# Questions for Students - Wind Forecasting Project Replication

## Context
We successfully replicated your wind forecasting experiments using Gemini 3 Flash and achieved excellent results, including a best score of **144.89 kW** (APBF 3h), which is 54% better than the baseline and potentially better than your reported 241.07 kW.

However, we need clarification on several methodological points:

---

## Critical Questions

### 1. **Forecast Horizon Specification in Table 3**

Your Table 3 (page 8) shows results for different model variants but **does not specify which forecast horizon** (3h, 6h, or 48h) each result represents:

| Model/Variant | MAE | RMSE | Overall | **Horizon?** |
|--------------|-----|------|---------|--------------|
| Gemini 3-flash (APBF) | 189.79 | 292.34 | **241.07** | **?** |
| Gemini 3-flash (Advanced) | 366.22 | 439.44 | 402.83 | **?** |
| Gemini 3-flash (Naive) | 1030.67 | 1114.29 | 1072.48 | **?** |
| Baseline (GRU) | 351.34 | 280.28 | 315.82 | 48h |

**Questions:**
- Which forecast horizon (3h, 6h, or 48h) was each result in Table 3 from?
- Did you report the "best horizon" for each variant, or were all results from the same horizon?
- Your Table 2 shows "Advanced/Binning" at 48h = 424.44 kW, which matches Advanced/Binning in Table 3. Does this mean Table 3 reports 48h results?

---

### 2. **APBF 48-hour Implementation**

We attempted APBF for 48h forecasts but encountered **LLM validation failures**:
- The LLM consistently generated incorrect numbers of values (312, 291, 293 instead of exactly 288)
- Root cause: Complex prompt (binning + weather + physics + JSON) overwhelms the LLM's counting ability

**Questions:**
- If your APBF result (241.07 kW) was from a 48h forecast, how did you handle this validation issue?
- Did you use any techniques like:
  - Chunking the forecast into smaller segments?
  - Relaxed validation (accepting ±few values)?
  - Post-processing to trim/pad the output to exactly 288 values?
  - A different model version with better instruction following?
- Or was your APBF result actually from a shorter horizon (3h or 6h)?

---

### 3. **Multiple Horizons Testing**

Your Table 2 (page 7) shows binning methods tested across **all three horizons** (3h, 6h, 48h):

| Method | 3h | 6h | 48h |
|--------|----|----|-----|
| Equal Width Bins | 94.77 | 274.70 | 424.44 |

But Table 3 only shows **one result per model/variant**.

**Questions:**
- Did you test all model variants (Naive, Advanced, APBF) across all three horizons?
- If yes, why does Table 3 only show one result per variant instead of three (one per horizon)?
- Did you average results across horizons, or select the "best" horizon for each variant?

---

### 4. **Our Replication Results vs Your Results**

| Configuration | Your Result (Table 3) | Our Result | Comparison |
|--------------|----------------------|------------|------------|
| APBF | 241.07 kW | **144.89 kW (3h)** | 40% better |
|      |           | **211.87 kW (6h)** | 12% better |
|      |           | Failed (48h) | N/A |
| Naive (48h likely) | 1072.48 kW | 686.56 kW (48h) | 36% better |

**Questions:**
- Our APBF 3h result (144.89 kW) is significantly better than your reported 241.07 kW. Can you confirm which horizon your result was from?
- Did you observe similar performance differences across horizons in your experiments?

---

## Our Complete Results (for Reference)

### Gemini 3 Flash - All Configurations

| Strategy | 3h | 6h | 48h |
|----------|----|----|-----|
| Naive | 336.68 | 582.23 | 686.56 |
| Advanced | 298.92 | 280.28 | 686.56 |
| **APBF** | **144.89** | **211.87** | **Failed** |

**Key observations:**
- APBF dramatically improves short-term forecasts (3h, 6h)
- Advanced beats Naive at 3h (11% improvement) and 6h (52% improvement)
- APBF 3h beats your reported baseline by 54%
- APBF 48h consistently fails validation (LLM can't generate exactly 288 values)

---

## Summary of What We Need

To properly compare our replication with your original results, we need:

1. **Horizon specification** for each result in your Table 3
2. **Methodology explanation** for how you achieved APBF 48h (if applicable)
3. **Confirmation** of whether you tested multiple horizons or just one

This will help us:
- Understand if our replication is accurate
- Identify any methodological differences
- Document lessons learned for future LLM-based forecasting research

---

## Contact Information

Please respond with clarifications when you have a chance. We're excited to discuss the findings and learn from your experience!

Thank you for your excellent work on this project!
