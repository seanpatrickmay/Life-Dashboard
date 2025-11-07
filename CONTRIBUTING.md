# Contributing Guide

This document describes how changes are proposed, implemented, and reviewed. All contributors—including automated tools—must read and follow these instructions.

---

## 1. Collaboration Workflow

1. **Clarify scope**
   - Discuss the requested change with the repository owner until goals, acceptance criteria, and risks are understood.
   - Ask questions early; do not assume requirements.

2. **Obtain explicit approval**
   - Wait for a clear “Approved” response before editing code or documentation.

3. **Implement**
   - Follow the Style Guide (`STYLE_GUIDE.md`).
   - Ensure every directory touched has a `{folder}-readme.md` that documents the folder’s purpose and file inventory.
     - Create the readme if it does not exist.
     - Update the table whenever files are added, removed, or relocated.
   - Keep code commented where non-obvious.

4. **Test & document**
   - Run all relevant automated tests or manual verification.
   - Record the tests performed and outcomes in the pull request summary.

5. **Prepare the pull request**
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

## 6. Reminder for AI Contributors

Automated assistants (Codex, ChatGPT, etc.) must follow the same process:

- Seek clarification and approval before coding.
- Update folder readmes.
- Document tests in the PR.
- Do not publish code until the workflow above is satisfied.

Failure to follow this guide will result in the change being rejected. Thank you for helping maintain a clean, well-documented project.
