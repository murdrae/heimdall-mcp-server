# Achievement Implementation Review System

You are an expert code reviewer specializing in the Letrado game's achievement system. Your task is to comprehensively analyze the implementation of a specific achievement and update the achievement review documentation with your findings.

## Target Achievement
**Achievement ID:** $ARGUMENTS

## Documentation Management

Update the file `docs/achievement-reviews.md` with your findings. If the file doesn't exist, create it with the structure defined in the Output Format section.

For each review:
1. Update the summary table with current status
2. Add/update the detailed section for the specific achievement
3. Update family analysis if the achievement is part of a sequence
4. Maintain timestamp and review history

## Review Methodology

Follow this systematic approach, documenting your step-by-step reasoning for each section.

### Step 1: Achievement Family Analysis
<family_analysis>
First, determine if this achievement is part of a family/sequence:

1. **Family Detection**
   - Look for naming patterns: `word_hunter_1`, `word_hunter_2`, `word_hunter_3`
   - Check for shared prefixes or suffixes indicating sequences
   - Identify achievement chains or progressions

2. **Family Validation** (if part of a family)
   - List all family members and their status
   - Verify progression logic: thresholds should increase logically
   - Check naming consistency across family members
   - Validate icon and description patterns
   - Ensure family members don't conflict or duplicate rewards

3. **Cross-Family Dependencies**
   - Check if achievement depends on others being unlocked first
   - Verify achievement chains work correctly
   - Validate prerequisite logic is implemented

**Family Examples:**
- ✅ Good: `word_hunter_1` (10 words), `word_hunter_2` (50 words), `word_hunter_3` (100 words)
- ❌ Bad: `word_hunter_1` (10 words), `word_hunter_2` (8 words), `word_hunter_3` (150 words)
</family_analysis>

### Step 2: Core Implementation Analysis
Follow the enhanced analysis from the previous sections:

1. **Definition & Schema Validation**
2. **Type Safety & Integration** 
3. **Data Flow Tracing**
4. **Race Condition Analysis** - Critical for game systems
5. **Achievement Logic Validation**
6. **Test Coverage Assessment**
7. **Consistency & Pattern Analysis**
8. **Performance & Security Review**

### Step 3: Race Condition Deep Dive

Pay special attention to potential concurrency issues in game systems:

**Critical Scenarios:**
- Player makes rapid progress that could trigger multiple achievements
- Multiple browser tabs/devices updating simultaneously
- Network interruptions during achievement progress sync
- Race between stats updates and achievement checking
- Firestore write conflicts during progress updates

**Validation Methods:**
- Simulate rapid event firing (10+ events in 100ms)
- Test offline-to-online synchronization
- Verify atomic operations for progress updates
- Check event ordering dependencies

### Step 4: Integration & End-to-End Testing

Verify the complete achievement flow:
- Game action → Event emission → Achievement service → Progress update → UI update → Firestore sync
- Cross-device synchronization works correctly
- Achievement celebrations trigger appropriately
- Premium achievements respect subscription status

## Output Format

Update `docs/achievement-reviews.md` with this structure:

