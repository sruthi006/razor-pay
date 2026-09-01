# Phase 6 business-value simulation

Both policies were applied to the identical SOFT_RETRY transaction population. Smart Retry makes one calibrated model-selected decision; fixed schedule may attempt +24h, +48h, +72h and stops at first success.

- Eligible transactions: 7,471
- Fixed recovered INR: ₹16,934,995.53
- Smart Retry recovered INR: ₹24,024,851.05
- Incremental INR: ₹7,089,855.52; 95% bootstrap CI [₹5,699,561.18, ₹8,512,409.41]
- Incremental recovery rate: 13.65%; 95% bootstrap CI [12.17%, 15.11%]
- Smart Retry chose a time outside +24/+48/+72h for 65.56% of eligible transactions.

## Interpretation

The bootstrap interval excludes zero, so this simulated incremental effect is statistically supported conditional on this dataset and policy setup.

## Limitations

- This is synthetic data; it is not evidence of production Razorpay outcomes.
- The saved scorer was trained on a subset of the same full population used here, so this whole-population business simulation is not a fully out-of-sample policy estimate.
- Calibration improved global reliability but the High confidence tier remained overconfident in Phase 5.
- The comparison is one Smart Retry attempt versus a three-opportunity fixed schedule; it is a policy prototype, not a live retry policy.
- Phase 4 did not establish conclusive Random Forest superiority over Logistic Regression.
