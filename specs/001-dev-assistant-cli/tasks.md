# Tasks: Developer Assistant CLI

**Input**: Design documents from `/specs/001-dev-assistant-cli/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED per FR-026 to FR-028 (TDD mandatory, 80% coverage for core/ and adapters/)

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- Source: `src/devassist/`
- Tests: `tests/unit/`, `tests/integration/`, `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure per plan.md layout
- [ ] T002 Initialize Python project with pyproject.toml (Python 3.11+, dependencies: typer, httpx, pydantic, rich, google-cloud-aiplatform)
- [ ] T003 [P] Configure ruff for linting and formatting in pyproject.toml
- [ ] T004 [P] Configure pytest with pytest-asyncio in pyproject.toml
- [ ] T005 [P] Create README.md with project overview and setup instructions
- [ ] T006 [P] Create .gitignore for Python project
- [ ] T007 Create src/devassist/__init__.py with version and package metadata

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase (TDD - Write First, Must Fail)

- [ ] T008 [P] Write failing test for ConfigManager in tests/unit/test_config_manager.py
- [ ] T009 [P] Write failing test for CacheManager in tests/unit/test_cache_manager.py
- [ ] T010 [P] Write failing contract test for ContextSourceAdapter in tests/contract/test_context_source_contract.py

### Core Models

- [ ] T011 [P] Create SourceType enum in src/devassist/models/context.py
- [ ] T012 [P] Create ConnectionStatus enum in src/devassist/models/context.py
- [ ] T013 [P] Create ContextSource model in src/devassist/models/context.py
- [ ] T014 [P] Create ContextItem model in src/devassist/models/context.py
- [ ] T015 [P] Create configuration models in src/devassist/models/config.py

### Core Infrastructure

- [ ] T016 Implement ConfigManager in src/devassist/core/config_manager.py (load/save YAML, env var precedence)
- [ ] T017 Implement CacheManager in src/devassist/core/cache_manager.py (15-min TTL, JSON file storage)
- [ ] T018 Create abstract ContextSourceAdapter base class in src/devassist/adapters/base.py
- [ ] T019 [P] Create error classes in src/devassist/adapters/errors.py (AuthenticationError, SourceUnavailableError, RateLimitError)
- [ ] T020 Implement workspace directory initialization in src/devassist/core/config_manager.py

### CLI Foundation

- [ ] T021 Create Typer app entrypoint in src/devassist/cli/main.py
- [ ] T022 Add --version and --help commands in src/devassist/cli/main.py
- [ ] T023 Add security warning display on startup (per FR-004) in src/devassist/cli/main.py
- [ ] T024 Configure Rich console for formatted output in src/devassist/cli/main.py

**Checkpoint**: Foundation ready - all tests from T008-T010 must PASS. User story implementation can now begin.

---

## Phase 3: User Story 2 - Context Source Configuration (Priority: P1) - PREREQUISITE

**Goal**: Enable users to configure context sources (Gmail, Slack, JIRA, GitHub) - Required before US1

**Independent Test**: Run `devassist config add gmail` and verify OAuth flow completes, credentials stored

**Note**: US2 is implemented before US1 because Morning Brief depends on configured sources

### Tests for User Story 2 (TDD - Write First, Must Fail)

- [ ] T025 [P] [US2] Write failing integration test for Gmail OAuth flow in tests/integration/test_gmail_adapter.py
- [ ] T026 [P] [US2] Write failing integration test for Slack auth in tests/integration/test_slack_adapter.py
- [ ] T027 [P] [US2] Write failing integration test for JIRA auth in tests/integration/test_jira_adapter.py
- [ ] T028 [P] [US2] Write failing integration test for GitHub auth in tests/integration/test_github_adapter.py

### Implementation for User Story 2

- [ ] T029 [P] [US2] Implement GmailAdapter with OAuth2 flow in src/devassist/adapters/gmail.py
- [ ] T030 [P] [US2] Implement SlackAdapter with bot token auth in src/devassist/adapters/slack.py
- [ ] T031 [P] [US2] Implement JiraAdapter with API token auth in src/devassist/adapters/jira.py
- [ ] T032 [P] [US2] Implement GitHubAdapter with PAT auth in src/devassist/adapters/github.py
- [ ] T033 [US2] Implement config add command in src/devassist/cli/config.py (guided setup per source)
- [ ] T034 [US2] Implement config list command in src/devassist/cli/config.py (show sources without exposing secrets)
- [ ] T035 [US2] Implement config remove command in src/devassist/cli/config.py (delete credentials)
- [ ] T036 [US2] Implement config test command in src/devassist/cli/config.py (validate connections)
- [ ] T037 [US2] Add adapter factory for source type lookup in src/devassist/adapters/__init__.py

