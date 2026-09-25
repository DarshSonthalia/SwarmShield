import unittest
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

from swarmshield.webapp import STATIC_ROOT, SwarmShieldHandler, generate_payload


class WebAppTests(unittest.TestCase):
    def test_payload_has_both_runs(self):
        payload = generate_payload()
        self.assertEqual(set(payload["runs"]), {"baseline", "swarmshield"})
        self.assertTrue(payload["runs"]["swarmshield"]["trajectories"])

    def test_payload_accepts_custom_force_sizes(self):
        payload = generate_payload(7, 3, seed=9, duration_s=75)
        self.assertEqual(payload["scenario"]["threat_count"], 7)
        self.assertEqual(payload["scenario"]["interceptor_count"], 3)
        self.assertEqual(payload["scenario"]["duration_s"], 75)

    def test_index_uses_module_driven_3d_scene(self):
        html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="tacticalScene"', html)
        self.assertIn('<script type="module" src="/app.js"></script>', html)
        self.assertNotIn('id="tacticalMap"', html)
        self.assertIn("SYNTHETIC SCENARIO", html)
        self.assertIn("VERTICAL SCALE 3×", html)

    def test_renderer_uses_local_three_modules(self):
        renderer = (STATIC_ROOT / "tactical3d.js").read_text(encoding="utf-8")
        self.assertIn("from 'three'", renderer)
        self.assertIn("./vendor/OrbitControls.js", renderer)
        self.assertNotIn("https://", renderer)
        for name in ("three.module.js", "three.core.js", "OrbitControls.js", "LICENSE", "README.md"):
            self.assertTrue((STATIC_ROOT / "vendor" / name).is_file(), name)

    def test_renderer_exposes_controller_api(self):
        renderer = (STATIC_ROOT / "tactical3d.js").read_text(encoding="utf-8")
        self.assertIn("export function initTactical3D", renderer)
        for method in (
            "loadScenario", "setStrategy", "setTime", "setVisibility",
            "setCameraPreset", "resize", "dispose",
        ):
            self.assertIn(method, renderer)

    def test_controller_delegates_rendering(self):
        app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("initTactical3D", app)
        self.assertIn("viewer.loadScenario", app)
        self.assertIn("viewer.setStrategy", app)
        self.assertIn("viewer.setTime", app)
        self.assertNotIn("tacticalMap", app)
        self.assertNotIn("getContext('2d')", app)

    def test_renderer_declares_visual_only_boundaries(self):
        renderer = (STATIC_ROOT / "tactical3d.js").read_text(encoding="utf-8")
        self.assertIn("export const VERTICAL_SCALE = 3", renderer)
        self.assertIn("export const TRAIL_WINDOW_SECONDS = 20", renderer)
        self.assertIn("export function simulationToWorld", renderer)
        self.assertIn("setTime(continuousTime, discreteTime", renderer)

    def test_server_serves_local_modules_as_javascript(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), SwarmShieldHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for path in ("/app.js", "/tactical3d.js", "/vendor/three.module.js", "/vendor/three.core.js", "/vendor/OrbitControls.js"):
                with self.subTest(path=path), urlopen(base + path) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("javascript", response.headers["Content-Type"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
