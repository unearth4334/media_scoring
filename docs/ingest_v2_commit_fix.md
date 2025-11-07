# Fix for Ingest V2 Commit Error

## Problem

During database ingestion using the ingest v2 tool, the following error occurred:

```
❌ Commit Failed
Error: This Session's transaction has been rolled back due to a previous exception during flush. 
To begin a new transaction with this Session, first issue Session.rollback(). 
Original exception was: A string literal cannot contain NUL (0x00) characters.
```

This error happened when:
1. A media file contained metadata or keywords with NUL (0x00) characters
2. PostgreSQL rejected the string with the NUL character
3. SQLAlchemy's session was rolled back
4. The code continued trying to use the rolled-back session
5. The entire batch commit failed catastrophically

## Solution

This fix implements a multi-layered approach to handle this error gracefully:

### 1. String Sanitization (`app/utils/sanitization.py`)

Added comprehensive string sanitization utilities that:
- Remove NUL (0x00) characters from all strings before database insertion
- Recursively sanitize nested dictionaries and lists
- Preserve all other content while removing only the problematic characters
- Handle metadata, keywords, and complex nested structures

Key functions:
- `sanitize_string()` - Removes NUL characters from individual strings
- `sanitize_dict()` - Recursively sanitizes dictionary values
- `sanitize_list()` - Recursively sanitizes list items
- `sanitize_file_data()` - Entry point for sanitizing complete file data

### 2. Enhanced Error Handling (`app/routers/ingest_v2.py`)

Updated the commit process to:
- Sanitize all file data before attempting database insertion
- Flush changes after each operation to detect errors early
- Catch and handle individual file errors without breaking the batch
- Rollback the session after each error to maintain database consistency
- Commit successful changes periodically (every 10 files) to avoid losing progress
- Track both successful and failed commits
- Continue processing remaining files even if some fail
- Report detailed error information for failed files

### 3. Comprehensive Testing

Added two test suites:

**tests/test_sanitization.py** - Unit tests for sanitization utilities:
- String sanitization with NUL characters
- Dictionary sanitization (simple and nested)
- List sanitization (simple and nested)
- File data sanitization (metadata, keywords, complex structures)
- Edge cases (empty strings, non-strings, clean data)

**tests/test_commit_nul_handling.py** - Integration tests for commit handling:
- Files with NUL characters in metadata
- Files with NUL characters in keywords
- Database error handling and rollback
- Complex nested structures with NUL characters

## Changes Made

### Modified Files

1. **app/routers/ingest_v2.py**
   - Added import for `sanitize_file_data`
   - Updated `_commit_single_file()` to:
     - Sanitize file data before database operations
     - Flush changes after each operation
     - Properly handle and rollback on errors
   - Updated `commit_data_background()` to:
     - Track successful and failed commits
     - Commit periodically to preserve progress
     - Log detailed statistics

### New Files

1. **app/utils/sanitization.py**
   - Complete string sanitization utility module
   - Functions for sanitizing strings, dicts, lists, and file data
   - Comprehensive documentation

2. **tests/test_sanitization.py**
   - 14 unit tests for sanitization functions
   - Coverage of all edge cases and data structures

3. **tests/test_commit_nul_handling.py**
   - 4 integration tests for commit error handling
   - Tests with mocked database service

4. **tests/manual_test_nul_handling.py**
   - Manual test script for verification
   - Demonstrates the fix in action
   - Provides clear output showing sanitization

## Testing

All tests pass successfully:

```bash
# Run sanitization tests
python3 -m pytest tests/test_sanitization.py -v
# Result: 14 passed

# Run commit handling tests  
python3 -m pytest tests/test_commit_nul_handling.py -v
# Result: 4 passed

# Run manual verification
python3 tests/manual_test_nul_handling.py
# Result: ✅ All Tests Passed!
```

## Impact

### Before the Fix
- A single file with NUL characters would cause the entire batch commit to fail
- No files would be saved to the database
- The session would be in an unusable state
- Users would see a cryptic SQLAlchemy error message

### After the Fix
- NUL characters are automatically removed from all data before insertion
- Individual file errors are caught and logged
- Other files in the batch continue to be processed
- The database remains in a consistent state
- Users see clear error messages for problematic files
- Successful files are committed periodically to preserve progress

## Usage

No changes to the API or user interface are required. The fix is transparent to users:

1. Start the ingest v2 process as normal
2. If files contain NUL characters, they will be automatically sanitized
3. If other database errors occur, they will be handled gracefully
4. Check the `commit_errors` list in the session status to see any issues
5. The majority of files will be committed successfully

## Future Enhancements

Possible improvements for future consideration:
- Add logging of sanitized data to help users identify source of NUL characters
- Provide option to reject files with NUL characters instead of sanitizing
- Add sanitization for other problematic characters
- Implement retry logic for transient database errors
- Add progress indicators showing successful vs. failed commits

## Backwards Compatibility

This fix is fully backwards compatible:
- No API changes
- No database schema changes
- No configuration changes required
- Existing functionality is preserved
- Only adds new error handling and sanitization
