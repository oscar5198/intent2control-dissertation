# Supervisor Review Package

Prepared for review by Georgios and Hidetaka.

## Purpose

This package contains the supervisor-facing listening candidates for the MSc dissertation study. It is designed so reviewers can understand the proposed mix triplets, listen to the recommended audio, and optionally inspect the complete mix pool without opening intermediate analysis files.

The recommendations are based on three evidence streams:

- Acoustic diversity from corrected Diff-MST feature-space candidate pools.
- Brecht's historical no-context preference ratings, used for Similar/Wide rating stratification after acoustic screening.
- Alignment verification using pairwise offsets, waveform checks, and rapid-switch listening files.

The package does not regenerate or alter any analysis result. It reorganises existing review assets only.

## How To Review

1. Start with `Candidate_Summary.csv` for the one-row-per-song overview.
2. Open each `SUMMARY.md` inside `Main_Study_Candidates/` and `Backup_Candidates/`.
3. For a quick review, listen only to the recommended triplets in `Audio/Similar Ratings/` and `Audio/Wide Ratings/`.
4. Use each category's `RapidSwitch.wav` for quick comparison, then listen to the individual recommended mix WAVs.
5. For a deeper review, open `Mix_Pool/` to hear the complete candidate set from which the recommendations were derived.
6. Check `Alignment_Figures/` if a triplet has PASS/REVIEW/FAIL alignment notes.
7. Record whether each recommended triplet is acceptable, whether another combination from `Mix_Pool/` is preferable, or whether replacement candidates should be requested.

## Important Review Note

Algorithmic acoustic/rating diversity does not guarantee acceptable production quality. Several selected mixes, particularly in Wide Ratings sets, may sound subjectively poor or production-unbalanced. Please treat the current triplets as technically selected candidates, not final perceptual approvals.

## Folder Guide

- `Main_Study_Candidates/`: four songs currently used in the main study design.
- `Backup_Candidates/`: four backup songs available if replacements are needed.
- `Mix_Pool/`: complete candidate mix pool for that song, copied from existing preview outputs.
- `Audio/Similar Ratings/` and `Audio/Wide Ratings/`: the selected recommendation triplets plus rapid-switch comparison files.
- `alignment_verification_booklet.pdf`: consolidated alignment evidence.
- `archive/`: original package tables, reports, old package layout, and duplicate copy artifacts retained for provenance.
