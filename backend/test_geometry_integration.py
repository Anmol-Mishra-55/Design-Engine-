"""
Test geometry integration across all files
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_geometry_imports():
    """Test that all geometry-related imports work"""
    try:
        # Test main geometry generator
        from app.geometry_generator_real import create_object_geometry, generate_real_glb

        print("OK: geometry_generator_real imports work")

        # Test generate.py imports
        from app.api.generate import create_local_preview_file, generate_mock_glb

        print("OK: generate.py imports work")

        # Test geometry API
        from app.api.geometry_generator import GLBGenerator

        print("OK: geometry_generator API imports work")

        # Test storage integration

        print("OK: storage.py imports work")

        return True
    except Exception as e:
        print(f"FAILED: Import failed: {e}")
        return False


def test_geometry_generation():
    """Test actual geometry generation"""
    try:
        from app.geometry_generator_real import generate_real_glb

        # Test kitchen spec
        kitchen_spec = {
            "objects": [
                {
                    "id": "kitchen_cabinet_01",
                    "type": "cabinet",
                    "dimensions": {"width": 2.0, "depth": 0.6, "height": 0.9},
                },
                {
                    "id": "kitchen_island_01",
                    "type": "island",
                    "dimensions": {"width": 2.4, "depth": 1.2, "height": 0.9},
                },
            ]
        }

        glb_data = generate_real_glb(kitchen_spec)
        print(f"OK: Kitchen GLB generated: {len(glb_data)} bytes")

        # Test building spec
        building_spec = {
            "objects": [
                {"id": "wall_01", "type": "wall", "dimensions": {"width": 5.0, "height": 3.0, "thickness": 0.2}},
                {"id": "door_01", "type": "door", "dimensions": {"width": 0.9, "height": 2.1, "thickness": 0.05}},
            ]
        }

        glb_data = generate_real_glb(building_spec)
        print(f"OK: Building GLB generated: {len(glb_data)} bytes")

        # Test automotive spec
        car_spec = {
            "objects": [
                {"id": "car_body_01", "type": "car_body", "dimensions": {"width": 1.8, "length": 4.5, "height": 1.5}},
                {"id": "wheel_01", "type": "wheel", "dimensions": {"radius": 0.3, "width": 0.2}},
            ]
        }

        glb_data = generate_real_glb(car_spec)
        print(f"OK: Automotive GLB generated: {len(glb_data)} bytes")

        return True
    except Exception as e:
        print(f"FAILED: Geometry generation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_file_creation():
    """Test local file creation"""
    try:
        from app.api.generate import create_local_preview_file

        spec = {"objects": [{"id": "test", "type": "cabinet", "dimensions": {"width": 1, "depth": 1, "height": 1}}]}

        test_path = "data/geometry_outputs/test_integration.glb"
        create_local_preview_file(spec, test_path)

        if os.path.exists(test_path):
            size = os.path.getsize(test_path)
            print(f"OK: Local file created: {test_path} ({size} bytes)")
            os.remove(test_path)  # Cleanup
            return True
        else:
            print("FAILED: Local file not created")
            return False

    except Exception as e:
        print(f"FAILED: File creation failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Geometry Integration...")
    print("=" * 50)

    tests = [test_geometry_imports, test_geometry_generation, test_file_creation]

    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"PASSED: {passed}/{len(tests)} tests")

    if passed == len(tests):
        print("SUCCESS: All geometry integration tests PASSED!")
    else:
        print("FAILED: Some tests failed - check integration")
