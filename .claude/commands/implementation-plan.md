# Create a Feature Feature Description Document - Follow below instruction from top-down

Use the following instructions to create a detailed Feature Description document for a new Letrado feature. This plan will serve as a guide for implementing the feature, but implementation should NOT be executed yet.

## Create a TODO with EXACTLY these 5 Items

1. Analyze the Feature Requirements and Technical Context
2. Identify Affected Files and Components
3. Design Implementation Approach with TypeScript Types
4. Define Implementation Steps in Detail
5. Suggest Validation Checkpoints

Follow these steps meticulously to generate a comprehensive Feature Description document.

## DETAILS on every TODO item

### 1. Analyze the Feature Requirements and Technical Context

check: <$ARGUMENTS>

If empty, prompt user for feature description, otherwise interpret <$ARGUMENTS> as the feature to be implemented.

- EXTRACT core functionality requirements
- IDENTIFY alignment with existing data layer architecture (FirestoreClient, DataManager)
- ANALYZE how feature fits with current React context system
- DETERMINE UI/UX considerations for Portuguese-language word game
- RELATE feature to existing user flow (anonymous vs. authenticated users)
- IDENTIFY integration points with Firebase services (Firestore, Auth, Functions)

### 2. Identify Affected Files and Components

- LIST specific files that need modification (exact paths)
- IDENTIFY affected React contexts (GameContext, AuthContext)
- DETERMINE required new components and files
- ANALYZE interface changes in existing components
- MAP data flow changes through the application
- IDENTIFY affected Cloud Functions (if any)

### 3. Design Implementation Approach with TypeScript Types

- DEFINE TypeScript interfaces and types needed for the feature
- DESIGN React component props and state
- DETERMINE required hook signatures
- SPECIFY any new DataManager methods and function signatures
- OUTLINE Firebase schema changes (if needed)
- MAINTAIN alignment with existing type patterns (e.g., GameResponse, DailyProgress)

### 4. Define Implementation Steps in Detail

- CREATE ordered list of coding tasks with precise file paths
- INCLUDE progress tracking markers [TODO], [IN PROGRESS], [COMPLETED]
- WRITE pseudo-code for key algorithms and data transformations
- PROVIDE specific utility functions needed
- HIGHLIGHT reuse opportunities with existing code
- SPECIFY explicit import statements needed
- INCLUDE error handling patterns
- INDICATE exact positioning of new code within existing files
- MARK critical implementation steps with [CRITICAL]
- FLAG potential challenges with [CAUTION]

### 5. Suggest Validation Checkpoints

- DEFINE clear success criteria for implementation
- CREATE validation steps with [VALIDATION] markers
- DETERMINE console.log statements for verification
- SUGGEST UI inspection points
- OUTLINE expected behavior with different user types
- PROVIDE verification approach for data persistence
- INCLUDE progress reporting instructions

## Output Format

IMPORTANT: The output should be a structured document, NOT actual implementation code.
PLACEMENT: write the document to docs/feature_descriptions directory.

In this specific order:

- **Feature Name:** Clear, concise name of the feature
- **Overview:** Brief summary focusing on user value and technical context
- **Requirements Analysis:** Detailed breakdown with technical implications
- **Files Affected:** List of all files to be modified with exact paths and purposes
- **TypeScript Models:** All new types, interfaces, and type extensions
- **Implementation Steps:** Numbered, ordered coding tasks with file paths and code snippets, including progress markers [TODO], [IN PROGRESS], [COMPLETED]
- **Key Notes:** Important implementation considerations marked with [NOTE], [CAUTION], or [CRITICAL]
- **Validation Checkpoints:** Specific checkpoints to verify during implementation with [VALIDATION] markers
- **Progress Tracking:** Instructions for reporting implementation progress

Make implementation steps precise and executable. Include exact file paths, specific function names, and code positioning guidance. Focus on maintaining consistency with existing Letrado application architecture patterns and React contexts.
