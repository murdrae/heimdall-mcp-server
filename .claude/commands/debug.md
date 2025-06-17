# Debug issue - Follow below instruction from top-down

Follow these steps to debug and fix an issue in the Letrado project.

## Create a TODO with EXACTLY these 5 Items

1. Track issue in GitHub
2. Identify root cause
3. Propose solution and get approval
4. Implement fix
5. Document resolution

## DETAILS on every TODO item

### 1. Track issue in GitHub

- USE `gh issue view [number]` IF issue number was provided in <$ARGUMENTS>
- USE `gh issue create` with clear description IF NO issue number provided
- EXTRACT information tracked in the GitHub issue

### 2. Identify root cause

- LOCATE relevant code files and execution paths
- TRACE how the error occurs
- TEST hypotheses systematically
- ISOLATE specific code causing the issue
- EXTRACT exact error messages and reproduction steps
- IDENTIFY affected components and user flows

### 3. Provide Debug Report and get approval

- DETERMINE minimal changes needed
- IDENTIFY specific files to modify
- PROVIDE the following report to the user:

```markdown
# Debug Report: [Issue Description]
Date: YYYY-MM-DD
GitHub Issue: #[issue-number]

## Root Cause
[What causes the issue]

## Solution
[How it should be fixed]

## Files to be Modified
- [file path]: [changes to be made]

## Verification
[How it can be tested]

## Prevention
[How to prevent similar issues]
```

- STOP!!
- WAIT EXPLICIT approval
- DOCUMENT the report in the gh issue
- PROCEED to implementation

### 4. Implement fix

- MAKE approved changes only
- ADD error handling as needed
- TEST fix thoroughly
- VERIFY issue is resolved
- UPDATE GitHub issue with progress

### 5. Document resolution

- UPDATE GitHub issue with the Debug Report - updated to cover the work done
- CLOSE GitHub issue with reference to report


## Output Format

- **GitHub Issue:** #[number] (new or existing)
- **Issue Summary:** Brief description
- **Root Cause:** Analysis of the problem
- **Proposed Solution:** How to fix it
- **Approval Status:** Awaiting user approval or approved
- **Implementation Status:** Complete or in progress
- **Debug Report:** Path to report when completed

CRITICAL: Must get user approval before implementing any fix.
