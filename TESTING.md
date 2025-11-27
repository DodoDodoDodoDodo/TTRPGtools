# Testing Guide for TTRPGTools

## Current Test Files

### `tests/test_parsers.py`
Tests individual parser functions in isolation:
- `parse_talent_table()` - Extracts talents from formatted tables
- `parse_talent_prose()` - Extracts talents from prose descriptions
- `parse_characteristic_advances_table()` - Parses stat advancement costs
- `parse_advances_table()` - Parses skill/talent advance tables
- `parse_divination_table()` - Parses divination roll tables
- `parse_psychic_powers()` - Parses psychic power definitions

**Key Point**: These tests use pre-extracted text snippets from `stuff.md` and verify the parsers can handle well-formatted input. They do NOT test:
- Career/rank context extraction from surrounding text
- Handling malformed or edge-case input
- Integration with the book_import auto-detection system

### `tests/test_book_import.py`
Tests the auto-detection system:
- Finding and parsing multiple section types in a single file
- Writing parsed entries to library files via CLI

**Key Point**: Tests that sections are found and parsed, but doesn't verify career/rank context is captured.

### `tests/test_models.py`
Tests the character and advance models:
- Character creation and XP tracking
- Advance purchase validation (prerequisites, costs, limits)
- Serialization/deserialization

### `tests/test_cli_import.py`
Tests CLI import commands:
- Text import workflow
- Error reporting

## Critical Missing Test Coverage

### 1. Career/Rank Context Extraction
**Problem**: Characteristic advances and skill/talent advances are parsed without capturing which career path or rank they belong to.

**Example**:
```
Table 2-2: Adept Characteristic Advances
Characteristic Simple Intermediate Trained Expert
Weapon Skill 500 750 1,000 2,500
...

ARCHIVIST
ADVANCES
"Throne blind you boy..."
Advance Cost Type Prerequisites
Drive (Ground Vehicle) 100 S —
...
```

The parser extracts the costs/advances but loses:
- Career: "Adept"
- Rank: "Archivist"

**Why AI Tests Miss This**:
- Tests only verify that parsing succeeds and extracts obvious fields
- They don't verify semantic correctness or domain-specific requirements
- They assume the structure shown in test data represents all requirements

### 2. Duplicate Handling
The database contains:
- 594 duplicate entries (same name, different career costs)
- 612 characteristic advances without career identification

**This is correct behavior** - each career has different advancement costs. But without career tracking, the data is unusable.

### 3. Data Integrity Constraints
No tests verify:
- All advances for a career have the same source
- Career names are normalized (e.g., "Guardsman" vs "guardsman")
- Rank names follow expected patterns
- Cross-references between advances (prerequisites) are valid

## How to Write Good Tests

### Test Real-World Usage Patterns

```python
def test_characteristic_advances_include_career():
    """Verify career path is captured from table headers."""
    text = """
Table 2-2: Adept Characteristic Advances
Characteristic Simple Intermediate Trained Expert
Weapon Skill 500 750 1,000 2,500
"""
    entries = parse_characteristic_advances_table(text)
    assert all(e.career == "Adept" for e in entries)
```

### Test Edge Cases from Real Data

```python
def test_advance_table_captures_rank():
    """Verify rank name is extracted from section headers."""
    text = """
ARCHIVIST
ADVANCES
"Quote here..."
Advance Cost Type Prerequisites
Drive (Ground Vehicle) 100 S —
"""
    entries = parse_advances_table(text)
    assert all(e.rank == "Archivist" for e in entries)
```

### Test Integration, Not Just Units

```python
def test_full_career_import_preserves_context():
    """Import a complete career section and verify all context is preserved."""
    # Use actual multi-section career text
    entries = auto_parse_book(full_adept_career_text)

    # Verify career and rank are on all entries
    assert all(e.get('career') for e in entries)

    # Verify no orphaned advances
    characteristic_advances = [e for e in entries if e['type'] == 'characteristic_advance']
    assert all(e.get('career') for e in characteristic_advances)
```

### Test Data Quality, Not Just Parsing

```python
def test_no_duplicate_advances_within_career():
    """Each career+rank should have unique advance names."""
    entries = load_database('advances.json')
    by_career_rank = group_by(entries, lambda e: (e['career'], e['rank']))

    for (career, rank), advances in by_career_rank.items():
        names = [a['name'] for a in advances]
        assert len(names) == len(set(names)), f"Duplicates in {career}/{rank}"
```

## Testing Philosophy

1. **Test behavior, not implementation**: Don't just verify the parser runs without errors. Verify it produces semantically correct output.

2. **Use real data**: Test files should use actual rulebook excerpts, not simplified examples.

3. **Test invariants**: Write tests that verify domain rules (e.g., "all advances must have a career").

4. **Test end-to-end workflows**: Don't just test parsers in isolation. Test the full import → query → use cycle.

5. **Make failures informative**: When a test fails, the error message should explain what domain rule was violated, not just "assertion failed".

## Next Steps for This Project

1. Add `career` and `rank` fields to all entry types
2. Modify parsers to accept and use these parameters
3. Update `book_import.py` to extract context from surrounding lines
4. Write tests that verify career/rank context is preserved
5. Re-import database with corrected data