**Checkpoint**: User Story 2 complete. Verify: `devassist config add gmail`, `devassist config list`, `devassist config test`

---

## Phase 4: User Story 1 - Unified Morning Brief (Priority: P1) - MVP

**Goal**: Generate consolidated summary from all configured sources using AI

**Independent Test**: Run `devassist brief` and receive formatted summary within 60 seconds

### Tests for User Story 1 (TDD - Write First, Must Fail)

- [ ] T038 [P] [US1] Write failing test for ContextAggregator in tests/unit/test_aggregator.py
- [ ] T039 [P] [US1] Write failing test for RelevanceRanker in tests/unit/test_ranker.py
- [ ] T040 [P] [US1] Write failing test for BriefGenerator in tests/unit/test_brief_generator.py
- [ ] T041 [P] [US1] Write failing test for VertexAIClient in tests/unit/test_vertex_client.py

### Models for User Story 1

- [ ] T042 [P] [US1] Create Brief model in src/devassist/models/brief.py
- [ ] T043 [P] [US1] Create BriefItem model in src/devassist/models/brief.py
- [ ] T044 [P] [US1] Create BriefSummary model for AI response in src/devassist/models/brief.py

### AI Integration

- [ ] T045 [US1] Implement VertexAIClient in src/devassist/ai/vertex_client.py (Gemini 1.5 Flash)
- [ ] T046 [US1] Create summarization prompt template in src/devassist/ai/prompts.py
- [ ] T047 [US1] Add context optimization logic in src/devassist/ai/vertex_client.py (token budget management)

### Core Services

- [ ] T048 [US1] Implement ContextAggregator in src/devassist/core/aggregator.py (parallel fetch with asyncio.gather)
- [ ] T049 [US1] Implement RelevanceRanker in src/devassist/core/ranker.py (score by recency, sender, keywords)
- [ ] T050 [US1] Implement BriefGenerator in src/devassist/core/brief_generator.py (orchestrate aggregator + ranker + AI)
- [ ] T051 [US1] Add graceful degradation handling in src/devassist/core/aggregator.py (continue on source failure)

### CLI for User Story 1

- [ ] T052 [US1] Implement brief command in src/devassist/cli/brief.py
- [ ] T053 [US1] Add --sources flag to filter sources in src/devassist/cli/brief.py
- [ ] T054 [US1] Add --refresh flag to bypass cache in src/devassist/cli/brief.py
- [ ] T055 [US1] Add --json flag for machine-readable output in src/devassist/cli/brief.py
- [ ] T056 [US1] Create Rich formatted brief display in src/devassist/cli/brief.py

**Checkpoint**: MVP Complete. Verify: `devassist brief` generates summary from configured sources within 60 seconds.

---

## Phase 5: User Story 4 - Preference Learning (Priority: P2)

**Goal**: Learn user preferences over time to improve relevance ranking

**Independent Test**: Mark item as important, verify future briefs prioritize similar items

### Tests for User Story 4 (TDD - Write First, Must Fail)

- [ ] T057 [P] [US4] Write failing test for PreferenceStore in tests/unit/test_preference_store.py
- [ ] T058 [P] [US4] Write failing test for FeedbackHandler in tests/unit/test_feedback_handler.py
- [ ] T059 [P] [US4] Write failing test for PreferenceService in tests/unit/test_preference_service.py

### Models for User Story 4

- [ ] T060 [P] [US4] Create UserPreference model in src/devassist/models/preferences.py
- [ ] T061 [P] [US4] Create Feedback model in src/devassist/models/preferences.py

### Implementation for User Story 4

- [ ] T062 [US4] Implement PreferenceStore in src/devassist/preferences/preference_store.py (CRUD operations)
- [ ] T063 [US4] Implement FeedbackHandler in src/devassist/preferences/feedback_handler.py (capture thumbs up/down)
- [ ] T064 [US4] Implement PreferenceService in src/devassist/preferences/preference_service.py (apply to ranking)
- [ ] T065 [US4] Integrate PreferenceService with RelevanceRanker in src/devassist/core/ranker.py
- [ ] T066 [US4] Implement prefs add command in src/devassist/cli/prefs.py (explicit preference)
- [ ] T067 [US4] Implement prefs list command in src/devassist/cli/prefs.py
- [ ] T068 [US4] Implement prefs reset command in src/devassist/cli/prefs.py

