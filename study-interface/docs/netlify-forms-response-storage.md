# Netlify Forms response storage

The deployed static frontend submits the final listening-study response to Netlify Forms.

## Configuration

- Form name: `listening-study`
- Static declaration: `study-interface/frontend/index.html`
- Submission code: `study-interface/frontend/js/netlify-submission.js`
- Study version constant: `STUDY_VERSION = "2026-08-04-v1"` in `netlify-submission.js`

Netlify detects the hidden form at deploy time. The review page sends a URL-encoded `POST` to the current deployed HTML path, normally `/pages/review.html`, with `form-name=listening-study`. No API keys or secrets are used in the frontend.

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

`episode_order_json` is an array of scenario IDs in first-presented order.

`song_order_json` is an object keyed by episode ID, where each value is the two-song order shown in that episode:

```json
{
  "edr_1_relaxation": ["lead_me", "red_to_blue"]
}
```

`mix_mapping_json` is nested by episode and song because the current interface randomises Version A/B/C mappings per trial:

```json
{
  "edr_1_relaxation": {
    "lead_me": {
      "A": "lead_me_pxl_l1",
      "B": "lead_me_pxl_l4",
      "C": "lead_me_mcg_pro2"
    }
  }
}
```

`presentation_order_json` records displayed label order by episode and song. The interface displays A/B/C in fixed positions, so each trial is normally `["A", "B", "C"]`; the physical stimulus behind each label is stored in `mix_mapping_json`.

`responses_json` is one object per mix rating:

```json
{
  "episode_id": "edr_1_relaxation",
  "episode_position": 1,
  "song_id": "lead_me",
  "song_position": 1,
  "display_label": "B",
  "display_position": 2,
  "stimulus_id": "lead_me_pxl_l4",
  "rating": 78,
  "comment": "Clear vocals; useful for concentrating.",
  "response_time_ms": 12450
}
```

`derived_preferences_json` stores the highest-rated mix per episode and song. Ties are explicit with `tie: true` and `tied_stimulus_ids`.

`client_validation_json` records compact checks for response count, required comments, stimulus IDs, ratings, episodes, songs, mixes per trial, and mapping consistency.

## Study ID

`study_id` is generated once at study start with `crypto.randomUUID()`. Older browsers fall back to `crypto.getRandomValues()` and finally a non-sequential timestamp/random string. It is stored in the current namespaced study state as `session.studyId` so retries reuse the same ID.

## Duplicate and retry behaviour

Final submission uses `final.submissionInProgress` and `final.submissionCompleted` state flags. The Final Submit button is disabled while saving. Completion is shown only after Netlify returns a successful HTTP response. If submission fails, answers and randomisation remain intact, the same `study_id` is reused, and the participant can retry.

After confirmed success, a small local marker is stored in `final.submissionResult` and route guards prevent repeat submission in the same browser session.

## Testing

Run a local HTTP server from `study-interface/frontend`, complete the flow for Group 1 and Group 2, and use browser devtools or a fetch mock to inspect the final `POST` to the current review-page path. Direct Netlify Forms storage cannot be fully verified locally; after deployment, complete a pilot submission and confirm it appears under Netlify Site dashboard -> Forms -> `listening-study`.

Before launch, export pilot/test submissions from Netlify, confirm `study_version`, then delete pilot/test submissions from the Netlify Forms dashboard so launch data starts cleanly.

## Long-format analysis

Use:

```bash
python study-interface/scripts/netlify_forms_to_long_csv.py netlify-export.csv long-format.csv
```

The script parses `responses_json`, preserves participant-level fields, writes a long-format CSV, and creates a validation report beside the output. Do not run it on or commit real participant data.