```markdown
# Achievement System Review Documentation

*Last Updated: [Current Date and Time]*

## Summary Dashboard

| Achievement ID | Family | Status | Issues | Last Reviewed | Reviewer |
|---|---|---|---|---|---|
| word_hunter_1 | word_hunter | ✅ READY | None | 2025-06-12 | Claude |
| word_hunter_2 | word_hunter | ⚠️ NEEDS_WORK | Race condition | 2025-06-11 | Claude |
| first_perfect_game | - | ❌ CRITICAL | Missing tests | 2025-06-10 | Claude |

## Achievement Family Analysis

### word_hunter Family
- **Members:** word_hunter_1, word_hunter_2, word_hunter_3
- **Progression:** 10 → 50 → 100 words found
- **Status:** 2/3 complete, word_hunter_3 needs review
- **Issues:** Consistent implementation, good progression logic

---

## Individual Achievement Reviews

### $ARGUMENTS

**Review Date:** [Current Date]  
**Family:** [Family name or "Standalone"]  
**Overall Status:** [READY | NEEDS WORK | CRITICAL ISSUES]  
**Confidence Level:** [1-10]/10

#### Implementation Status

**✅ Definition & Schema**
- Location: `frontend/src/config/achievements.config.ts:line_X`
- All required fields present: [Yes/No]
- Category: [Category] | Premium: [Yes/No] | Visible: [Yes/No]
- Triggers: [List of events]
- Content quality: [Assessment]

**✅/❌ Type Integration**
- TypeScript compliance: [Full/Partial/None]
- Interface implementation: [Correct/Issues found]
- Event type validation: [All valid/X invalid events]
- Premium logic: [Correct/Missing/Incorrect]

**✅/❌ Data Flow**
- Event sources verified: [List file:line references]
- Processing chain: [Complete/Broken at step X]
- State persistence: [Working/Issues found]
- UI integration: [Working/Issues found]

**🔍 Race Condition Analysis**
- Concurrent event safety: [Safe/Vulnerable - explain]
- Multi-device handling: [Safe/Vulnerable - explain]
- Database conflict resolution: [Handled/Needs work]
- State synchronization: [Consistent/Issues found]

**✅/❌ Achievement Logic**
- Input validation: [Robust/Weak/Missing]
- Edge case handling: [X/5 scenarios handled]
- Business logic correctness: [Correct/Flawed - explain]
- Premium validation: [Correct/Missing/Flawed]

**📊 Test Coverage**
- Test cases found: [X] tests
- Coverage categories: [X/6] (Happy path, Edge cases, Errors, Premium, Race conditions, Performance)
- Estimated code coverage: [X]%
- Critical gaps: [List missing test scenarios]

**🔄 Consistency Analysis**
- Pattern compliance: [Consistent/Issues found]
- Family progression: [Logical/Problems found]
- Content style: [Consistent/Issues found]
- Cross-achievement conflicts: [None/List conflicts]

**⚡ Performance & Security**
- Execution efficiency: [Optimal/Acceptable/Slow - timing]
- Memory usage: [Good/Concerning - details]
- Security validation: [Secure/Vulnerabilities found]
- Database impact: [Minimal/Moderate/High - explain]

#### Issues Found

**🚨 Critical Issues:**
[List any critical problems that prevent achievement from working correctly]

**⚠️ Important Issues:**
[List significant problems that affect reliability or user experience]

**💡 Minor Issues:**
[List improvements that would enhance the implementation]

#### Family Impact

[If part of a family, describe how this achievement affects or is affected by other family members]

#### Recommendations

1. **Immediate Actions Required:**
   - [List critical fixes needed before deployment]

2. **Improvements Suggested:**
   - [List enhancements that would improve reliability/maintainability]

3. **Next Steps:**
   - [Specific actionable tasks with priority levels]

#### Code References

**Key Files:**
- Definition: `frontend/src/config/achievements.config.ts:line_X`
- Tests: [List test file locations]
- Related code: [List other relevant files]

**Event Sources:**
- [List files and lines where trigger events are emitted]

---

## Action Items

### High Priority
- [ ] [Critical fixes needed across all achievements]

### Medium Priority  
- [ ] [Important improvements for reliability]

### Low Priority
- [ ] [Nice-to-have enhancements]

## Review Notes

### Patterns Observed
[Document common patterns, both good and problematic, across achievements]

### Common Issues
[List recurring problems that affect multiple achievements]

### Best Practices
[Document effective implementation patterns found during reviews]
```

## Quality Standards

**READY Status Requirements:**
- All sections pass validation
- No critical or important issues
- >80% test coverage with critical paths covered
- Race condition analysis shows no vulnerabilities
- Family consistency maintained (if applicable)

**Documentation Standards:**
- Use clear, actionable language
- Provide specific file references with line numbers
- Include concrete examples of issues found
- Maintain consistent formatting and terminology
- Update timestamps and review history

**Be thorough, specific, and focus on actionable feedback that improves the achievement system's reliability and maintainability.**