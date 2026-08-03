# Study Configuration

This document defines the frozen study design in a technology-independent configuration format. It is intended to guide later implementation without choosing a framework, database, or hosting stack.

Final experimental excerpt names, audio filenames, and real mix identities are defined for researcher-facing configuration in `frontend/config/stimuli.json` and `docs/final-stimuli-manifest.md`. Participants must continue to see only neutral Song A/Song B and Version A/B/C labels.

```yaml
study:
  id: intent2control_listening_study
  title: Intent2Control contextual listening study
  dissertation_project: Intent2Control with Controllable Intent Strength
  status: frozen_experimental_design
  estimated_duration: 15-20 minutes
  target_sample:
    pilot: 6-8 participants
    main: approximately 40-50 participants
  data_retention_years: 5
  anonymity:
    direct_identifiers_intentionally_collected: false
    excluded_direct_identifiers:
      - names
      - email addresses
      - IP addresses
      - other direct identifiers

groups:
  - id: group_01
    assigned_excerpts:
      - group_01_song_a_lead_me
      - group_01_song_b_red_to_blue
  - id: group_02
    assigned_excerpts:
      - group_02_song_a_in_the_meantime
      - group_02_song_b_pouring_room

scenarios:
  - id: edr_1_relaxation
    title: EDR-1 — Unwinding After a Demanding Day
    text: You have finished everything that required your attention for the day. You now have some uninterrupted time at home and do not need to complete any other tasks. You feel mentally tired and would like to settle into a calmer state. You decide to spend some time listening to music while you unwind.
  - id: edr_2_distraction
    title: EDR-2 — Taking Your Mind Off Everyday Concerns
    text: You are travelling alone to a familiar destination and have some time before you arrive. A few everyday concerns have been going through your mind repeatedly. There is nothing you can do about them at that moment, and you would prefer not to keep thinking about them. You listen to music to occupy your attention during the journey.
  - id: edr_3_enjoyment
    title: EDR-3 — Enjoying Unstructured Free Time
    text: You have some free time at home and nothing in particular that you need to do. You are not feeling tired or worried, but you would like to enjoy the time rather than let it pass uneventfully. You choose to listen to music for entertainment. You want the listening experience to feel pleasant and engaging.
  - id: fm_1_focus
    title: FM-1 — Sustaining Concentration During Focused Work
    text: You are working on a task that requires sustained concentration for an extended period. You understand what you need to do, but your attention has started to drift. You want to remain mentally engaged and make steady progress without becoming distracted. You listen to music while continuing the task.
  - id: fm_2_motivation
    title: FM-2 — Maintaining Energy During Physical Activity
    text: You are partway through an individual exercise session. The activity requires continued physical effort, but your energy and motivation have begun to decrease. You want to maintain your momentum and complete the session with consistent effort. You listen to music while you continue exercising.

excerpts:
  - id: group_01_song_a_lead_me
    final_excerpt_name: Lead Me
    participant_label: Song A
    audio_source: frontend/assets/audio/study-stimuli/main-study/group_01/song_a_lead_me/
    group: group_01
    mix_slots:
      - slot: mix_01
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_9346b5d4ade2
        audio_filename: researcher-readable mix filename defined in frontend/config/stimuli.json
      - slot: mix_02
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_d5b28dfc8a93
        audio_filename: mix_02.wav
      - slot: mix_03
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_f1f7973e5bac
        audio_filename: mix_03.wav
  - id: group_01_song_b_red_to_blue
    final_excerpt_name: Red To Blue
    participant_label: Song B
    audio_source: frontend/assets/audio/study-stimuli/main-study/group_01/song_b_red_to_blue/
    group: group_01
    mix_slots:
      - slot: mix_01
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_e2654ec905ad
        audio_filename: mix_01.wav
      - slot: mix_02
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_7ac13e0b6376
        audio_filename: mix_02.wav
      - slot: mix_03
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_dcc6aef84d67
        audio_filename: mix_03.wav
  - id: group_02_song_a_in_the_meantime
    final_excerpt_name: In The Meantime
    participant_label: Song A
    audio_source: frontend/assets/audio/study-stimuli/main-study/group_02/song_a_in_the_meantime/
    group: group_02
    mix_slots:
      - slot: mix_01
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_efdedc0a36e7
        audio_filename: mix_01.wav
      - slot: mix_02
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_22efc79c8253
        audio_filename: mix_02.wav
      - slot: mix_03
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_c7bdcba64775
        audio_filename: mix_03.wav
  - id: group_02_song_b_pouring_room
    final_excerpt_name: Pouring Room
    participant_label: Song B
    audio_source: frontend/assets/audio/study-stimuli/main-study/group_02/song_b_pouring_room/
    group: group_02
    mix_slots:
      - slot: mix_01
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_0ddb25d6180b
        audio_filename: mix_01.wav
      - slot: mix_02
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_132e75f34470
        audio_filename: mix_02.wav
      - slot: mix_03
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_cbf8555ee2b2
        audio_filename: mix_03.wav

trial_count_calculations:
  scenarios_per_participant: 5
  excerpts_per_scenario: 2
  trials_per_participant: 10
  mix_versions_per_trial: 3
  ratings_per_participant: 30
  comments_per_participant: 30

rating_scale:
  type: continuous
  minimum: 0
  maximum: 100
  construct: preference
  interface: shared multi-marker preference scale for Practice Trial and Main Study listening tasks
  markers:
    - Version A
    - Version B
    - Version C
  anchors:
    - value: 0
      label: Bad
    - value: 25
      label: Poor
    - value: 50
      label: Fair
    - value: 75
      label: Good
    - value: 100
      label: Excellent
  midpoint_label: null
  marker_triggered_audio_playback: true
  desktop_layout: horizontal shared scale
  mobile_layout: vertical shared scale where needed
  stored_rating_semantics: one integer 0-100 rating per version remains unchanged

comments:
  per_mix_comment_field: true
  comments_required: true
  comments_per_participant: 30
  required: true
  behaviour: required
  empty_or_whitespace_only_allowed: false
  meaningful_response_threshold: TBC

response_time:
  response_time_recording: true
  minimum_recorded_events:
    - study_start
    - page_entry
    - page_exit_or_completion
    - trial_start
    - trial_submission
    - final_submission
  duration_derivation: derive from timestamps
  exact_technical_fields: TBC

audio_playback:
  replay_allowed: true
  replay_limit: none
  comparative_audio_policy:
    applies_to:
      - Pre-Study Listening Task
      - Practice Trial
      - Main Study listening tasks
    one_audio_playing_at_a_time: true
    reset_previous_version_to_start_on_switch: true
    start_newly_selected_version_from_start: true
    seeking_prevented_in_javascript: true
    individual_player_volume_fixed: true
    playback_rate_fixed: true
    download_discouraged_where_browser_supported: true
    native_controls_hidden: true
    custom_controls:
      - Play/Pause
      - Restart
      - progress display
      - elapsed/duration time display
    individual_volume_icon_visible: false
  setup_test_audio:
    configured_temporary_development_path: frontend/assets/audio/study-stimuli/listening-setup/setup_test_audio.wav
    final_file: TBC
    progression_if_file_missing: blocked
  playback_event_recording: TBC
  experimental_audio_format: WAV, 44.1 kHz, stereo, 16-bit PCM frontend copies
  experimental_loudness_preparation: -20.8 LUFS integrated
  experimental_normalisation_policy: revised rating-stratification candidate-review audio normalised during frontend integration where needed

pre_study_listening_task:
  configuration_file: frontend/config/screening.json
  mode: development
  production_ready: false
  participant_facing_label: Pre-Study Listening Task
  current_development_structure: six-item Version A/B/C matching task shown on one scrollable page
  participant_flow_step_count: one study step
  item_count: 6
  segment_count: 2
  repetitions_per_segment: 3
  presentation_order:
    randomised_once_per_attempt: true
    persisted_on_refresh: true
    storage_key_pattern: screening.presentationOrder.attemptN
  answer_position:
    version_a_role: matching reference
    matching_answer_randomised_between:
      - Version B
      - Version C
  temporary_audio_directory: frontend/assets/audio/study-stimuli/pre-study-listening-task/
  source_audio_preserved_as: external Mix Evaluation Dataset source mixes, not copied into the participant-facing interface
  temporary_audio_source: WAV clips generated from original Mix Evaluation Dataset InTheMeantime mix files
  temporary_segments:
    prestudy_segment_01:
      song: InTheMeantime
      reference_mix: DU-H
      comparison_mix: DU-M
      excerpt_start_seconds: 42.0
      excerpt_end_seconds: 48.0
      comparison_offset_seconds_relative_to_reference: 0.0
      files:
        Version A source: screening-item-01-version-a.wav
        matching duplicate source: screening-item-01-version-b.wav
        non_matching source: screening-item-01-version-c.wav
    prestudy_segment_02:
      song: InTheMeantime
      reference_mix: DU-H
      comparison_mix: DU-J
      excerpt_start_seconds: 54.0
      excerpt_end_seconds: 60.0
      comparison_offset_seconds_relative_to_reference: -0.00225
      files:
        Version A source: screening-item-02-version-a.wav
        matching duplicate source: screening-item-02-version-b.wav
        non_matching source: screening-item-02-version-c.wav
  participant_facing_score_displayed: false
  internal_scoring_stored: true
  stored_per_presentation:
    - segment internal ID
    - repetition number
    - presentation order
    - Version A/B/C mapping
    - participant answer
    - correct answer
    - correctness
    - playback state
    - timing fields
  required_audio_choices_per_item:
    - Version A
    - Version B
    - Version C
  answer_options:
    - Version B
    - Version C
  development_answer_position_policy: randomised per generated presentation and persisted with the presentation order
  current_alignment_audit:
    matching_pair_aligned: true
    matching_pair_offset_seconds: 0.000
    previous_non_matching_option: used a different musical segment in the temporary development files
    audio_correction_made: true
    current_non_matching_option: different mix of the same song and same aligned excerpt
    final_scientific_selection_status: final two segment/song selections and scientific selection criteria remain TBC
  old_screening_audit:
    previous_files_identical: true
    previous_answer_key_valid: false
    reason: all previous configured MP3 files had identical byte hashes and therefore did not create a perceptual matching task
  temporary_minimum_score: 2
  temporary_maximum_attempts: 2
  temporary_retry_enabled: true
  temporary_failure_behaviour: development message only
  final_stimuli: TBC
  final_two_segments: TBC
  brecht_preference_based_selection_criteria: TBC
  brecht_preference_results: TBC
  production_correct_answers: TBC
  production_minimum_score: TBC
  production_maximum_attempts: TBC
  failure_or_exclusion_behaviour: TBC
  development_bypass:
    default_enabled: false
    production_allowed: false

instructions:
  acknowledgement_required: true
  acknowledgement_text: I understand how to complete the listening task.
  route_requires_screening_passed: true
  completion_timestamp_recorded: true

practice_trial:
  configuration_file: frontend/config/practice.json
  mode: development
  production_ready: false
  responses_excluded_from_main_analysis: true
  practice_scenario_id: practice_scenario_restaurant
  practice_scenario_label: Practice scenario
  practice_scenario_title: Dinner Date
  practice_excerpt_id: practice_excerpt_practice_song
  participant_excerpt_label: Practice song
  scenario_text: Imagine you are having dinner at a quiet restaurant with someone you recently started dating. The conversation is relaxed, and soft background music is playing while you enjoy the evening. Listen to the three versions of the same music clip and decide which versions feel most suitable for this situation.
  audio_source: frontend/assets/audio/study-stimuli/practice-trial/coldstar/
  audio_source_type: practice-only real Mix Evaluation Dataset song excerpt using three existing dataset mixes, independent from the main experimental songs
  participant_facing_real_song_title_displayed: false
  participant_facing_mix_identities_displayed: false
  excerpt_start_seconds: 12.0
  excerpt_end_seconds: 40.0
  duration_seconds: approximately 28
  version_labels:
    - Version A
    - Version B
    - Version C
  practice_mix_versions:
    - file: practice-version-a-dataset-mix-01.wav
      role: existing dataset mix
    - file: practice-version-b-dataset-mix-02.wav
      role: existing dataset mix
    - file: practice-version-c-dataset-mix-03.wav
      role: existing dataset mix
  rating_scale:
    minimum: 0
    maximum: 100
    step: 1
    untouched_marker_counts_as_complete: false
  comments_required: true
  whitespace_only_comments_allowed: false
  meaningful_response_threshold: TBC
  audio_playback_required_for_completion: true
  audio_playback_requirement_final: confirmed_for_current_practice_interface
  route_requires_instruction_acknowledgement: true
  trial_route_requires_practice_completion: true

randomisation:
  group_assignment:
    groups:
      - group_01
      - group_02
    method: random
    balancing_strategy: TBC
  scenario_order:
    participant_facing: randomised once per participant
    structure: five scenario pairs
    internal_prefixes_only: EDR/FM codes remain internal and are not displayed
  excerpt_order_within_scenario:
    participant_facing_labels:
      - Song A
      - Song B
    stable_mapping_per_participant: true
    randomised_within_each_scenario_pair: true
    pair_adjacency_required: true
  mix_label_mapping:
    display_labels:
      - Version A
      - Version B
      - Version C
    randomised_independently_per_trial: true
  mix_presentation_order: TBC

questionnaires:
  demographic:
    - id: age_range
      response_options: TBC
    - id: gender
      optional: true
      response_options: TBC
    - id: cultural_influence_country
      label: Which country has most influenced your musical and cultural background?
      helper_text: For example, this could be the country where you spent most of your childhood or formative years.
      response_options: TBC
    - id: music_listening_habits
      response_options: TBC
    - id: music_production_or_audio_engineering_experience
      response_options: TBC
    - id: hearing_difficulty
      response_options: TBC
  post_task:
    - id: scenario_immersion
      response_options: TBC
      layout: horizontal_likert_where_space_allows
    - id: task_difficulty
      response_options: TBC
    - id: prior_excerpt_familiarity
      response_options: TBC
    - id: headphones_or_earphones_used
      response_options: TBC
      prefer_not_to_say: false
      other_detail:
        enabled: true
        required_when_other_selected: true
    - id: completion_location_or_environment
      response_options: TBC
      prefer_not_to_say: false
      other_detail:
        enabled: true
        required_when_other_selected: true
    - id: additional_comments
      optional: true

completion_requirements:
  consent_completed: true
  eligibility_completed: true
  audio_screening_passed: true
  practice_trial_completed: true
  experimental_ratings_completed: 30
  experimental_comments_completed: 30
  demographic_questionnaire_completed: true
  post_task_questionnaire_completed: true
  final_submission_confirmed: true

development_final_payload:
  enabled_for_frontend_development_only: true
  production_persistence: false
  storage_key: final.payload
  session_id_key: session.developmentId
  direct_identifiers_intentionally_collected: false
  backend_submission: TBC
  includes:
    - anonymous development session ID
    - study version
    - timestamps
    - consent states
    - listening setup states
    - screening attempts and result
    - instruction acknowledgement
    - practice completion metadata
    - group assignment
    - generated trial order and mix-label mappings
    - submitted experimental responses
    - demographic responses
    - post-task responses
    - final submission timestamp

development_helpers:
  trial_completion_helper:
    enabled_by_default: false
    requires_frontend_development_mode: true
    hidden_in_production: true
    explicit_confirmation_required: true
    creates_placeholder_trial_records: true
    preserves_group_trial_order_and_mappings: true
    modifies_practice_responses: false

data_retention:
  data_retention_years: 5
  retention_start_point: TBC
  deletion_or_archival_procedure: TBC
  responsible_data_custodian: TBC
  must_follow_qmul_requirements: true
```

