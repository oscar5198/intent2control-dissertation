# Intent2Control Five-Mix Frontend

This folder contains an isolated five-mix listening-study frontend. It was copied from `study-interface/frontend-6mix/` for implementation convenience, but the active behaviour in this folder is five-mix only.

The approved current three-mix frontend in `study-interface/frontend/` and the six-mix fork in `study-interface/frontend-6mix/` are unchanged.

## Active Configuration

- Frontend root: `study-interface/frontend-5mix/`
- localStorage namespace: `intent2control.study.5mix.v1.`
- State schema: `five_mix_state_v1_2026-08-06`
- Stimulus configuration version: `five_mix_frontend_v1_2026-08-06`
- Netlify Forms name: `listening-study-5mix`
- Netlify schema: `five_mix_netlify_forms_v1`
- Netlify publish directory: `study-interface/frontend-5mix`
- Local entry page: `pages/index.html`
- Main Study versions per task: 5, labelled Version A-Version E
- Main Study total per participant: 6 trials, 30 ratings, 6 shared comparative comments
- Practice trial: five ColdStar versions, preserving the current practice song/excerpt/vignette/rating scale/anchors/purpose/validation separation

## Stimulus Set

The active five-mix set is taken from:

`outputs/stimulus_selection/11_five_mix_selection_review_20260806/recommended_five_mix_selections.csv`

Active songs:

- Group 01, Song A, Lead Me: DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2
- Group 01, Song B, I'd Like To Know: PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7
- Group 02, Song A, In The Meantime: QUT-B, DU-H, DU-I, DU-K, QUT-pro
- Group 02, Song B, Pouring Room: McG-R, McG-T, McG-X, McG-pro1, McG-V

`Red To Blue` is not active in the five-mix config. The frontend-local Main Study audio folder now contains exactly the 20 active WAV files referenced by `config/stimuli.json`.

## State Handling

`js/storage.js` validates saved state against the active five-mix stimulus configuration before route guards run. Corrupt localStorage values are removed, incompatible saved Main Study trial orders are cleared, and final submission state is not written until Netlify returns success.

After a completed submission, testers can revisit `pages/index.html` or use the completion-page button to start a fresh session without manually clearing browser storage.

## Participant UI

Main Study comment fields are visible from the start of each listening trial. Submission still requires all five versions to be played, all five markers deliberately rated, and one non-empty comparative comment.

Marker state colours are neutral in this version. Rated/unrated/currently-playing states remain visible through border and shadow treatment, but the copied orange/green marker cues are not used.

## Validation

Run:

```powershell
python study-interface\scripts\validate_frontend_5mix.py
```

Expected output:

```text
frontend-5mix validation passed
```

For local browser testing, serve the folder over HTTP so config/audio fetches work:

```powershell
python -m http.server 8015 --directory study-interface/frontend-5mix
```

Then open:

```text
http://127.0.0.1:8015/pages/index.html
```

## Known Limitations

- The root `index.html` uses a static meta refresh to `pages/index.html`; Netlify should still publish the folder root, but testers should use `pages/index.html` as the explicit study entry URL when possible.
- Existing Netlify CSV conversion/parser work is not included here; this frontend submits the five-mix form and schema, but downstream export tooling may need a separate five-mix converter.
- Phase 2 marks manual listening confirmation as required before pilot or production use.
- Manual listening should include the closest-neighbour pairs, all five mixes per song, `DU-K` in `In The Meantime`, and the complete `I'd Like To Know` replacement set.
