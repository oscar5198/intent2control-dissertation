from pathlib import Path
import itertools
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

SOURCES = {
    "current_pool": "experimental-design/stimulus-selection/final-selection/source-evidence/current_pool/acoustic_candidate_pool.csv",
    "current_pairwise": "experimental-design/stimulus-selection/final-selection/source-evidence/current_pairwise/pairwise_distances_v2.csv",
    "current_features": "experimental-design/stimulus-selection/final-selection/source-evidence/current_features/processed_features_v2.csv",
    "current_ratings": "experimental-design/stimulus-selection/final-selection/source-evidence/current_ratings/mix_preference_rating_summary_within_song.csv",
    "six_proposals": "experimental-design/stimulus-selection/final-selection/source-evidence/six_proposals/six_mix_proposals.csv",
    "six_pairwise": "experimental-design/stimulus-selection/final-selection/source-evidence/six_pairwise/six_mix_pairwise_distances.csv",
    "six_qc": "experimental-design/stimulus-selection/final-selection/source-evidence/six_qc/six_mix_technical_qc.csv",
    "six_audio": "experimental-design/stimulus-selection/final-selection/source-evidence/six_audio/six_mix_audio_manifest.csv",
    "six_alignment": "experimental-design/stimulus-selection/final-selection/source-evidence/six_alignment/six_mix_alignment_summary.csv",
    "perceptual_status": "experimental-design/stimulus-selection/final-selection/source-evidence/perceptual_status/PERCEPTUAL_REVIEW_STATUS.md",
    "rtb_review": "experimental-design/stimulus-selection/final-selection/source-evidence/rtb_review/final_alignment_and_red_to_blue_review.md",
    "backup_pool": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_pool/acoustic_candidate_pool_backup.csv",
    "backup_pairwise": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_pairwise/pairwise_distances_backup.csv",
    "backup_features": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_features/processed_features_backup.csv",
    "backup_ratings": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_ratings/mix_preference_rating_summary_within_song_backup.csv",
    "backup_review": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_review/mix_level_summary_backup.csv",
    "backup_alignment": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_alignment/alignment_summary_backup.csv",
    "backup_pairwise_alignment": "experimental-design/stimulus-selection/final-selection/source-evidence/backup_pairwise_alignment/pairwise_alignment_verification_backup.csv",
}


def read_csv(name):
    return pd.read_csv(ROOT / SOURCES[name])


current_pool = read_csv("current_pool")
current_pairwise = read_csv("current_pairwise")
current_features = read_csv("current_features")
current_ratings = read_csv("current_ratings").rename(columns={"mean_preference": "mean_previous_preference"})
six = read_csv("six_proposals")
six_pairwise = read_csv("six_pairwise")
six_qc = read_csv("six_qc")
six_audio = read_csv("six_audio")
six_alignment = read_csv("six_alignment")
backup_pool = read_csv("backup_pool")
backup_pairwise = read_csv("backup_pairwise")
backup_features = read_csv("backup_features")
backup_ratings = read_csv("backup_ratings").rename(columns={"mean_preference": "mean_previous_preference"})
backup_review = read_csv("backup_review")
backup_alignment = read_csv("backup_alignment")

ACCEPTED = ["Lead Me", "In The Meantime", "Pouring Room"]
CURRENT = ["Lead Me", "In The Meantime", "Pouring Room", "Red To Blue"]
BACKUPS = sorted(backup_pool["song"].unique())
ALL_SONGS = CURRENT + BACKUPS


def key(a, b):
    return tuple(sorted([str(a), str(b)]))


def pw_lookup(df):
    return {key(r.mix_i_original_name, r.mix_j_original_name): r.to_dict() for _, r in df.iterrows()}


PW_SIX = pw_lookup(six_pairwise)
PW_CURRENT = pw_lookup(current_pairwise)
PW_BACKUP = pw_lookup(backup_pairwise)


