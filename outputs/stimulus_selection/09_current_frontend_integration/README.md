# Current Frontend Integration

This folder records the active four-song, two-group stimulus configuration currently used by the study interface.

The authoritative runtime source is `study-interface/frontend/config/stimuli.json`. The tables here are derived from that configuration and the researcher-facing manifest in `study-interface/docs/final-stimuli-manifest.md`; they do not replace or independently alter the frontend stimuli.

## Status

- Current frontend status: technically integrated; perceptual approval pending.
- Active selections: three mixes per song, two songs per participant group, four songs total.
- Selection basis: corrected acoustic candidate pools followed by Similar/Wide prior-rating stratification and frontend integration.
- Perceptual quality status: not finally approved. Informal researcher listening found that several selected mixes, especially in Wide Ratings sets, sounded subjectively poor or production-unbalanced.

Algorithmic acoustic/rating diversity does not guarantee acceptable production quality. Candidate pools remain available for supervisor review and possible replacement decisions.

## Files

| File | Purpose |
| --- | --- |
| `tables/current_frontend_stimuli.csv` | Current authoritative stimulus table derived from `stimuli.json`. |
| `validation/frontend_stimulus_integrity.md` | Validation notes for configured files, groups, labels, and manifest/config consistency. |
