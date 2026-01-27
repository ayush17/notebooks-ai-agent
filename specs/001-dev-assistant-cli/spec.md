# Feature Specification: Developer Assistant CLI

**Feature Branch**: `001-dev-assistant-cli`
**Created**: 2026-01-26
**Status**: Draft
**Input**: Agentic Assistant for Developers - Python CLI application with multi-context aggregation, Unified Morning Brief, meeting scheduling, dynamic personal assistant with learning preferences, stakeholder inquiry, pair programming/mentoring, quarterly connection notes, EC2 sandbox toggle, and auto-response capabilities with human-in-the-loop.

## Overview

A Python CLI application that serves as an intelligent developer assistant, aggregating context from multiple sources (Gmail, Slack, JIRA, GitHub/GitLab, AI Workspace, Org Charts/LDAP) to provide actionable insights and automate routine tasks. The CLI-first architecture enables future UI extensions (Slack bot, web app, etc.) through a shared service layer.

## Clarifications

### Session 2026-01-27

- Q: Credential storage method? → A: Unencrypted local config file (development only, with warning displayed to user)
- Q: Context cache TTL? → A: 15 minutes - balanced freshness and API efficiency
- Q: AI model provider for MVP? → A: GCP Vertex AI (Gemini models)
- Q: Minimum viable context sources for MVP? → A: Gmail, Slack, JIRA, and GitHub (communication + developer workflow)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Morning Brief (Priority: P1)

As a developer starting my workday, I want to receive a consolidated summary of all relevant updates across my communication and work tracking tools so I can quickly understand what needs my attention today.

**Why this priority**: This is the core value proposition - aggregating context from multiple sources into a single actionable summary. It demonstrates the multi-source integration and AI summarization capabilities.

**Independent Test**: Can be fully tested by running a single CLI command that fetches and summarizes data from configured sources, delivering immediate value as a standalone feature.

**Acceptance Scenarios**:

1. **Given** the user has configured at least one context source (e.g., Gmail), **When** they run the morning brief command, **Then** they receive a formatted summary of relevant items from that source within 30 seconds.

2. **Given** the user has configured multiple context sources, **When** they run the morning brief command, **Then** all sources are queried and results are merged into a prioritized, coherent summary.

3. **Given** a context source is temporarily unavailable, **When** the morning brief runs, **Then** the system gracefully degrades by showing available data and noting which sources failed.

4. **Given** the user has previously indicated preferences (e.g., "prioritize security alerts"), **When** generating the brief, **Then** matching items appear at the top of the summary.

---

### User Story 2 - Context Source Configuration (Priority: P1)

As a developer, I want to configure which context sources to connect (Gmail, Slack, JIRA, GitHub, etc.) so the assistant can access my relevant data.

**Why this priority**: Required foundation for all other features - without context source configuration, no aggregation is possible.

**Independent Test**: Can be fully tested by running configuration commands and verifying credentials are stored securely and connections can be validated.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **When** the user runs the configure command for a source, **Then** they are guided through OAuth or API key setup with clear instructions.

2. **Given** valid credentials are provided, **When** configuration completes, **Then** a connection test is performed and success/failure is clearly reported.

3. **Given** credentials are stored, **When** the user lists configured sources, **Then** they see which sources are active without exposing sensitive credential data.

4. **Given** a user wants to remove a source, **When** they run the remove command, **Then** stored credentials are securely deleted and the source is removed from aggregation.

---

### User Story 3 - Stakeholder/SME Inquiry (Priority: P2)

As a developer needing expertise, I want to ask questions and have the assistant identify relevant stakeholders or subject matter experts from organizational data so I can get help efficiently.

**Why this priority**: Leverages the context aggregation to provide immediate value for common developer need - finding the right person to ask.

**Independent Test**: Can be tested by querying for expertise and verifying the system returns relevant people based on configured org data sources.

**Acceptance Scenarios**:

1. **Given** LDAP/org chart data is configured, **When** the user asks "who knows about payment processing?", **Then** the system returns a ranked list of people with relevant expertise or project involvement.

2. **Given** the query matches multiple potential experts, **When** results are displayed, **Then** each person includes context (role, team, recent relevant activity) to help the user choose.

3. **Given** no organizational data is configured, **When** the user runs an inquiry, **Then** they receive a helpful message explaining which sources to configure.

---

### User Story 4 - Preference Learning (Priority: P2)

