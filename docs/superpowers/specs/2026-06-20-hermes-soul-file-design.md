# Hermes Soul File Design

## Goal

Give the local Hermes web UI a persistent identity file that describes what kind
of agent it is, while keeping document-ingestion and latest-only search safety
rules intact.

## Design

The project ships a default soul file at `hermes_ui/soul.md`. The Hermes web UI
loads this file for every chat request and injects it before per-request routing
instructions. This makes the agent identity stable while still letting runtime
state decide whether a question should be answered generally, routed to selected
documents, or routed to the latest document snapshot.

The soul file is trusted local configuration, not user input. User messages and
document selections remain base64-encoded in the prompt and are still treated as
inert data.

## Configuration

`HERMES_SOUL_FILE` can override the bundled soul file. In Docker, the default is:

```text
/app/hermes_ui/soul.md
```

Operators can later mount a custom file and point `HERMES_SOUL_FILE` at it.

## Safety

The soul can shape tone, purpose, and operating principles. It must not weaken
document safety rules:

- never delete, clear, reset, or overwrite archived/indexed data;
- preserve old versions;
- search only the active latest-version snapshot;
- answer general questions normally when documents are empty or irrelevant.

