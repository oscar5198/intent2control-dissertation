# Final Stimuli Manifest

This researcher-facing manifest documents the experimental audio files integrated into the study interface on 2026-07-26.

Participant-facing pages must not display artist names, song titles, source filenames, original mix names, analytical roles, or internal mix identifiers. Participants should see only:

- `Music excerpt: Song A` or `Music excerpt: Song B`
- `Version A`, `Version B`, and `Version C`
- The contextual listening scenario text

## Source Materials

Final WAV files were copied from:

```text
outputs/final_stimuli/stimuli/
```

Source metadata reviewed:

- `outputs/final_stimuli/final_stimulus_report.md`
- `outputs/final_stimuli/metadata/frontend_stimulus_manifest.json`
- `outputs/final_stimuli/metadata/final_selection.csv`
- `outputs/final_stimuli/metadata/provenance.csv`

Participant-group allocation was taken from:

- `outputs/stimulus_selection/01_dataset_and_song_selection/reports/four_song_selection_report.md`

The allocation source names `Group A` and `Group B`; the frontend uses `group_01` and `group_02` as neutral implementation identifiers.

## Frontend Storage Location

The copied experimental audio files are stored under:

```text
study-interface/frontend/assets/audio/experimental/
```

The final frontend filenames are neutral and do not expose source song or mix identities.

## Group Mapping

| Frontend group | Source allocation | Participant labels | Researcher-facing excerpts |
| --- | --- | --- | --- |
| `group_01` | Group A | Song A, Song B | Lead Me; Red To Blue |
| `group_02` | Group B | Song A, Song B | In The Meantime; Pouring Room |

## Integrated Stimulus Files

| Group | Participant excerpt | Artist | Song | Slot | Analytical role | Original mix | Internal mix ID | Source WAV | Frontend WAV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_01` | representative | McG-A | `mix_9346b5d4ade2` | `Lead Me/representative/McG-A_28sec.wav` | `assets/audio/experimental/group_01/song_a/mix_01.wav` |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_02` | contrast_1 | PXL-L1 | `mix_d5b28dfc8a93` | `Lead Me/contrast_1/PXL-L1_28sec.wav` | `assets/audio/experimental/group_01/song_a/mix_02.wav` |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_03` | contrast_2 | DU-D | `mix_f1f7973e5bac` | `Lead Me/contrast_2/DU-D_28sec.wav` | `assets/audio/experimental/group_01/song_a/mix_03.wav` |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_01` | representative | McG-A | `mix_e2654ec905ad` | `Red To Blue/representative/McG-A_28sec.wav` | `assets/audio/experimental/group_01/song_b/mix_01.wav` |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_02` | contrast_1 | McG-B | `mix_7ac13e0b6376` | `Red To Blue/contrast_1/McG-B_28sec.wav` | `assets/audio/experimental/group_01/song_b/mix_02.wav` |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_03` | contrast_2 | McG-F | `mix_dcc6aef84d67` | `Red To Blue/contrast_2/McG-F_28sec.wav` | `assets/audio/experimental/group_01/song_b/mix_03.wav` |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_01` | representative | UCP-A4 | `mix_efdedc0a36e7` | `In The Meantime/representative/UCP-A4_28sec.wav` | `assets/audio/experimental/group_02/song_a/mix_01.wav` |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_02` | contrast_1 | DU-J | `mix_22efc79c8253` | `In The Meantime/contrast_1/DU-J_28sec.wav` | `assets/audio/experimental/group_02/song_a/mix_02.wav` |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_03` | contrast_2 | QUT-B | `mix_c7bdcba64775` | `In The Meantime/contrast_2/QUT-B_28sec.wav` | `assets/audio/experimental/group_02/song_a/mix_03.wav` |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_01` | representative | McG-Q | `mix_0ddb25d6180b` | `Pouring Room/representative/McG-Q_28sec.wav` | `assets/audio/experimental/group_02/song_b/mix_01.wav` |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_02` | contrast_1 | McG-pro1 | `mix_132e75f34470` | `Pouring Room/contrast_1/McG-pro1_28sec.wav` | `assets/audio/experimental/group_02/song_b/mix_02.wav` |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_03` | contrast_2 | McG-X | `mix_cbf8555ee2b2` | `Pouring Room/contrast_2/McG-X_28sec.wav` | `assets/audio/experimental/group_02/song_b/mix_03.wav` |

## Technical Validation

All 12 integrated files were decoded with Python's WAV reader and checked after copying.

| Check | Result |
| --- | --- |
| File count | 12 WAV files |
| Duration | 28.000 seconds each |
| Sample rate | 44,100 Hz |
| Channels | Stereo |
| Bit depth | 24-bit PCM |
| File size | 7,408,844 bytes each |
| Non-silent audio | Passed |
| Unique SHA-256 hashes | Passed |

The final stimulus report also describes the files as loudness-normalised to -20.8 LUFS with no detected clipping.

## Runtime Randomisation Requirements

The final stimulus files are fixed in `frontend/config/stimuli.json`, but participant presentation remains randomised:

- A participant is assigned one group.
- Scenario order is randomised once and persisted.
- The two assigned song trials within each scenario remain adjacent.
- Song A/Song B order may be randomised within each scenario pair.
- Version A/B/C mapping is randomised independently for each trial and persisted.
- The analysis payload stores neutral display labels separately from internal mix identifiers.

## Licensing and Usage Notes

The final stimulus metadata reviewed for this integration did not contain complete per-file licensing fields. Earlier song-selection documentation notes Creative Commons BY 3.0 licensing for `Red To Blue` and `Pouring Room`. Any remaining licensing or permission checks for `Lead Me` and `In The Meantime` should be confirmed before deployment if they are not already covered by the study's existing permissions workflow.

## Remaining Non-Stimulus Dependencies

The experimental audio stimuli are now production-ready in the frontend configuration. This does not mean the full study is deployed or production-ready. The following remain outside this manifest:

- Final server-side balanced group assignment.
- Production backend submission and secure storage.
- Final setup-test audio.
- Final audio-screening stimuli and pass/failure policy.
- Final practice-trial audio or replacement decision.