**Checkpoint**: User Story 4 complete. Verify: `devassist prefs add --keyword "urgent"`, then check brief prioritization.

---

## Phase 6: User Story 3 - Stakeholder/SME Inquiry (Priority: P2)

**Goal**: Find subject matter experts based on organizational data

**Independent Test**: Run `devassist ask "who knows about payments?"` and get ranked expert list

**Note**: Post-MVP, depends on LDAP integration (FR-011 marked post-MVP)

### Tests for User Story 3 (TDD - Write First, Must Fail)

- [ ] T069 [P] [US3] Write failing test for ExpertFinder in tests/unit/test_expert_finder.py

### Implementation for User Story 3

- [ ] T070 [US3] Create ExpertFinder service in src/devassist/core/expert_finder.py
- [ ] T071 [US3] Implement expert matching from GitHub/JIRA activity in src/devassist/core/expert_finder.py
- [ ] T072 [US3] Implement ask command in src/devassist/cli/ask.py
- [ ] T073 [US3] Add Rich formatted expert list display in src/devassist/cli/ask.py
- [ ] T074 [US3] Add graceful fallback when org data unavailable in src/devassist/core/expert_finder.py

**Checkpoint**: User Story 3 complete. Verify: `devassist ask "who knows about API design?"`

---

## Phase 7: User Story 5 - EC2 Sandbox Toggle (Priority: P3)

**Goal**: Start/stop EC2 sandbox instances from CLI

**Independent Test**: Run `devassist sandbox status` and see instance states

### Tests for User Story 5 (TDD - Write First, Must Fail)

- [ ] T075 [P] [US5] Write failing test for SandboxManager in tests/unit/test_sandbox_manager.py

### Models for User Story 5

- [ ] T076 [P] [US5] Create SandboxInstance model in src/devassist/models/sandbox.py
- [ ] T077 [P] [US5] Create InstanceState enum in src/devassist/models/sandbox.py

### Implementation for User Story 5

- [ ] T078 [US5] Implement SandboxManager in src/devassist/core/sandbox_manager.py (boto3 integration)
- [ ] T079 [US5] Implement sandbox add command in src/devassist/cli/sandbox.py
- [ ] T080 [US5] Implement sandbox status command in src/devassist/cli/sandbox.py
- [ ] T081 [US5] Implement sandbox start command in src/devassist/cli/sandbox.py
- [ ] T082 [US5] Implement sandbox stop command in src/devassist/cli/sandbox.py

**Checkpoint**: User Story 5 complete. Verify: `devassist sandbox status`, `devassist sandbox start dev-box`

---

## Phase 8: User Story 6 - Auto-Response Draft (Priority: P3)

**Goal**: Generate draft responses with human-in-the-loop approval

**Independent Test**: Run `devassist draft` with message context and get editable draft

### Tests for User Story 6 (TDD - Write First, Must Fail)

- [ ] T083 [P] [US6] Write failing test for DraftGenerator in tests/unit/test_draft_generator.py

### Models for User Story 6

- [ ] T084 [P] [US6] Create DraftResponse model in src/devassist/models/draft.py
- [ ] T085 [P] [US6] Create DraftStatus enum in src/devassist/models/draft.py

### Implementation for User Story 6

- [ ] T086 [US6] Create response draft prompt template in src/devassist/ai/prompts.py
- [ ] T087 [US6] Implement DraftGenerator in src/devassist/core/draft_generator.py
- [ ] T088 [US6] Implement draft command with approval workflow in src/devassist/cli/draft.py
- [ ] T089 [US6] Add --approve and --reject flags in src/devassist/cli/draft.py
- [ ] T090 [US6] Implement send functionality for Gmail/Slack in src/devassist/core/draft_generator.py

**Checkpoint**: User Story 6 complete. Verify: Draft generation, approval workflow, and send.

---

## Phase 9: User Story 7 - Quarterly Connection Notes (Priority: P3)

**Goal**: Generate contribution summaries for quarterly reviews

**Independent Test**: Run `devassist notes --from 2026-01-01 --to 2026-03-31` and get formatted report

### Tests for User Story 7 (TDD - Write First, Must Fail)

- [ ] T091 [P] [US7] Write failing test for NotesGenerator in tests/unit/test_notes_generator.py

### Implementation for User Story 7

