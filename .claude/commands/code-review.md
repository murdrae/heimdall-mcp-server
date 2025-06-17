# Code Review - Execute top to bottom

Use the following instructions from top to bottom to execute a Code Review.

## Create a TODO with EXACTLY these 6 Items

1. Analyze the Scope given
2. Find code changes within Scope
3. Find relevant Specification and Documentation
4. Compare code changes against Documentation and Requirements
5. Analyze possible differences
6. Provide PASS/FAIL verdict with details

Follow step by step and adhere closely to the following instructions for each step.

## DETAILS on every TODO item

### 1. Analyze the Scope given

check: <$ARGUMENTS>

If empty, use default, otherwise interpret <$ARGUMENTS> to identify the scope of the Review.

### 2. Find code changes within Scope

With the identified Scope use `git diff` (on default: `git diff HEAD~1` or `git diff dev`) to find code changes.

### 3. Find relevant Specifications and Documentation

- FIND the relevant document document in docs/ directory
- FIND and READ the corresponding Feature Description document in docs/feature_description. Mark **FAIL** if feature description is missing.
- INTERPRET project documentation, Feature Description and Test Plan. FIND ALL related REQUIREMENTS there.

### 4. Compare code changes against Documentation and Requirements

- Use DEEP THINKING to compare changes against found Requirements and Specs.
- Compare especially these things:
  - **Data models / schemas** — fields, types, constraints, relationships.
  - **APIs / interfaces** — endpoints, params, return shapes, status codes, errors.
  - **Config / environment** — keys, defaults, required/optional.
  - **Behaviour** — business rules, side-effects, error handling.
  - **Quality** — naming, formatting, tests, linter status.
  - **Test Implementation** — verify all tests specified in the Test Plan are implemented.
  - **Test Results** — verify all implemented tests are passing.

**IMPORTANT**:

- Deviations from the Specs are NOT allowed. Not even small ones. Be very picky here!
- If in doubt call a **FAIL** and ask the User.
- Zero tolerance on not following the Specs and Documentation.

### 5. Analyze the differences and Peer Review with O3

- Analyze any difference found
- Give every issue a Severity Score
- Severity ranges from 1 (low) to 10 (high)
- Remember List of issues and Scores for output
- PEER review with O3 to ensure code in review follows entreprise grade level.
- Check specifically for:
  - Failing tests (Severity 9)
  - Feature implementation not matching Feature Description (Severity 10)

### 6. Provide PASS/FAIL verdict with details

- Call a **FAIL** on any differences found.
  - Zero Tolerance - even on well meant additions.
  - Leave it on the user to decide if small changes are allowed.
- Only **PASS** if no discrepancy appeared.
- **ALWAYS FAIL** if any required tests are missing or failing.

#### IMPORTANT: Output Format

In this very particular Order:

- Result: **FAIL/PASS** Your final decision on if it's a PASS or a FAIL.
- **Scope:** Inform the user about the review scope.
- **Findings** Detailed list with all Issues found and Severity Score.
- **Summary** Short summary on what is wrong or not.
- **Recommendation** Your personal recommendation on further steps.


### Finish work

In case of **PASS**, wait for the user to approve your veredict. If the user approves your veredict:

- ADD the summary of your veredict to the progress tracking document in docs/progress/ referent to the review.
- COMMIT the file with your veredict - never mention claude code or anthropic.