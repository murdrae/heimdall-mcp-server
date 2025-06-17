# Execute Feature Implementation Plan - Follow below instruction from top-down

Use the following instructions from top to bottom to implement a Letrado feature based on its Feature Description Plan and Test Plan.

## Create a TODO with EXACTLY these 7 Items

1. Check for existing implementation progress
2. Read general instructions and feature documentation
3. Understand Feature Description Plan
4. Implement the NEXT STEP of feature code changes
5. Track and document implementation progress

Follow step by step and adhere closely to the following instructions for each step.

## DETAILS on every TODO item

### 1. Check for existing implementation progress

- SEARCH for an existing progress file in docs/progress/ that matches the pattern PROGRESS_FEATURE_[FeatureName]_*.md
- IF FOUND, READ the progress file thoroughly to understand:
  - Current implementation status
  - Completed steps
  - In-progress steps
  - Known issues or questions
  - Next planned actions
- USE this information to resume implementation from the correct point
- IF NOT FOUND, you will need to start implementation from the beginning

### 2. Read general instructions and feature documentation

- READ CLAUDE.md for general project instructions and conventions
- FIND the Feature Description Plan in docs/feature_description/
- FIND the Test Plan in docs/test_plan/
- READ ALL documents referred in the Feature Description Plan
- READ relevant background documentation in docs/

### 3. Understand Feature Description Plan

- ANALYZE all sections of the Feature Description Plan
- NOTE the Feature Name and core requirements
- IDENTIFY affected files and components
- UNDERSTAND implementation steps and their sequence
- PAY ATTENTION to TypeScript models and interfaces
- COMPREHEND validation checkpoints and success criteria
- DISCUSS with O3 for better clarity of the points

### 4. Implement feature code changes

- FOLLOW implementation steps in the exact sequence provided
- IMPLEMENT ONLY the NEXT step in the feature plan
- ADHERE strictly to the Feature Description Plan
- MAINTAIN code style and patterns consistent with the existing codebase
- IMPLEMENT all TypeScript interfaces exactly as specified
- ADDRESS all validation points during implementation
- DO NOT add any unspecified code or features
- DISCUSS with O3 on what you implemented and use the feedback
- NOTIFY user of any ambiguities or conflicts found in the plan and WAIT FOR CLARIFICATION

### 5. Track and document implementation progress

- IF no progress file exists, CREATE a new progress tracking file in docs/progress/
- NAME the file: PROGRESS_FEATURE_[FeatureName]_[YYYYMMDD].md (where [FeatureName] is the feature name with spaces replaced by underscores and [YYYYMMDD] is the current date)
- UPDATE this file throughout the implementation process
- INCLUDE detailed progress status using the specified format
- MARK implementation steps with [IN PROGRESS] and [COMPLETED] markers
- DOCUMENT blockers, questions, and decisions made
- ENSURE the progress file is kept current with implementation status
- **COMMIT** every time you edit this document, you MUST git commit the work progress with a meaningful commit message.

## Progress Tracking Format

The progress file must follow this strict format:

```markdown
# Implementation Progress: [Feature Name]
Date: YYYY-MM-DD
Feature Description Plan: [link to feature description plan]
Test Plan: [link to test plan]

## Overall Progress
Implementation: [X]% complete
Tests: [Y]% complete
Files Modified: [count]

## Implementation Steps Status

### Feature Code
| Step | Status | File | Description |
|------|--------|------|-------------|
| 1. [Step name] | [COMPLETED/IN PROGRESS/TODO] | [file path] | [description] |
| ... | ... | ... | ... |

### Tests
| Test Type | Status | File | Description |
|-----------|--------|------|-------------|
| Unit | [COMPLETED/IN PROGRESS/TODO] | [file path] | [description] |
| ... | ... | ... | ... |

## Current Focus
[Description of what is currently being implemented]

## Completed Items
- [Item 1]
- [Item 2]
- ...

## Next Steps
- [Next step 1]
- [Next step 2]
- ...

## Key Notes and Questions
- [Note/Question 1]
- [Note/Question 2]
- ...
```

## Output Format

Provide a summary of your work with:

- **Implementation Status:** Whether you're continuing or starting implementation
- **Progress File:** Path to the existing or newly created progress tracking file
- **Current Status:** Summary of completed and in-progress work
- **Next Actions:** Your immediate next implementation steps
- **Questions:** Any immediate questions about the feature plans

Then begin implementation, updating the progress tracking file as you work.
