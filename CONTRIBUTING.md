# Contributing Guide

This document describes how changes are proposed, implemented, and reviewed. All contributors—including automated tools—must read and follow these instructions. These guidelines are optimized for Codex-style assistants, so start with the quick-reference material below before diving into the detailed sections.

---

## Quick Start for Codex Assistants

1. **Align on scope.** Confirm the persona, goal, and acceptance criteria with the repository owner; turn ambiguities into explicit questions.
2. **Capture user stories.** Draft them with the owner and keep them visible in the working ticket or PR description.
3. **Secure explicit approval.** Wait for a clear “Approved” response before changing files, and surface blockers immediately.
4. **Map impacted folders.** Ensure every touched directory has an up-to-date `{folder}-readme.md` documenting purpose and file inventory.
5. **Review required references.** Re-read `STYLE_GUIDE.md`, related folder readmes, and any linked decisions.
6. **Implement deliberately.** Comment non-obvious logic, keep commits scoped, and note any scope adjustments for re-approval.
7. **Test and document.** Run all relevant automated/manual tests, capture outcomes, and include them in the PR checklist.
8. **Prepare the PR.** Summarize changes, risks, approvals, and test evidence using the template below.

---

## Required Artifacts at a Glance

| Item | When Required | Notes / Template |
| --- | --- | --- |
| `STYLE_GUIDE.md` | Any code change | Follow naming, structure, and theming rules. |
| `{folder}-readme.md` | Every directory touched | Must exist and list purpose + file overview. See template below. |
| User stories | Before implementation | Persona, goal, and measurable acceptance criteria captured with the owner. |
| Explicit approval log | Before editing files | Keep the approval reference (comment/link) handy for the PR. |
| Tests & verification log | Whenever behavior may change | Document commands run and outcomes in the PR. |
| PR summary | Every pull request | Use the PR template below for consistency. |

---

## 1. Collaboration Workflow

1. **Clarify scope**
   - Discuss the requested change with the repository owner until goals, acceptance criteria, and risks are understood.
   - Ask questions early; do not assume requirements.

2. **Create user stories**
   - Partner with the repository owner (me) to outline one or more user stories that capture the persona, goal, and measurable acceptance criteria for the change.
   - Keep these stories visible (PR description, linked doc, or ticket) and update them if scope shifts.

3. **Obtain explicit approval**
   - Wait for a clear “Approved” response before editing code or documentation.

4. **Implement**
   - Follow the Style Guide (`STYLE_GUIDE.md`).
   - Ensure every directory touched has a `{folder}-readme.md` that documents the folder’s purpose and file inventory.
     - Create the readme if it does not exist.
     - Update the table whenever files are added, removed, or relocated.
   - Keep code commented where non-obvious.

5. **Test & document**
   - Run all relevant automated tests or manual verification.
   - Record the tests performed and outcomes in the pull request summary.

6. **Prepare the pull request**
   - Summarize changes, risks, and test results.
   - Reference any discussions or approvals.
   - Request approval from the repository owner (other approvals are advisory).

---

## 2. Folder Readmes

Each folder touched by a change must contain a `{folder}-readme.md` with:

| Section | Notes |
| --- | --- |
| **Purpose** | One or two sentences describing the folder’s responsibility. |
| **File overview** | Table listing files/modules/components and their roles. |

Readmes are informational only—do not store design discussions or planning notes inside them.

---

## 3. Communication Rules

- Surface blockers, questions, or assumptions immediately in the main discussion thread.
- Document major decisions in the PR or linked conversation.
- If scope changes mid-implementation, pause and get re-approval.

---

## 4. Coding & Review Checklist

Before requesting review, confirm:

- [ ] Scope clarified and approved by the repository owner.
- [ ] Style guide rules followed (naming, structure, theming, documentation).
- [ ] `{folder}-readme.md` files exist and accurately reflect current contents.
- [ ] Tests executed; results documented in the PR.
- [ ] PR summarizes changes, risks, tests, and references approvals.

---

## 5. Approval Authority

- The repository owner is the sole gatekeeper. No change is merged without their explicit sign-off, even if automated checks pass.

---

## 6. AI Contributor Checklist

1. Confirm you have the latest scope, user stories, and approvals in writing.
2. List every folder you will touch and verify the corresponding `{folder}-readme.md` exists (create/update if needed).
3. Re-read `STYLE_GUIDE.md` and any relevant design notes before editing.
4. Implement the change, keeping non-obvious decisions documented inline or in commit messages.
5. Run and record all relevant tests, including manual steps if automation is unavailable.
6. Populate the PR summary template with scope, risks, approvals, and test evidence before requesting review.

Failure to follow this guide will result in the change being rejected. Thank you for helping maintain a clean, well-documented project.

---

## 7. Templates & Examples

### Folder Readme Template

```markdown
# {folder}-readme

## Purpose
Briefly describe why this folder exists and what responsibilities it owns.

## File Overview
| File / Module | Description |
| --- | --- |
| example_file.ext | One-line description of the file’s role. |
| subfolder/ | Note notable subdirectories or groupings. |
```

### Pull Request Summary Template

```markdown
## Summary
- Short bullet list describing the change.
- Mention any scope decisions or trade-offs.

## Risks & Mitigations
- Note behavioural, performance, or rollout risks and how they are mitigated/tested.

## Approvals
- Link to explicit owner approval and any supporting discussions.

## Tests
- `command or manual step` — result
- Additional verification notes
```
