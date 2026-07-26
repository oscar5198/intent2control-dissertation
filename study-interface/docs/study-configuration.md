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
    audio_source: frontend/assets/audio/experimental/group_01/song_a/
    group: group_01
    mix_slots:
      - slot: mix_01
        display_label: Version A, Version B, or Version C
        real_mix_identity: mix_9346b5d4ade2
        audio_filename: mix_01.wav
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
    audio_source: frontend/assets/audio/experimental/group_01/song_b/
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
    audio_source: frontend/assets/audio/experimental/group_02/song_a/
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
    audio_source: frontend/assets/audio/experimental/group_02/song_b/
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
  left_endpoint_label: 0 - Least preferred
  right_endpoint_label: 100 - Most preferred
  midpoint_label: null

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
  setup_test_audio:
    configured_temporary_development_path: frontend/assets/audio/setup-test-development.mp3
    final_file: TBC
    progression_if_file_missing: blocked
  playback_event_recording: TBC
  experimental_audio_format: WAV, 44.1 kHz, stereo, 24-bit PCM
  experimental_loudness_preparation: -20.8 LUFS according to final stimulus report
  experimental_normalisation_policy: final experimental stimuli already prepared

audio_screening:
  configuration_file: frontend/config/screening.json
  mode: development
  production_ready: false
  current_placeholder_structure: three-item Version A/B/C matching task
  item_count: 3
  temporary_audio_directory: frontend/assets/audio/screening-development/
  temporary_audio_source: duplicated DU-H.mp3 assets
  required_audio_choices_per_item:
    - X
    - A
    - B
  answer_options:
    - A
    - B
  temporary_minimum_score: 2
  temporary_maximum_attempts: 2
  temporary_retry_enabled: true
  temporary_failure_behaviour: development message only
  final_stimuli: outputs/final_stimuli/metadata/frontend_stimulus_manifest.json
  correct_answers: TBC
  minimum_score: TBC
  maximum_attempts: TBC
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
  practice_scenario_id: practice_scenario_development
  practice_excerpt_id: practice_excerpt_development
  temporary_audio_source: frontend/assets/audio/setup-test-development.mp3
  version_labels:
    - Version A
    - Version B
    - Version C
  rating_scale:
    minimum: 0
    maximum: 100
    step: 1
    untouched_slider_counts_as_complete: false
  comments_required: true
  whitespace_only_comments_allowed: false
  meaningful_response_threshold: TBC
  audio_playback_required_for_completion: false
  audio_playback_requirement_final: TBC
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
    - id: nationality
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
    - id: task_difficulty
      response_options: TBC
    - id: prior_excerpt_familiarity
      response_options: TBC
    - id: headphones_or_earphones_used
      response_options: TBC
    - id: completion_location_or_environment
      response_options: TBC
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
    current_path: frontend/assets/audio/experimental/
    status: final_experimental_stimuli_integrated
    replacement_required_before_pilot: false
    manifest: docs/final-stimuli-manifest.md
```

## Unresolved values

- Verified Participant Information Sheet transcription: TBC.
- Verified consent transcription: TBC.
- Eligibility criteria and listening setup wording: TBC.
- Final setup test audio file: TBC.
- Audio screening instructions, stimuli, correct answers, pass rule, retry behaviour, and exclusion procedure: TBC.
- Final practice scenario wording: TBC.
- Final practice excerpt and audio: TBC.
- Practice-specific audio playback requirement: TBC.
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