def universe(song):
    if song in CURRENT:
        return {
            "review": six[six.song == song].copy(),
            "pool": current_pool[current_pool.song == song].copy(),
            "ratings": current_ratings[current_ratings.song == song].copy(),
            "features": current_features[current_features.song == song].copy(),
            "pairwise": PW_SIX,
            "pool_pairwise": PW_CURRENT,
            "basis": "six_mix_proposals_union",
        }
    return {
        "review": backup_review[backup_review.song == song].copy(),
        "pool": backup_pool[backup_pool.song == song].copy(),
        "ratings": backup_ratings[backup_ratings.song == song].copy(),
        "features": backup_features[backup_features.song == song].copy(),
        "pairwise": PW_BACKUP,
        "pool_pairwise": PW_BACKUP,
        "basis": "backup_supervisor_review_union",
    }


def distance(lookup, a, b):
    row = lookup.get(key(a, b), {})
    if not row:
        return np.nan, False, {}
    near = row.get("near_duplicate_flag", False)
    near = str(near).lower() in {"true", "1"}
    return float(row.get("combined_euclidean_distance", np.nan)), near, row


def metrics(rows, lookup):
    names = list(rows.original_mix_name)
    ratings = rows.set_index("original_mix_name")["mean_previous_preference"].astype(float).to_dict()
    pairs = []
    for a, b in itertools.combinations(names, 2):
        d, n, r = distance(lookup, a, b)
        pairs.append((a, b, d, n, r))
    ds = [p[2] for p in pairs if np.isfinite(p[2])]
    vals = [ratings[n] for n in names]
    best_pair = min(itertools.combinations(names, 2), key=lambda p: abs(ratings[p[0]] - ratings[p[1]]))
    best_pair_spread = abs(ratings[best_pair[0]] - ratings[best_pair[1]])
    best_trip = min(itertools.combinations(names, 3), key=lambda p: max(ratings[x] for x in p) - min(ratings[x] for x in p))
    best_trip_spread = max(ratings[x] for x in best_trip) - min(ratings[x] for x in best_trip)
    similar = list(best_trip if best_trip_spread <= 0.08 else best_pair)
    broad = [n for n in sorted(names, key=lambda x: ratings[x]) if n not in similar]
    return {
        "names": names,
        "min_distance": min(ds) if ds else np.nan,
        "median_distance": float(np.median(ds)) if ds else np.nan,
        "max_distance": max(ds) if ds else np.nan,
        "mean_distance": float(np.mean(ds)) if ds else np.nan,
        "near_duplicate_count": sum(int(p[3]) for p in pairs),
        "rating_range": max(vals) - min(vals),
        "closest_rating_pair_spread": best_pair_spread,
        "closest_rating_triplet_spread": best_trip_spread,
        "similar_subset": similar,
        "range_broadening": broad,
        "pairs": pairs,
    }


def score_combos(rows, lookup):
    output = []
    for names in itertools.combinations(list(rows.original_mix_name), 5):
        m = metrics(rows[rows.original_mix_name.isin(names)].copy(), lookup)
        similar_score = 1.0 if m["closest_rating_triplet_spread"] <= 0.08 else max(0, 1 - m["closest_rating_pair_spread"] / 0.18)
        output.append({**m, "combo": "|".join(names), "similar_score": similar_score})
    df = pd.DataFrame(output)
    for col in ["min_distance", "median_distance", "rating_range"]:
        lo, hi = df[col].min(), df[col].max()
        df[col + "_norm"] = 0.5 if hi == lo else (df[col] - lo) / (hi - lo)
    df["score"] = (
        0.38 * df.min_distance_norm
        + 0.25 * df.median_distance_norm
        + 0.22 * df.rating_range_norm
        + 0.15 * df.similar_score
        - 0.5 * df.near_duplicate_count
    )
    return df.sort_values(["score", "min_distance", "median_distance"], ascending=False)