## Phase 2B.4 frontend implementation note

The current static frontend implements the experimental trial system using `frontend/config/stimuli.json`.

```yaml
frontend_development_trial_system:
  experimental_stimuli_production_ready: true
  full_study_production_ready: false
  config_file: frontend/config/stimuli.json
  stimulus_configuration_version: rating_stratification_v2_2026-08-03
  approved_scenario_wording_inserted: true
  interaction_sequence:
    - Listen to the versions
    - Rate the versions
    - Explain your ratings
  group_assignment:
    group_count: 2
    method: temporary_frontend_random_assignment
    persisted: true
    secure_randomness_used_where_available: true
    final_server_side_balancing: TBC
  trial_generation:
    scenarios_per_participant: 5
    excerpts_per_group: 2
    trials_per_participant: 10
    rule: grouped_scenario_pairs
    scenario_repetition: exactly_twice
    excerpt_repetition_within_scenario: each_assigned_excerpt_once
    scenario_order: randomised_and_persisted
    scenario_pair_adjacency: required
    excerpt_order_within_scenario: randomised_and_persisted
    participant_excerpt_labels:
      - Song A
      - Song B
    participant_excerpt_label_mapping: stable_and_persisted
    internal_scenario_prefixes_displayed_to_participant: false
    compatibility_behaviour:
      old_unsubmitted_trial_order: regenerate
      old_submitted_trial_order: preserve_and_show_development_warning
      stimulus_version_mismatch_before_submission: regenerate_order_with_new_mix_set
      stimulus_version_mismatch_after_submission: preserve_old_records_and_require_fresh_mock_session
  version_mapping:
    labels:
      - Version A
      - Version B
      - Version C
    actual_mix_ids_stored_separately: true
    real_mix_id_displayed_to_participant: false
    mapping_randomised_per_trial: true
    mapping_persisted: true
  trial_validation:
    playback_started_required_for_all_versions: true
    full_playback_required: false
    deliberate_rating_required_for_all_versions: true
    non_whitespace_comment_required_for_all_versions: true
  response_storage:
    submitted_records_key: experimental.submittedTrials
    practice_response_separation: required
    duplicate_submitted_trial_records: not_allowed
  experimental_audio:
    current_path: frontend/assets/audio/study-stimuli/main-study/
    status: revised_rating_stratification_main_study_stimuli_integrated
    replacement_required_before_pilot: false
    manifest: docs/final-stimuli-manifest.md
    master_audio_manifest: docs/study-audio-manifest.md
    source: outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/
```

## Unresolved values

- Verified Participant Information Sheet transcription: TBC.
- Verified consent transcription: TBC.
- Eligibility criteria and listening setup wording: TBC.
- Final setup test audio file: TBC.
- Audio screening instructions, stimuli, correct answers, pass rule, retry behaviour, and exclusion procedure: TBC.
- Supervisor approval for the practice scenario and practice audio: TBC.
- Comment validation meaningful response threshold: TBC.
- Randomisation balancing strategy: TBC.
- Final server-side randomisation balancing strategy: TBC.
- Production scenario order, excerpt order, mix label mapping, and mix presentation order implementation: TBC.
- Final demographic response options: TBC.
- Final post-task response options: TBC.
- Final server-issued participant ID: TBC.
- Production backend submission and secure database persistence: TBC.
- Exact technical timing fields: TBC.
- Detailed playback-event recording: TBC.
- Retention start point, deletion or archival procedure, and responsible data custodian: TBC.
- Backend language, database, HTTPS configuration, server access method, and hosting environment: TBC.
