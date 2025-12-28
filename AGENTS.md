# Fork-Specific Changes for AI Agents

This document describes changes made to this fork for a **picture frame use case**. These modifications enable random photo browsing suitable for digital picture frames.

## Branch: `picture_frame_tweaks`

## Use Case
This fork adds functionality to browse iCloud photos at random offsets, making it suitable for digital picture frame applications that need to display photos in a randomized manner rather than sequential order.

## Modified Files

### `src/pyicloud_ipd/services/photos.py`

**Location**: `PhotoAlbum` class (around line 666-795)

**Changes Summary**:
1. Add `random` import
2. Add `random_offset_mode` parameter to `__init__`
3. Add `_offsets` tracking list to `__init__`
4. Initialize random offsets on first iteration in `photos` property (when `random_offset_mode=True`)
5. Replace sequential offset progression with random selection (when `random_offset_mode=True`)

**Detailed Modifications**:

#### 1. Add Random Import
```python
# At top of file (around line 4):
import random
```

#### 2. Add random_offset_mode Parameter and Offsets Tracking to __init__
```python
# In PhotoAlbum.__init__ (around line 668):
def __init__(
    self,
    params: Dict[str, Any],
    session: PyiCloudSession,
    service_endpoint: str,
    name: str,
    list_type: str,
    obj_type: str,
    query_filter: Sequence[Dict[str, Any]] | None = None,
    page_size: int = 100,
    zone_id: Dict[str, Any] | None = None,
    random_offset_mode: bool = False,  # NEW: Enable picture frame mode
):
    # ... existing fields ...
    self.random_offset_mode = random_offset_mode  # NEW
    self._offsets: list[int] = []  # NEW: For picture frame random offset tracking
```

#### 3. Initialize Random Offsets in photos Property
```python
# At start of photos property (around line 734):
@property
def photos(self) -> Generator[PhotoIterationResult, Any, None]:
    # Picture frame mode: Initialize random offsets on first iteration
    if self.random_offset_mode and not self._offsets:  # NEW: Guard with mode check
        album_length_result = self.get_album_length()
        match album_length_result:
            case AlbumLengthSuccess(count):
                album_length = count
            case _:
                # If we can't get album length, fall back to sequential
                album_length = 0
        
        if album_length > 0:
            self._offsets = [i for i in range(0, album_length - 1, min(self.page_size, album_length))]
            try:
                self.offset = self._offsets.pop(random.randint(0, len(self._offsets) - 1))
            except (ValueError, IndexError):
                self.offset = 0
    
    while True:
        # ... rest of method
```

#### 4. Replace Offset Progression Logic
```python
# In photos property, after yielding photos (around line 785):
if master_records_len:
    for master_record in master_records:
        record_name = master_record["recordName"]
        yield PhotoIterationSuccess(
            PhotoAsset(master_record, asset_records[record_name])
        )
    
    # Picture frame mode: Pick next random offset after yielding all photos at current offset
    if self.random_offset_mode:  # NEW: Guard with mode check
        try:
            self.offset = self._offsets.pop(random.randint(0, len(self._offsets) - 1))
        except ValueError:
            self.offset = 0
        except IndexError:
            yield PhotoIterationComplete()
            return
    else:  # NEW: Preserve original sequential behavior
        self.increment_offset(1)
else:
    yield PhotoIterationComplete()
    return
```

## Re-applying Changes After Upstream Merge

When merging upstream changes, focus on the `PhotoAlbum.photos` property in `src/pyicloud_ipd/services/photos.py`:

1. **Add import**: Ensure `import random` is at the top of the file
2. **Add tracking field**: Add `self._offsets: list[int] = []` to `PhotoAlbum.__init__`
3. **Initialize offsets**: At start of `photos` property, check if `_offsets` is empty and initialize with random offset list
4. **Replace offset progression**: Remove `self.increment_offset(1)` calls and replace with random offset selection after yielding photos
5. **Handle edge cases**: Catch `ValueError` and `IndexError` when popping from offsets list

## Testing Considerations

Test these scenarios after re-applying changes:
- Album with single photo (should not crash)
- Album with photos < page_size (should handle gracefully)
- Empty offsets list (should start at 0 or complete iteration)
- Album length retrieval failure (should fall back to sequential)

## Commit History

- `136c7af` (2025-12-28): Update AGENTS.md with latest commit history
- `d9a27c0` (2025-12-28): Fix type check errors in http.py and test_random_offset_mode.py
- `81d0fbd` (2025-12-28): Add random offset mode for picture frame use case
- `2fbd3b9` (2025-12-28): Add comprehensive tests for random offset mode
- `7ad07a5` (2024-09-20): Add handling for a single offset
- `2b998ce` (2024-09-20): Handle ValueError when offsets are exhausted
- `52f000d` (2024-09-20): Handle case where filters return a single photo
- `e4af2b1` (2024-07-07): Initial random offset implementation

## Dependencies

No additional dependencies required beyond upstream project.
