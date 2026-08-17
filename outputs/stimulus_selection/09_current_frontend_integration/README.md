# Historical Frontend Integration

This folder records an older three-mix frontend-integration state. It is retained
for provenance and downstream references, but it is no longer authoritative for
the live study.

The authoritative runtime source for the live study is now
`study-interface/frontend-5mix/config/stimuli.json`. The tables here were derived
from the older `study-interface/frontend/config/stimuli.json` and the older
researcher-facing manifest in `study-interface/docs/final-stimuli-manifest.md`;
they do not replace or independently alter the current five-mix frontend.

## Status

- Historical frontend status: technically integrated at the time, but superseded.
- Historical selections: three mixes per song, two songs per participant group, four songs total.
- Selection basis: corrected acoustic candidate pools followed by Similar/Wide prior-rating stratification and frontend integration.
- Perceptual quality status: not finally approved. Informal researcher listening found that several selected mixes, especially in Wide Ratings sets, sounded subjectively poor or production-unbalanced.

Algorithmic acoustic/rating diversity does not guarantee acceptable production quality. Candidate pools remain available for supervisor review and possible replacement decisions.

## Files

| File | Purpose |
| --- | --- |
| `tables/current_frontend_stimuli.csv` | Historical stimulus table derived from the older three-mix `stimuli.json`. |
| `validation/frontend_stimulus_integrity.md` | Historical validation notes for configured files, groups, labels, and manifest/config consistency. |
