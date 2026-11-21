"""Unit tests for FacecamService spatial clustering and crop box expansion."""

import unittest
from backend.app.services.facecam_service import FacecamService
from backend.app.models.facecam import FacecamRegion


class TestFacecamService(unittest.TestCase):

    def setUp(self):
        self.service = FacecamService()

    def test_spatial_clustering_detects_webcam(self):
        """Persistent faces in one quadrant with low variance should be identified as the facecam."""
        # 100 samples total
        total_samples = 100
        detections = []

        # Streamer in TOP_RIGHT (around x=1500, y=100, w=160, h=160 in 1920x1080)
        # Present in 60 frames with slight natural jitter
        for i in range(60):
            detections.append({
                "frame_idx": i,
                "x": 1500 + (i % 5),
                "y": 100 + (i % 3),
                "w": 160 + (i % 2),
                "h": 160 + (i % 2)
            })

        # Add transient NPC faces moving across the screen in bottom half (frames 10 to 20)
        for i in range(10):
            detections.append({
                "frame_idx": 10 + i,
                "x": 100 + i * 80,  # Moving rapidly across
                "y": 700,
                "w": 120,
                "h": 120
            })

        cluster = self.service.cluster_persistent_faces(
            frame_detections=detections,
            total_samples=total_samples,
            frame_w=1920,
            frame_h=1080
        )

        self.assertIsNotNone(cluster)
        self.assertEqual(cluster["quadrant"], "TOP_RIGHT")
        self.assertGreaterEqual(cluster["persistence_ratio"], 0.50)
        self.assertAlmostEqual(cluster["fw"], 160, delta=5)
        self.assertAlmostEqual(cluster["fh"], 160, delta=5)

    def test_rejection_of_transient_gameplay_faces(self):
        """Transient NPC faces appearing in only a few frames or moving widely should be rejected."""
        total_samples = 100
        detections = []

        # Only 5 frames have faces scattered across screen
        for i in range(5):
            detections.append({
                "frame_idx": i * 15,
                "x": 200 * i,
                "y": 300,
                "w": 100,
                "h": 100
            })

        cluster = self.service.cluster_persistent_faces(
            frame_detections=detections,
            total_samples=total_samples,
            frame_w=1920,
            frame_h=1080
        )

        self.assertIsNone(cluster)

    def test_facecam_crop_box_expansion(self):
        """Crop box should expand around face, preserve 16:9 widescreen ratio, and have even dimensions."""
        fx, fy, fw, fh = 1400, 150, 120, 120
        frame_w, frame_h = 1920, 1080

        x, y, w, h = self.service.calculate_facecam_crop_box(
            fx=fx, fy=fy, fw=fw, fh=fh,
            frame_w=frame_w, frame_h=frame_h,
            target_aspect=16.0 / 9.0
        )

        # Dimensions must be even for encoder compatibility
        self.assertEqual(w % 2, 0)
        self.assertEqual(h % 2, 0)
        self.assertEqual(x % 2, 0)
        self.assertEqual(y % 2, 0)

        # Expanded box should be larger than original face
        self.assertGreater(w, fw)
        self.assertGreater(h, fh)

        # Aspect ratio should approximate 16:9
        aspect = w / h
        self.assertAlmostEqual(aspect, 16.0 / 9.0, delta=0.05)

        # Must fit inside frame bounds
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, frame_w)
        self.assertLessEqual(y + h, frame_h)

    def test_boundary_clamping(self):
        """Crop box near top-left or bottom-right edges must clamp within [0, frame_bounds]."""
        # Face right in top-left corner
        x, y, w, h = self.service.calculate_facecam_crop_box(
            fx=10, fy=10, fw=100, fh=100,
            frame_w=1920, frame_h=1080
        )
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)
        self.assertLessEqual(w, 1920)
        self.assertLessEqual(h, 1080)

        # Face right in bottom-right corner
        x2, y2, w2, h2 = self.service.calculate_facecam_crop_box(
            fx=1850, fy=1000, fw=100, fh=100,
            frame_w=1920, frame_h=1080
        )
        self.assertLessEqual(x2 + w2, 1920)
        self.assertLessEqual(y2 + h2, 1080)
        self.assertGreaterEqual(x2, 0)
        self.assertGreaterEqual(y2, 0)

    def test_empty_detections(self):
        """Empty detections should return None safely."""
        res = self.service.cluster_persistent_faces([], total_samples=50, frame_w=1920, frame_h=1080)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