As a developer using the assistant regularly, I want it to learn my preferences over time so recommendations become more relevant without manual configuration.

**Why this priority**: Differentiates from static tools by providing personalized, improving experience - but requires baseline functionality first.

**Independent Test**: Can be tested by providing explicit feedback on results and verifying subsequent queries reflect learned preferences.

**Acceptance Scenarios**:

1. **Given** the user marks an item as "important" or "not relevant", **When** similar items appear in future briefs, **Then** they are ranked higher or lower accordingly.

2. **Given** accumulated preference data exists, **When** the user views their preference profile, **Then** they can see and modify learned preferences.

3. **Given** the user wants to reset preferences, **When** they run the reset command, **Then** all learned preferences are cleared and the system returns to defaults.

---

### User Story 5 - EC2 Sandbox Toggle (Priority: P3)

As a developer with cloud development environments, I want to start/stop my EC2 sandbox instances from the CLI so I can manage costs without leaving my terminal.

**Why this priority**: Useful utility but lower priority than core context aggregation features. Simple integration that provides immediate value.

**Independent Test**: Can be tested by toggling instance state and verifying the change in AWS console.

**Acceptance Scenarios**:

1. **Given** AWS credentials are configured, **When** the user runs the sandbox status command, **Then** they see the current state of their designated sandbox instances.

2. **Given** a sandbox instance is stopped, **When** the user runs the start command, **Then** the instance starts and the user is notified when it's ready.

3. **Given** a sandbox instance is running, **When** the user runs the stop command, **Then** the instance stops and the user receives confirmation.

---

### User Story 6 - Auto-Response Draft (Priority: P3)

As a developer receiving routine inquiries, I want the assistant to draft responses to emails/Slack messages that I can review and approve before sending (human-in-the-loop).

**Why this priority**: Advanced feature requiring robust context understanding and user trust - better to nail fundamentals first.

**Independent Test**: Can be tested by providing a message context and verifying a sensible draft is generated for user review.

**Acceptance Scenarios**:

1. **Given** a message context is provided, **When** the user requests a draft response, **Then** a contextually appropriate draft is generated and displayed.

2. **Given** a draft is generated, **When** the user reviews it, **Then** they can approve, edit, or reject before any action is taken.

3. **Given** the user approves a draft, **When** confirmation is received, **Then** the response is sent through the appropriate channel and logged.

4. **Given** the user rejects a draft, **When** rejection is confirmed, **Then** no message is sent and the user can optionally provide feedback for improvement.

---

### User Story 7 - Quarterly Connection Notes (Priority: P3)

As a developer preparing for performance discussions, I want to generate notes summarizing my contributions and task completions for a given period so I have data for quarterly reviews.

**Why this priority**: Valuable but periodic use - core daily functionality takes precedence.

**Independent Test**: Can be tested by generating a report for a date range and verifying it includes relevant completed work from configured sources.

**Acceptance Scenarios**:

1. **Given** work tracking sources (JIRA, GitHub) are configured, **When** the user requests quarterly notes for a date range, **Then** a summary of completed items is generated with key metrics.

2. **Given** the generated notes are displayed, **When** the user reviews them, **Then** they can export to common formats (markdown, text).

---

### Edge Cases

- What happens when OAuth tokens expire mid-session? System should detect expiration, notify user, and guide re-authentication without losing work context.
- How does the system handle rate limiting from external APIs? Implement exponential backoff and inform user of delays.
- What happens when the AI model service is unavailable? Fall back to raw data presentation with clear messaging about reduced functionality.
- How does the system handle conflicting information from multiple sources? Present both with source attribution, let user determine ground truth.
- What happens when the local workspace directory is inaccessible? Fail gracefully with clear error message about storage requirements.

## Requirements *(mandatory)*

### Functional Requirements

#### Core Infrastructure
- **FR-001**: System MUST provide a CLI interface using a command/subcommand structure (e.g., `devassist brief`, `devassist config add gmail`)
- **FR-002**: System MUST store all working data in a configurable local workspace directory
- **FR-003**: System MUST support configuration via environment variables, config files, and CLI flags (in order of precedence)
- **FR-004**: System MUST store credentials in a local config file (unencrypted for development) and display a security warning on startup
- **FR-005**: System MUST provide clear, actionable error messages for all failure modes

