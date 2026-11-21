# Plan 10-02 Summary: Facecam Detection REST API & Visual Debug Frame Export

## Implementation Overview
Exposed the streamer facecam detection pipeline via REST API endpoints, integrated stage checkpointing into `storage_service`, updated `MediaMetadata` with `facecam_region`, and implemented visual debug frame generation.

### Key Deliverables Completed:
1. **Model & Metadata Extension (`backend/app/models/project.py`)**:
   - Added `facecam_region: Optional[FacecamRegion] = None` to `MediaMetadata` Pydantic model for project-level persistence.
2. **REST API Router (`backend/app/api/routes_facecam.py`)**:
   - `POST /api/projects/{project_id}/facecam/detect`: Executes facecam spatial clustering on source media, caches results to `checkpoint_facecam.json`, updates project metadata, and generates an inspection JPEG preview.
   - `GET /api/projects/{project_id}/facecam`: Retrieves the cached `FacecamRegion` without recalculating.
   - `GET /api/projects/{project_id}/facecam/debug_frame`: Returns an annotated JPEG `FileResponse` showing the localized facecam bounding box, screen quadrant, and detection confidence overlay.
3. **Application Mount (`backend/app/main.py`)**:
   - Registered `facecam_router` under `/api/projects/{project_id}/facecam`.
4. **Visual Debug Frame Generator (`backend/app/services/facecam_service.py`)**:
   - Implemented `generate_debug_frame` with OpenCV FFMPEG demuxer, green bounding box overlay `(0, 255, 0)`, confidence tags, and fallback canvas generation for corrupt/stub media.
5. **Automated Integration Tests (`tests/test_facecam_api.py`)**:
   - 5 route tests covering 404 handling, 400 validation, detection execution, cache retrieval, and JPEG binary verification.
   - 100% pass rate.

## Verification Results
- `pytest tests/test_facecam_api.py -v`: 5 passed in 0.64s.
- `tests/run_all_tests.py`: All 36 tests passing in 0.27s.
