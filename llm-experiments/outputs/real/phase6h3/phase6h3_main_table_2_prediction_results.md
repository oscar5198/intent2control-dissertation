# Main Table 2: Held-Out Preference Prediction

| Model | Condition | Top-1 % | 95% CI | Chance p (BH) | Mean Spearman | MAE | RMSE | Primary role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-5.5 | non_history | 22.7% | [0.174, 0.291] | 0.215 | -0.021 | 29.77 | 35.74 | LLM without participant history |
| GPT-5.5 | personalised_history | 34.3% | [0.281, 0.412] | 5.13e-06 | 0.325 | 21.75 | 30.22 | LLM with participant history |
| Claude Sonnet 5 | non_history | 20.7% | [0.156, 0.269] | 0.430 | -0.092 | 29.90 | 35.26 | LLM without participant history |
| Claude Sonnet 5 | personalised_history | 35.9% | [0.295, 0.427] | 1.43e-06 | 0.248 | 24.47 | 31.73 | LLM with participant history |
| Llama 3.1 70B Instruct | non_history | 24.7% | [0.193, 0.312] | 0.077 | 0.006 | 30.43 | 36.56 | LLM without participant history |
| Llama 3.1 70B Instruct | personalised_history | 25.8% | [0.202, 0.323] | 0.052 | 0.039 | 29.56 | 35.50 | LLM with participant history |
| Centaur | non_history | 24.7% | [0.193, 0.312] | 0.077 | 0.002 | N/A | N/A | LLM without participant history |
| Centaur | personalised_history | 26.3% | [0.206, 0.328] | 0.044 | 0.013 | N/A | N/A | LLM with participant history |
| Mixed-effects primary acoustic | baseline | 34.3% | [0.281, 0.412] | 5.13e-06 | 0.347 | 23.00 | 27.59 | Matched empirical predictive baseline |
