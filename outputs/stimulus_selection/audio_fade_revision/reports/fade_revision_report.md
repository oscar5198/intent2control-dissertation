# Audio Fade Revision Report

Supervisor request: remove perceptible excerpt fades and retain only a technically necessary, effectively inaudible anti-click fade.

To minimise interference with immediate mix comparison, perceptible excerpt fades were removed. An identical 5 ms half-cosine fade was retained at each boundary solely to prevent discontinuities and audible clicks.

Previous active configuration found: 1.0 second preview fades in the v2 candidate-pool generator.
Revised configuration: 5.0 ms fade-in, 5.0 ms fade-out, half-cosine shape, applied identically to all regenerated review excerpts.
Rationale: 5 ms is long enough to remove boundary discontinuities at 44.1 kHz while staying below perceptual fade durations and below the 10 ms supervisor limit.

Files updated: main and backup acoustic candidate-pool previews, Similar/Wide triplet review audio, alignment-review copies, rapid-switch files, live supervisor package audio, package manifests, and ZIP archives.
Loudness policy: all active review files remained raw-level; no loudness normalisation, peak normalisation, compression, limiting, or gain change was added.
Scientific preservation: song selections, approved excerpt timings, alignment mappings, feature tables, acoustic distances, ratings, shortlists, and frontend configuration were hash-checked and remained unchanged.
Boundary QC: 386 of 386 regenerated/copied WAV records passed duration/channel/clipping checks.
Package refresh: main package manifest hash 1f869dcd95d9e33df3875e93472ca631623da301acca4ceace5b41b5f9f38325; main ZIP hash caf0c980502f69397ced0341d29fd90a926df00cec36704c98183ee60394471f.
Backup package manifest hash 8d1de4f7a6b8644bd5c2cfc53f9a798337854e7e4783f5c27bdaabae015cc45a; backup ZIP hash 36062017c12f81d3d67c5c3a4a539a3cca521407b5760226d5a70abc74dc34b4.
Warnings: see fade_revision_manifest.csv notes column.
Readiness: revised review audio is ready for pilot listening review subject to supervisor sign-off.
