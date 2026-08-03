# Study Stimuli Audio Index

This folder is a researcher-facing consolidated copy of the active frontend audio used by the study interface. It is not linked from participant-facing pages.

## Folder Index

```text
study-stimuli/
??? listening-setup/
??? pre-study-listening-task/
?   ??? segment_01/
?   ??? segment_02/
??? practice-trial/
?   ??? coldstar/
??? main-study/
    ??? group_01/
    ?   ??? song_a_lead_me/
    ?   ??? song_b_red_to_blue/
    ??? group_02/
        ??? song_a_in_the_meantime/
        ??? song_b_pouring_room/
```

## Listening Setup

- `listening-setup/setup_test_audio.wav` - temporary playback-test audio. Real song/source metadata is not available in current metadata.

## Pre-Study Listening Task

- `pre-study-listening-task/segment_01/reference_mix.wav` - InTheMeantime DU-H, 42-48 s.
- `pre-study-listening-task/segment_01/matching_duplicate.wav` - identical duplicate of segment 01 reference.
- `pre-study-listening-task/segment_01/alternative_mix.wav` - InTheMeantime DU-M, same 42-48 s region.
- `pre-study-listening-task/segment_02/reference_mix.wav` - InTheMeantime DU-H, 54-60 s.
- `pre-study-listening-task/segment_02/matching_duplicate.wav` - identical duplicate of segment 02 reference.
- `pre-study-listening-task/segment_02/alternative_mix.wav` - InTheMeantime DU-J, same 54-60 s region with configured -0.00225 s comparison offset.

These pre-study files are active development/review audio and are not final scientifically approved pre-study stimuli.

## Practice Trial

ColdStar practice-only excerpt, 12-40 s:

- `practice-trial/coldstar/cns_a.wav` - CNS-A
- `practice-trial/coldstar/cns_b.wav` - CNS-B
- `practice-trial/coldstar/cns_c.wav` - CNS-C

## Main Study

Group 1:

- Song A, Lead Me, Wide Ratings: `pxl_l1.wav`, `pxl_l4.wav`, `mcg_pro2.wav`
- Song B, Red To Blue, Wide Ratings: `mcg_c.wav`, `mcg_h.wav`, `mcg_pro1.wav`

Group 2:

- Song A, In The Meantime, Wide Ratings: `du_k.wav`, `qut_pro.wav`, `du_n.wav`
- Song B, Pouring Room, Similar Ratings: `mcg_r.wav`, `mcg_t.wav`, `mcg_x.wav`

Participant-facing pages must continue to show only neutral Song A/Song B and Version A/B/C labels.