selected = {}
eval_rows = []
combo_rows = []
for song in ALL_SONGS:
    u = universe(song)
    scored = score_combos(u["review"], u["pairwise"])
    best = scored.iloc[0].to_dict()
    selected[song] = {**u, "names": best["names"], "metrics": best}
    for _, row in scored.drop(columns=["pairs"]).iterrows():
        combo_rows.append({"song": song, **row.to_dict()})

    dvals, near = [], 0
    for a, b in itertools.combinations(list(u["pool"].original_mix_name), 2):
        d, n, _ = distance(u["pool_pairwise"], a, b)
        if np.isfinite(d):
            dvals.append(d)
        near += int(n)
    ratings = u["ratings"]
    eval_rows.append(
        {
            "song": song,
            "artist": u["review"].artist.iloc[0] if "artist" in u["review"] else u["pool"].artist.iloc[0],
            "candidate_pool_mix_count": len(u["pool"]),
            "reviewed_union_mix_count": len(u["review"]),
            "available_candidate_mixes": "|".join(u["pool"].original_mix_name.astype(str)),
            "reviewed_union_mixes": "|".join(u["review"].original_mix_name.astype(str)),
            "candidate_pool_min_pairwise_distance": min(dvals),
            "candidate_pool_median_pairwise_distance": float(np.median(dvals)),
            "candidate_pool_max_pairwise_distance": max(dvals),
            "candidate_pool_near_duplicate_count": near,
            "candidate_pool_rating_range": float(ratings.mean_previous_preference.max() - ratings.mean_previous_preference.min()),
            "minimum_rating_count": int(ratings.rating_count.min()),
            "technical_problematic_mixes": "|".join(
                u["pool"][u["pool"].get("technical_qc_status", pd.Series("", index=u["pool"].index)).astype(str).str.lower().isin(["review_required", "fail"])].original_mix_name.astype(str)
            ),
            "stereo_imbalance_qc_mixes": "|".join(
                u["pool"][u["pool"].get("stereo_imbalance_qc_flag", pd.Series(False, index=u["pool"].index)).astype(str).str.lower().isin(["true", "1"])].original_mix_name.astype(str)
            ),
            "best_reviewed_five_mix_set": "|".join(best["names"]),
            "best_reviewed_five_min_distance": best["min_distance"],
            "best_reviewed_five_median_distance": best["median_distance"],
            "best_reviewed_five_max_distance": best["max_distance"],
            "best_reviewed_five_rating_range": best["rating_range"],
            "best_reviewed_five_similar_subset": "|".join(best["similar_subset"]),
            "best_reviewed_five_range_broadening": "|".join(best["range_broadening"]),
        }
    )


def alignment_summary(song):
    if song in BACKUPS:
        rows = backup_alignment[backup_alignment.song == song]
        pass_count = (rows.automatic_result == "PASS").sum()
        review_count = (rows.automatic_result == "REVIEW").sum()
        score = (pass_count + 0.65 * review_count) / max(1, len(rows))
        text = "; ".join(f"{r.condition}:{r.automatic_result} {float(r.maximum_ms_offset):.1f} ms" for _, r in rows.iterrows())
        return score, text
    rows = six_alignment[six_alignment.song == song]
    status = rows.automatic_status.iloc[0]
    offset = float(rows.maximum_offset_ms.iloc[0])
    score = 0.75 if status == "REVIEW" else 0.55
    return score, f"{status} {offset:.1f} ms; previous Oscar review found no obvious timing issue"


rank_rows = []
for song in ["Red To Blue"] + BACKUPS:
    m = selected[song]["metrics"]
    align_score, align_text = alignment_summary(song)
    reliability = align_score - (0.08 if song == "Red To Blue" else 0)
    score = 0.35 * m["min_distance"] + 0.20 * m["median_distance"] + 1.2 * m["rating_range"] + 0.75 * reliability
    rank_rows.append(
        {
            "song": song,
            "recommended_five": "|".join(m["names"]),
            "min_pairwise_distance": m["min_distance"],
            "median_pairwise_distance": m["median_distance"],
            "max_pairwise_distance": m["max_distance"],
            "rating_range": m["rating_range"],
            "similar_subset": "|".join(m["similar_subset"]),
            "alignment_evidence": align_text,
            "replacement_rank_score": score,
            "notes": "Existing concern: perceived similarity despite acceptable metrics." if song == "Red To Blue" else "Backup reviewed union candidate.",
        }
    )