- [ ] T092 [US7] Implement NotesGenerator in src/devassist/core/notes_generator.py
- [ ] T093 [US7] Add JIRA completed issues aggregation in src/devassist/core/notes_generator.py
- [ ] T094 [US7] Add GitHub PRs/commits aggregation in src/devassist/core/notes_generator.py
- [ ] T095 [US7] Implement notes command in src/devassist/cli/notes.py
- [ ] T096 [US7] Add --format flag (markdown, text) in src/devassist/cli/notes.py
- [ ] T097 [US7] Add export to file functionality in src/devassist/cli/notes.py

**Checkpoint**: User Story 7 complete. Verify: `devassist notes --from 2026-01-01 --to 2026-03-31`

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T098 [P] Create Containerfile with entrypoint per FR-024
- [ ] T099 [P] Add evaluation harness skeleton per FR-025 in tests/evaluation/
- [ ] T100 [P] Update README.md with full CLI documentation
- [ ] T101 [P] Add quickstart.md validation test in tests/integration/test_quickstart.py
- [ ] T102 Run coverage report and ensure 80% for core/ and adapters/ per FR-028
- [ ] T103 Security review: ensure no secrets in logs or error messages
- [ ] T104 Performance validation: verify brief generation < 60 seconds (SC-001)
- [ ] T105 Add --no-ai fallback mode for brief command (edge case: AI unavailable)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────────────────────┐
                                                                     │
Phase 2 (Foundational) ──────────────────────────────────────────────┤
                                                                     │
    ┌────────────────────────────────────────────────────────────────┘
    │
    ▼
Phase 3 (US2: Config) ──► Phase 4 (US1: Brief) ──► [MVP COMPLETE]
                              │
    ┌─────────────────────────┴─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
Phase 5 (US4)            Phase 6 (US3)            Phase 7-9 (US5-7)
Preferences              SME Inquiry              Utilities (P3)
    │                         │                         │
    └─────────────────────────┴─────────────────────────┘
                              │
                              ▼
                      Phase 10 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US2 (Config) | Phase 2 | - |
| US1 (Brief) | US2 | - |
| US4 (Preferences) | US1 | US3, US5, US6, US7 |
| US3 (SME Inquiry) | Phase 2 | US4, US5, US6, US7 |
| US5 (EC2 Sandbox) | Phase 2 | US3, US4, US6, US7 |
| US6 (Auto-Response) | US1 | US3, US4, US5, US7 |
| US7 (Quarterly Notes) | US2 | US3, US4, US5, US6 |

### Parallel Opportunities

Within each phase, tasks marked [P] can run simultaneously.

---

## Parallel Example: Phase 4 (User Story 1)

```bash
# Launch all US1 tests in parallel:
T038: test_aggregator.py
T039: test_ranker.py
T040: test_brief_generator.py
T041: test_vertex_client.py

# Launch all US1 models in parallel:
T042: Brief model
T043: BriefItem model
T044: BriefSummary model
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 2 (Config) - must have sources to query
4. Complete Phase 4: User Story 1 (Brief) - core value proposition
5. **STOP and VALIDATE**: Run `devassist config add gmail`, then `devassist brief`
6. Deploy/demo if ready - **This is your hackathon MVP!**

### Incremental Delivery

| Increment | Stories | Value Delivered |
|-----------|---------|-----------------|
| MVP | US2 + US1 | Configure sources, generate morning brief |
| +Personalization | +US4 | Preferences improve relevance |
| +Collaboration | +US3 | Find experts |
| +Utilities | +US5, US6, US7 | EC2 toggle, auto-response, quarterly notes |

### Hackathon Priority

For a hackathon, focus on:
1. **Phase 1-2**: Setup and Foundation (required)
2. **Phase 3-4**: US2 + US1 = Working demo of morning brief
3. Skip US3-US7 unless time permits

---

## Task Summary

| Phase | Story | Task Count | Parallel Tasks |
|-------|-------|------------|----------------|
| 1 | Setup | 7 | 4 |
| 2 | Foundational | 17 | 8 |
| 3 | US2 (Config) | 13 | 8 |
| 4 | US1 (Brief) | 19 | 8 |
| 5 | US4 (Preferences) | 12 | 5 |
| 6 | US3 (SME Inquiry) | 6 | 1 |
| 7 | US5 (EC2 Sandbox) | 8 | 3 |
| 8 | US6 (Auto-Response) | 8 | 3 |
| 9 | US7 (Quarterly Notes) | 7 | 1 |
| 10 | Polish | 8 | 4 |
| **Total** | | **105** | **45** |

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- TDD: All test tasks (T008-T010, T025-T028, T038-T041, etc.) MUST fail before implementation
- Per FR-028: Maintain 80% coverage for core/ and adapters/
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