#### Context Integration (MVP: Gmail, Slack, JIRA, GitHub)
- **FR-006**: System MUST support pluggable context source adapters with a consistent interface
- **FR-007**: System MUST support Gmail context integration via OAuth2 *(MVP)*
- **FR-008**: System MUST support Slack context integration via OAuth2 or bot token *(MVP)*
- **FR-009**: System MUST support JIRA context integration via API token *(MVP)*
- **FR-010**: System MUST support GitHub context integration via personal access tokens *(MVP)*
- **FR-010a**: System MAY support GitLab context integration via personal access tokens *(post-MVP)*
- **FR-011**: System MAY support LDAP/org chart data integration for stakeholder lookup *(post-MVP)*
- **FR-012**: System MUST cache fetched context data locally with a 15-minute TTL to reduce API calls and enable offline reference

#### AI Integration
- **FR-013**: System MUST integrate with GCP Vertex AI (Gemini models) for summarization and inference
- **FR-014**: System MUST optimize context sent to AI models to stay within token limits
- **FR-015**: System MUST support configurable AI model selection within the Vertex AI Gemini family
- **FR-016**: System MUST persist conversation memory across sessions for continuity

#### Preference Learning
- **FR-017**: System MUST capture explicit user feedback (thumbs up/down, priority flags)
- **FR-018**: System MUST apply learned preferences to future result ranking
- **FR-019**: Users MUST be able to view, modify, and reset their preference profile

#### Utilities
- **FR-020**: System MUST support AWS EC2 instance state management (start/stop/status) for designated sandbox instances
- **FR-021**: System MUST generate human-in-the-loop draft responses with explicit approval workflow
- **FR-022**: System MUST generate periodic summary reports (quarterly notes) from aggregated work data

#### Architecture
- **FR-023**: System MUST separate CLI interface from core service logic to enable future UI additions
- **FR-024**: System MUST support running as a containerized application with mounted workspace directory
- **FR-025**: System MUST provide an evaluation harness for testing tool outcomes and scoring results

#### Development Process (TDD)
- **FR-026**: All feature implementation MUST follow TDD: write failing test first, implement minimal code to pass, then refactor
- **FR-027**: No production code may be written without a corresponding failing test
- **FR-028**: Code coverage MUST maintain minimum 80% for core/ and adapters/ modules

### Key Entities

- **ContextSource**: Represents a configured integration (type, credentials, connection state, last sync time)
- **ContextItem**: A single piece of information from a source (source, timestamp, content, metadata, relevance score)
- **UserPreference**: A learned or explicit preference (category, weight, source of learning)
- **Brief**: A generated summary (timestamp, included sources, items, AI-generated narrative)
- **DraftResponse**: A pending auto-response (original message context, generated draft, approval status, final action)
- **SandboxInstance**: An EC2 instance designation (instance ID, name, current state, last toggled)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can generate a morning brief aggregating 3+ sources in under 60 seconds
- **SC-002**: Users can configure a new context source in under 5 minutes with provided credentials
- **SC-003**: 80% of generated morning briefs are rated "useful" or better by users
- **SC-004**: Stakeholder inquiries return relevant results for 90% of queries when org data is available
- **SC-005**: Preference learning demonstrably improves result relevance after 10+ feedback interactions
- **SC-006**: EC2 sandbox toggle completes within 10 seconds of command execution
- **SC-007**: Draft responses require fewer than 2 edits on average before user approval
- **SC-008**: Quarterly notes generation completes in under 2 minutes for a 3-month period
- **SC-009**: System gracefully handles source failures without crashing, maintaining partial functionality
- **SC-010**: CLI commands provide helpful output for `--help` flags and invalid inputs

## Assumptions

- Users have appropriate access credentials for the services they want to integrate
- Users have reliable internet connectivity for API calls to external services
- The AI model service (GCP Vertex AI) is available and the user has access credentials
- Users are comfortable with CLI-based interfaces for the initial release
- OAuth flows can be completed via browser redirect for services requiring it
- Local storage is available and has sufficient space for caching and workspace data
- AWS credentials for EC2 management are pre-configured in the user's environment or provided during setup

## Out of Scope

- Web UI or graphical interface (CLI-first for this release)
- Slack bot interface (future UI layer addition)
- Real-time notifications or push updates (pull-based for CLI)
- Multi-user or team-wide deployments (single-user focus)
- Meeting scheduling automation (reserved for future iteration)
- Pair programming / AI mentor features (reserved for future iteration)
- Custom slash commands for AI workspaces (reserved for future iteration)