rank = pd.DataFrame(rank_rows).sort_values("replacement_rank_score", ascending=False)
replacement = "I'd Like To Know"
final_songs = ACCEPTED + [replacement]

BARK_LOW = [f"bark_mid_{i:02d}" for i in range(1, 7)]
BARK_HIGH = [f"bark_mid_{i:02d}" for i in range(17, 25)]
BARK_SIDE = [f"bark_side_{i:02d}" for i in range(1, 25)]


def derived(feat):
    feat = feat.copy()
    feat["bark_mid_low_mean"] = feat[BARK_LOW].mean(axis=1)
    feat["bark_mid_high_mean"] = feat[BARK_HIGH].mean(axis=1)
    feat["bark_side_mean"] = feat[BARK_SIDE].mean(axis=1)
    feat["brightness_proxy_high_minus_low"] = feat["bark_mid_high_mean"] - feat["bark_mid_low_mean"]
    return feat


def contribution(mix, feat):
    feat = derived(feat)
    labels = {
        "rms_mean": "source RMS/energy",
        "crest_factor_mean": "crest factor/dynamics",
        "stereo_width": "stereo width",
        "bark_mid_low_mean": "low/low-mid spectral energy",
        "bark_mid_high_mean": "upper-band spectral energy",
        "bark_side_mean": "side-channel spectral energy",
        "brightness_proxy_high_minus_low": "brightness proxy",
    }
    row = feat[feat.original_mix_name == mix]
    if row.empty:
        return "Feature contribution not available."
    vals = []
    for col, label in labels.items():
        s = pd.to_numeric(feat[col], errors="coerce")
        iqr = s.quantile(0.75) - s.quantile(0.25)
        if abs(iqr) < 1e-9:
            continue
        z = (float(row[col].iloc[0]) - s.median()) / iqr
        vals.append((abs(z), z, label))
    parts = []
    for _, z, label in sorted(vals, reverse=True)[:2]:
        parts.append(("higher " if z > 0 else "lower ") + label)
    return "; ".join(parts)


def nearest(names, mix, lookup):
    best = None
    for other in names:
        if other == mix:
            continue
        d, n, r = distance(lookup, mix, other)
        if np.isfinite(d) and (best is None or d < best[1]):
            best = (other, d, n, r)
    return best or ("", np.nan, False, {})


