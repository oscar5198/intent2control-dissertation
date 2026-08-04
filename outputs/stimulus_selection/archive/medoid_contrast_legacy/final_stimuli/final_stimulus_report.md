# Final Study Stimuli

## Frontend Use
Load `metadata/frontend_stimulus_manifest.json`. Canonical WAV files are under `stimuli/`.

The frontend must shuffle the three stimuli for each song at runtime and assign temporary A/B/C labels for that participant/trial. The runtime mapping must be recorded with each participant response. The manifest does not contain a fixed A/B/C mapping.

Do not expose original filenames, original mix names, institutions, analytical roles, or metadata to participants.

## Selected Stimuli and QC

| Song | Role | Original dataset filename | WAV | Duration | Sample rate | Bit depth | Channels | LUFS | Clipping | SHA-256 |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| In The Meantime | representative | UCP-A4.mp3 | `stimuli/In The Meantime/representative/UCP-A4_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `a0bebed18f4c3d9daa82bd0a0f732c501d723e264aebaabd777f3b964685876b` |
| In The Meantime | contrast_1 | DU-J.mp3 | `stimuli/In The Meantime/contrast_1/DU-J_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `d543d1df22f5381c62266924098b43c085221af5080841251c6b126e12462c20` |
| In The Meantime | contrast_2 | QUT-B.mp3 | `stimuli/In The Meantime/contrast_2/QUT-B_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `f0d132bdef6baa4273ae62c1769221a87d2bce29bf1d4ed0bb683c834886c17b` |
| Lead Me | representative | McG-A.mp3 | `stimuli/Lead Me/representative/McG-A_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `77d762610eacf5347d2276d4de51f250696fe64c9cf679e253bd6cfeac03de75` |
| Lead Me | contrast_1 | PXL-L1.mp3 | `stimuli/Lead Me/contrast_1/PXL-L1_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `02eabf47249ce3536ad2f77c8be35980be7733d21e899a7ca71997d662c820f6` |
| Lead Me | contrast_2 | DU-D.mp3 | `stimuli/Lead Me/contrast_2/DU-D_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `1f75bf8005a843e416e61a3b8dbd23ccc1f4ebd1b28aeadb9a4149b22d4b316e` |
| Pouring Room | representative | McG-Q.mp3 | `stimuli/Pouring Room/representative/McG-Q_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `fe0e67258e9b93f23a2edb3a2e1c09a425514fa2e01d2811f43a2fa2dbd4260a` |
| Pouring Room | contrast_1 | McG-pro1.mp3 | `stimuli/Pouring Room/contrast_1/McG-pro1_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `4e6f81933f4f72b62b426ebb154807cab764eb9ba09ae4749aaac284697a973a` |
| Pouring Room | contrast_2 | McG-X.mp3 | `stimuli/Pouring Room/contrast_2/McG-X_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `e36f0802b6c7f800e38eaac46d97e75c854568c3985f9b340b322ff1559b9d07` |
| Red To Blue | representative | McG-A.mp3 | `stimuli/Red To Blue/representative/McG-A_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `f14a0ca36c50cc785561163cd26542dcb47fc9fa704ceef4cb3126bebdd76ba5` |
| Red To Blue | contrast_1 | McG-B.mp3 | `stimuli/Red To Blue/contrast_1/McG-B_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `474dfe24df9b9817e75a103b2dd9b0c65ff65a9e3641776f2aeb212cb904d528` |
| Red To Blue | contrast_2 | McG-F.mp3 | `stimuli/Red To Blue/contrast_2/McG-F_28sec.wav` | 28.000 | 44100 | 24 | 2 | -20.800 | False | `4054e12f4541a3b339d07ee2e021e56898958a7cce0da5ce4e314b64191b1a80` |

## Hash Validation
- Active WAV count: 12
- All active WAV hashes match the pre-consolidation canonical stimuli hashes.
- Removed legacy metadata had no unique audio; fixed A/B/C mapping is deprecated and consolidated into provenance.

## Audio Specification
- 12 WAVs
- 28.000 seconds
- Stereo
- PCM 24-bit
- 44.1 kHz
- -20.8 LUFS
- No clipping

## Scientific Integrity
No audio, selected mixes, excerpts, analytical roles, QC values, hashes, or scientific decisions were changed.
