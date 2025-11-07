# Style Guide

This guide defines the coding conventions for the Life Dashboard project. All contributors—including automated tools—must follow these rules. When in doubt, prefer clarity and documentation over cleverness.

---

## 1. General Principles

- **Do not delete existing comments.** If a comment is outdated, update it instead of removing it.
- **Document intent.** Add short comments explaining *why* when code is non-obvious (complex business logic, tricky math, unusual workarounds).
- **Keep folder documentation current.** Every change that adds/moves/removes files must update the appropriate `{folder}-readme.md`.
- **One responsibility per module.** Avoid files that mix unrelated concerns.
- **Tests and manual verification must be recorded** (see CONTRIBUTING.md).

---

## 2. Backend (Python / FastAPI)

### Naming & Structure
- Follow PEP 8:
  - Modules and packages: `snake_case`.
  - Classes: `PascalCase`.
  - Functions & variables: `snake_case`.
  - Constants: `UPPER_SNAKE`.
- Keep data access logic in `db/repositories/`. Services orchestrate repositories and clients.
- Place integration code (Garmin, Vertex, etc.) in `app/clients/` modules.

### Async & I/O
- Prefer `async`/`await` for I/O. Avoid blocking calls (e.g., `time.sleep`) inside async functions.
- Wrap third-party API calls in try/except and log failures with context.

### Logging & Errors
- Use the project logger (`loguru.logger`). Include identifiers (user id, dates, etc.) in log messages when helpful.
- Re-raise exceptions only after adding informative context.

### Documentation
- Public functions and classes require docstrings summarizing purpose, parameters, and return values.
- When adding new SQLAlchemy models or migrations, update the relevant `{folder}-readme.md` with schema changes.

---

## 3. Frontend (React / TypeScript)

### Components & Hooks
- Use functional components with hooks.
- Naming:
  - Components: `PascalCase`.
  - Hooks: `useExample`.
  - Helpers/constants: `camelCase` / `UPPER_SNAKE` as appropriate.
- Co-locate component-specific styles alongside the component unless globally shared.
- When creating a new component folder, add/update the folder-specific readme (e.g., `components-readme.md`) describing the component’s purpose and props.

### Async & Data Fetching
- Wrap data fetching in hooks under `hooks/`.
- Surface loading and error states in UI components.
- Catch and handle promise rejections; log errors and show user-friendly messages where appropriate.

### Comments & Docs
- Briefly explain non-trivial effects, memoization, or data transformations (what side-effect triggers? why memoization needed?).
- Update the folder readme tables to reflect new components/services.

---

## 4. Monet Theming & Textures

### Theme Foundations
- Always use `ThemeProvider` from `frontend/src/theme/ThemeProvider.tsx`.
- Do not hardcode colors. Pull palette values from `frontend/src/theme/monetTheme.ts`.
- Components should rely on `theme.colors` or CSS variables defined in `GlobalStyle`, never raw hex values (unless updating the palette itself).

### Texture Usage
- All textures reside in `frontend/src/assets/textures/`. Each texture should have light and dark variants (`*_light.png`, `*_dark.png`) unless truly universal.
- Import textures in code (e.g., `import paperFiberLight from '../../assets/textures/paper_fiber_light.png';`). Do **not** reference `/assets/...` paths directly; rely on bundler-managed URLs.
- Backgrounds should prefer layering existing textures. Before introducing a new texture:
  - Add it under `assets/textures/`.
  - Document its purpose and usage in `assets/textures/textures-readme.md` (or equivalent).
  - Update the theming design notes describing why the new texture is necessary.
- Shared surfaces (cards, layouts, backgrounds) must use the existing textured components. Do not reintroduce one-off gradients without owner approval.

### Light/Dark Mode
- When implementing new UI surfaces, ensure both light and dark mode assets are handled via theme mode detection (no reliance on media queries alone).
- Update the design notes when adding or altering textures/colors.

---

## 5. Documentation & Folder Readmes

- Every folder touched by a change must have a `{folder}-readme.md`:
  - Folder purpose.
  - Table mapping files/components to responsibilities.
- When moving or deleting files, update the table accordingly.

---

## 6. Testing & Verification

- Record manual or automated tests in design notes and PR descriptions.
- If no automated tests exist, explain how the change was manually verified.
- Do not delete existing tests unless replacing them with equivalents.

---

Adhering to this guide keeps the Monet-inspired experience consistent and the codebase maintainable. When exceptional circumstances require breaking a rule, document the rationale in design notes and obtain approval from the repository owner first.