selection_rows, pair_rows, role_rows, checklist_rows, summary_rows = [], [], [], [], []
for song in final_songs:
    u = selected[song]
    names = u["names"]
    rows = u["review"][u["review"].original_mix_name.isin(names)].copy()
    m = metrics(rows, u["pairwise"])
    similar = set(m["similar_subset"])

    audio = {}
    if song in CURRENT:
        audio = {r.original_mix_name: r.output_path for _, r in six_audio[six_audio.song == song].iterrows()}
    else:
        audio = {r.original_mix_name: "" for _, r in backup_review[backup_review.song == song].iterrows()}

    for a, b in itertools.combinations(names, 2):
        d, n, r = distance(u["pairwise"], a, b)
        pair_rows.append(
            {
                "song": song,
                "mix_i": a,
                "mix_j": b,
                "combined_euclidean_distance": d,
                "scalar_only_distance": r.get("scalar_only_distance", ""),
                "bark_only_distance": r.get("bark_only_distance", ""),
                "rms_excluded_distance": r.get("rms_excluded_distance", ""),
                "near_duplicate_flag": n,
                "selection_status": "recommended_final_five",
            }
        )

    ratings = rows.set_index("original_mix_name").mean_previous_preference.astype(float)
    for _, r in rows.iterrows():
        mix = r.original_mix_name
        near = nearest(names, mix, u["pairwise"])
        rating = float(r.mean_previous_preference)
        role = "similar-rating subset" if mix in similar else "range-broadening"
        if role == "range-broadening" and rating not in [ratings.min(), ratings.max()]:
            role = "range-broadening / rating bridge"
        if song in BACKUPS:
            tech = "clear technical pool QC; PASS alignment for both source triplets" if song == "I'd Like To Know" else "clear technical pool QC; alignment review required"
            confidence = "high" if song == "I'd Like To Know" else "medium"
        else:
            q = six_qc[(six_qc.song == song) & (six_qc.original_mix_name == mix)]
            tech = f"{q.technical_qc_status.iloc[0]} ({q.qc_reasons.iloc[0]})" if len(q) else "review"
            confidence = "medium-high"
        selection_rows.append(
            {
                "song": song,
                "selected_mix_id": r.mix_id,
                "original_mix_name": mix,
                "brecht_mean_previous_preference": rating,
                "rating_count": int(r.rating_count),
                "role_in_set": role,
                "important_acoustic_or_perceptual_contribution": contribution(mix, u["features"]),
                "nearest_selected_neighbour": near[0],
                "nearest_selected_neighbour_distance": near[1],
                "reason_not_near_duplicate": f"nearest selected distance {near[1]:.3f}; near_duplicate_flag={near[2]}",
                "technical_quality_status": tech,
                "confidence_level": confidence,
                "manual_listening_confirmation_required": "yes",
                "review_audio_path": audio.get(mix, ""),
                "source_selection_basis": u["basis"],
            }
        )
        role_rows.append(
            {
                "song": song,
                "original_mix_name": mix,
                "mix_id": r.mix_id,
                "mean_previous_preference": rating,
                "assigned_role": role,
                "similar_subset_members": "|".join(m["similar_subset"]),
                "range_broadening_members": "|".join(m["range_broadening"]),
            }
        )
        checklist_rows.append(
            {
                "song": song,
                "mix": mix,
                "audio_path": audio.get(mix, ""),
                "listen_for": "distinctiveness from nearest neighbour; artefacts; timing; confidence rating differences",
                "nearest_neighbour": near[0],
                "nearest_distance": near[1],
                "approval_decision": "pending",
                "notes": "",
            }
        )

    summary_rows.append(
        {
            "song": song,
            "selected_mixes": "|".join(names),
            "minimum_pairwise_distance": m["min_distance"],
            "median_pairwise_distance": m["median_distance"],
            "maximum_pairwise_distance": m["max_distance"],
            "rating_range": m["rating_range"],
            "similar_rating_subset": "|".join(m["similar_subset"]),
            "range_broadening_mixes": "|".join(m["range_broadening"]),
            "selection_source": u["basis"],
        }
    )

pd.DataFrame(combo_rows).drop(columns=["pairs"], errors="ignore").to_csv(OUT / "five_mix_combination_scores.csv", index=False)
pd.DataFrame(selection_rows).to_csv(OUT / "recommended_five_mix_selections.csv", index=False)
pd.DataFrame(pair_rows).to_csv(OUT / "selected_pairwise_distances.csv", index=False)
summary = pd.DataFrame(summary_rows)
pd.DataFrame([{"source_key": k, "path": v, "exists": (ROOT / v).exists()} for k, v in SOURCES.items()]).to_csv(OUT / "authoritative_sources_manifest.csv", index=False)


def fmt(x, nd=3):
    return "" if pd.isna(x) else f"{float(x):.{nd}f}"


sel = pd.DataFrame(selection_rows)
eval_df = pd.DataFrame(eval_rows)
lines = [
    "# Five-Mix Selection Review",
    "",
    "Generated: 2026-08-06. Review-only recommendation; no frontend, backend, Netlify form, or earlier selection files were modified.",
    "",
    "## Authoritative Sources",
    "",
    "- Current/provisional songs: Stage 4 corrected acoustic pool, Stage 5 Brecht rating summaries, Stage 9 six-mix proposals, pairwise distances, QC, audio manifest, and alignment review.",
    "- Backup songs: Stage 8 backup acoustic pool, Brecht rating integration, supervisor-review mix summaries, pairwise distances, and alignment summaries.",
    "- Perceptual status: existing notes say approval is pending; feature distance is evidence for review, not proof of perceived difference.",
    "",
    "The compact source inputs used by this generator are in `experimental-design/stimulus-selection/final-selection/source-evidence/`. The final review reused existing processed feature tables and existing pairwise distance tables; it did not re-extract MST/Diff-MST features from WAVs or recompute pairwise distances from raw feature vectors. Existing accepted songs retained the previously accepted 28-second excerpt family, while `I'd Like To Know` came from the backup expansion/supervisor-review evidence as the replacement for Red To Blue.",
    "",
    "## Recommended Four-Song Set",
    "",
]
for song in final_songs:
    r = summary[summary.song == song].iloc[0]
    lines.append(f"- {song}: {r.selected_mixes.replace('|', ', ')}")
