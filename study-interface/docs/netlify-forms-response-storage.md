# Netlify Forms response storage

The deployed static frontend submits the final listening-study response to Netlify Forms.

Current live study note: the active final interface is the five-mix frontend in
`study-interface/frontend-5mix/`. Earlier three-mix and six-mix interface
folders have been removed locally, but the response-reconstruction workflow
below remains relevant to the current five-mix Netlify export because it
preserves `actual_mix_id` and runtime A-E mappings.

## Configuration

- Form name: `listening-study-5mix`
- Static declaration: `study-interface/frontend-5mix/index.html`
- Submission code: `study-interface/frontend-5mix/js/netlify-submission.js`
- Study version constant: `STUDY_VERSION = "five_mix_frontend_v1_2026-08-06"` in `netlify-submission.js`

Netlify detects the hidden form at deploy time. The review page sends a URL-encoded `POST` to the current deployed HTML path, normally `/pages/review.html`, with `form-name=listening-study-5mix`. No API keys or secrets are used in the frontend.

## Exported CSV columns

Netlify should export these columns:

- `study_id`
- `study_version`
- `submission_status`
- `study_group`
- `started_at`
- `completed_at`
- `duration_seconds`
- `consent_confirmed`
- `demographics_json`
- `assigned_song_ids_json`
- `episode_order_json`
- `song_order_json`
- `mix_mapping_json`
- `presentation_order_json`
- `responses_json`
- `derived_preferences_json`
- `client_validation_json`

`demographics_json` stores the existing demographic responses exactly as held by the frontend. `postTask` responses are not included in the requested fixed CSV schema.

## JSON structures

`assigned_song_ids_json` is an array of configured `sourceSongId` values for the assigned group.

`episode_order_json` is an array of episode IDs in first-presented order.

`song_order_json` is an object keyed by episode ID, where each value is the two-song order shown in that episode:

```json
{
  "EDR-1": ["lead_me", "id_like_to_know"]
}
```

`mix_mapping_json` is nested by episode and song because the current interface randomises Version A-E mappings per trial:

```json
{
  "EDR-1": {
    "lead_me": {
      "A": "lead_me_du_d",
      "B": "lead_me_du_e",
      "C": "lead_me_pxl_l1",
      "D": "lead_me_pxl_l4",
      "E": "lead_me_mcg_pro2"
    }
  }
}
```

`presentation_order_json` records displayed label order by episode and song. The current interface displays A-E in fixed positions, so each trial is normally `["A", "B", "C", "D", "E"]`; the physical stimulus behind each label is stored in `mix_mapping_json`.

`responses_json` is one object per mix rating:

```json
{
  "episode_id": "EDR-1",
  "episode_position": 1,
  "song_id": "lead_me",
  "song_position": 1,
  "display_label": "B",
  "display_position": 2,
  "stimulus_id": "lead_me_pxl_l4",
  "rating": 78,
  "comparative_comment": "Version B felt clearer than the others, and the clearer vocal balance suited the scenario.",
  "response_time_ms": 12450
}
```

`comparative_comment` is collected once per trial and repeated on each corresponding long-format mix-rating object so every rating remains linked to the trial-level explanation.

`derived_preferences_json` stores the highest-rated mix per episode and song. Ties are explicit with `tie: true` and `tied_stimulus_ids`.

`client_validation_json` records compact checks for response count, required comparative comments, stimulus IDs, ratings, episodes, songs, mixes per trial, and mapping consistency.

## Study ID

`study_id` is generated once at study start with `crypto.randomUUID()`. Older browsers fall back to `crypto.getRandomValues()` and finally a non-sequential timestamp/random string. It is stored in the current namespaced study state as `session.studyId` so retries reuse the same ID.

## Duplicate and retry behaviour

Final submission uses `final.submissionInProgress` and `final.submissionCompleted` state flags. The Final Submit button is disabled while saving. Completion is shown only after Netlify returns a successful HTTP response. If submission fails, answers and randomisation remain intact, the same `study_id` is reused, and the participant can retry.

After confirmed success, a small local marker is stored in `final.submissionResult` and route guards prevent repeat submission in the same browser session.

## Testing

Run a local HTTP server from `study-interface/frontend-5mix`, complete the flow for Group 1 and Group 2, and use browser devtools or a fetch mock to inspect the final `POST` to the current review-page path. Direct Netlify Forms storage cannot be fully verified locally; after deployment, complete a pilot submission and confirm it appears under Netlify Site dashboard -> Forms -> `listening-study-5mix`.

Before launch, export pilot/test submissions from Netlify, confirm `study_version`, then delete pilot/test submissions from the Netlify Forms dashboard so launch data starts cleanly.

## Long-format analysis

Use:

```bash
python study-interface/scripts/netlify_forms_to_long_csv.py netlify-export.csv long-format.csv
```

The script parses `responses_json`, preserves participant-level fields, writes a long-format CSV, and creates a validation report beside the output. Do not run it on or commit real participant data.

## Metadata Export With Mix IDs

The current five-mix form `listening-study-5mix` stores enough researcher-facing data to reconstruct the exact physical mixes shown in each trial when the raw Netlify participant-level CSV is available. The raw Netlify CSV is one row per completed submission and contains structured JSON columns such as `assigned_song_ids_json`, `episode_order_json` or `scenario_order_json`, `song_order_json`, `mix_mapping_json`, `presentation_order_json`, `responses_json`, and `client_validation_json`.

The analysis-ready processing utility is:

```cmd
python "study-interface\scripts\netlify_forms_to_long_csv_with_mix_ids.py" ^
  --input "outputs\study_data_checks\listening-study-5mix.csv" ^
  --output-dir "outputs\study_data_checks"
```

It writes:

- `responses_long.csv`: one row per individual displayed-mix rating. It preserves `study_id`, study/config versions, group, episode/scenario, song/excerpt, displayed label, displayed position, `stimulus_id`, `actual_mix_id`, rating, audio played state, comment, and response time.
- `experiment_metadata.csv`: one row per `study_id` x episode/scenario x song trial. It records trial order, episode/song positions, display order, `label_A_stimulus_id`, `label_B_stimulus_id`, `label_C_stimulus_id`, additional label-specific columns when more labels exist, all `stimulus_ids_shown`, all `actual_mix_ids_shown`, the trial-level comment, and per-row metadata validation status.
- `export_validation_report.json`: machine-readable validation summary covering duplicate study IDs, malformed JSON, missing stimulus IDs, missing mappings, mapping-response disagreements, invalid episode IDs, unassigned song IDs, duplicate responses, inconsistent comments, and whether every trial is fully reconstructable.
- `export_validation_issues.csv`: row-wise validation issues for quick inspection.

`study_id` is the anonymous study identifier and should be used in analysis outputs instead of `participant_id`. IP address, user-agent, and other Netlify/platform metadata should not be included in analysis-ready outputs. Keep raw Netlify exports and generated participant/test data out of Git unless a separate approved anonymisation and retention policy says otherwise.

The exact mix reconstruction works as follows: `presentation_order_json` gives the displayed label order for each episode/song trial, `mix_mapping_json` maps each displayed label to a stable physical `stimulus_id`, and `responses_json` repeats the displayed label, position, physical `stimulus_id`, rating, comment, and response time for each displayed mix. The utility validates that these fields agree before reporting the metadata row as `valid`.