lines += [
    "",
    f"Recommendation on Red To Blue: replace it with **{replacement}**. Red To Blue is technically usable, but the repository records a perceptual-similarity concern; the replacement has stronger reviewed five-mix reliability.",
    "",
    "## Song-Level Evidence Summary",
    "",
    "| Song | Pool mixes | Recommended five | Min d | Median d | Max d | Rating range | Similar-rating subset |",
    "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
]
for _, r in summary.iterrows():
    e = eval_df[eval_df.song == r.song].iloc[0]
    lines.append(f"| {r.song} | {int(e.candidate_pool_mix_count)} | {r.selected_mixes.replace('|', ', ')} | {fmt(r.minimum_pairwise_distance)} | {fmt(r.median_pairwise_distance)} | {fmt(r.maximum_pairwise_distance)} | {fmt(r.rating_range)} | {r.similar_rating_subset.replace('|', ', ')} |")
lines += [
    "",
    "## Red To Blue And Backup Ranking",
    "",
    "| Rank | Song | Recommended five | Min d | Median d | Rating range | Alignment evidence |",
    "| ---: | --- | --- | ---: | ---: | ---: | --- |",
]
for idx, r in enumerate(rank.reset_index(drop=True).itertuples(), 1):
    lines.append(f"| {idx} | {r.song} | {r.recommended_five.replace('|', ', ')} | {fmt(r.min_pairwise_distance)} | {fmt(r.median_pairwise_distance)} | {fmt(r.rating_range)} | {r.alignment_evidence} |")
lines += [
    "",
    "Interpretation: the ranking is a review aid, not an automatic decision. `I'd Like To Know` is recommended because it combines strong five-mix feasibility with PASS alignment evidence for both source triplets and no stereo-imbalance QC flags.",
    "",
    "## Selected Mix Table",
    "",
    "| Song | Mix | Brecht rating | Role | Contribution | Nearest selected neighbour | Technical status | Confidence | Listen? |",
    "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
]
for _, r in sel.iterrows():
    lines.append(f"| {r.song} | {r.original_mix_name} | {fmt(r.brecht_mean_previous_preference)} | {r.role_in_set} | {r.important_acoustic_or_perceptual_contribution} | {r.nearest_selected_neighbour} ({fmt(r.nearest_selected_neighbour_distance)}) | {r.technical_quality_status} | {r.confidence_level} | {r.manual_listening_confirmation_required} |")
lines += [
    "",
    "## Limitations",
    "",
    "- Diff-MST/MST features support claims about RMS/energy, crest-factor dynamics, stereo width, and Bark spectral/side-channel differences. They do not directly prove vocal prominence, drum prominence, clarity, masking, or perceived preference.",
    "- Oscar must listen to all recommended mixes, especially closest-neighbour pairs, before approval.",
    "- Current accepted songs retain Stage 9 automatic alignment REVIEW/FAIL status, although the existing visual/listening review recommended no source-time correction.",
    "- Review audio paths are referenced, not duplicated, to avoid copying large WAV files.",
    "",
    "## Output Files",
    "",
    "- `recommended_five_mix_selections.csv`",
    "- `selected_pairwise_distances.csv`",
    "- `five_mix_selection_traceability.csv`",
    "- `five_mix_combination_scores.csv`",
    "- `authoritative_sources_manifest.csv`",
    "- `frontend_5mix_main_audio_inventory_after_cleanup.csv`",
]
(OUT / "five_mix_selection_report.md").write_text("\n".join(lines), encoding="utf-8")

print(OUT)
print(summary.to_string(index=False))
