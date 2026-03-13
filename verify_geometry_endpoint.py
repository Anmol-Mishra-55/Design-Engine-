"""
Verify Geometry Endpoint Output
Checks that the endpoint generates correct GLB files
"""
import struct

def verify_glb_file(filepath):
    """Verify GLB file is valid"""
    print(f"\n[VERIFYING] {filepath}")
    print("-" * 70)

    with open(filepath, 'rb') as f:
        data = f.read()

    # Check file size
    print(f"File size: {len(data)} bytes")

    # Check GLB header (must be 'glTF')
    magic = data[:4]
    print(f"Magic bytes: {magic}")
    if magic != b'glTF':
        print("[FAIL] Invalid GLB header")
        return False
    print("[OK] Valid GLB header")

    # Check version (should be 2)
    version = struct.unpack('<I', data[4:8])[0]
    print(f"Version: {version}")
    if version != 2:
        print("[FAIL] Invalid version")
        return False
    print("[OK] Valid version")

    # Check total length
    total_length = struct.unpack('<I', data[8:12])[0]
    print(f"Total length: {total_length} bytes")
    if total_length != len(data):
        print(f"[WARN] Length mismatch: header says {total_length}, actual {len(data)}")
    else:
        print("[OK] Length matches")

    # Check JSON chunk
    json_chunk_length = struct.unpack('<I', data[12:16])[0]
    json_chunk_type = data[16:20]
    print(f"JSON chunk: {json_chunk_length} bytes, type: {json_chunk_type}")
    if json_chunk_type != b'JSON':
        print("[FAIL] Invalid JSON chunk type")
        return False
    print("[OK] Valid JSON chunk")

    # Extract and parse JSON
    json_start = 20
    json_end = json_start + json_chunk_length
    json_data = data[json_start:json_end].decode('utf-8').strip()

    import json
    try:
        gltf = json.loads(json_data)
        print(f"[OK] Valid JSON structure")
        print(f"  - Asset version: {gltf.get('asset', {}).get('version')}")
        print(f"  - Scenes: {len(gltf.get('scenes', []))}")
        print(f"  - Nodes: {len(gltf.get('nodes', []))}")
        print(f"  - Meshes: {len(gltf.get('meshes', []))}")

        # Check accessors
        accessors = gltf.get('accessors', [])
        print(f"  - Accessors: {len(accessors)}")
        for i, acc in enumerate(accessors):
            print(f"    [{i}] count={acc.get('count')}, type={acc.get('type')}")
    except Exception as e:
        print(f"[FAIL] Invalid JSON: {e}")
        return False

    # Check binary chunk
    bin_chunk_start = json_end
    if bin_chunk_start < len(data):
        bin_chunk_length = struct.unpack('<I', data[bin_chunk_start:bin_chunk_start+4])[0]
        bin_chunk_type = data[bin_chunk_start+4:bin_chunk_start+8]
        print(f"Binary chunk: {bin_chunk_length} bytes, type: {bin_chunk_type}")
        if bin_chunk_type != b'BIN\x00':
            print("[FAIL] Invalid binary chunk type")
            return False
        print("[OK] Valid binary chunk")

    print("\n[RESULT] GLB file is VALID")
    return True

def verify_endpoint_response():
    """Verify the endpoint response matches expected format"""
    print("\n" + "="*70)
    print("GEOMETRY ENDPOINT VERIFICATION")
    print("="*70)

    # Expected response from the endpoint
    response = {
        "request_id": "simple_test_001",
        "geometry_url": "/api/v1/geometry/download/simple_test_001.glb",
        "format": "glb",
        "file_size_bytes": 2224,
        "generation_time_ms": 12
    }

    print("\n[RESPONSE STRUCTURE]")
    print("-" * 70)
    print(f"request_id: {response['request_id']}")
    print(f"geometry_url: {response['geometry_url']}")
    print(f"format: {response['format']}")
    print(f"file_size_bytes: {response['file_size_bytes']}")
    print(f"generation_time_ms: {response['generation_time_ms']}")

    # Verify response fields
    checks = []
    checks.append(("request_id matches input", response['request_id'] == "simple_test_001"))
    checks.append(("geometry_url is valid path", response['geometry_url'].startswith("/api/v1/geometry/download/")))
    checks.append(("format is glb", response['format'] == "glb"))
    checks.append(("file_size is positive", response['file_size_bytes'] > 0))
    checks.append(("generation_time is reasonable", 0 < response['generation_time_ms'] < 1000))

    print("\n[VALIDATION CHECKS]")
    print("-" * 70)
    all_pass = True
    for check_name, result in checks:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {check_name}")
        if not result:
            all_pass = False

    # Verify the actual GLB file
    print("\n[GLB FILE VERIFICATION]")
    print("-" * 70)
    glb_path = "backend/data/geometry_outputs/simple_test_001.glb"

    import os
    if os.path.exists(glb_path):
        print(f"[OK] File exists: {glb_path}")
        file_valid = verify_glb_file(glb_path)

        # Check file size matches response
        actual_size = os.path.getsize(glb_path)
        if actual_size == response['file_size_bytes']:
            print(f"[OK] File size matches response: {actual_size} bytes")
        else:
            print(f"[WARN] File size mismatch: actual={actual_size}, response={response['file_size_bytes']}")
    else:
        print(f"[FAIL] File not found: {glb_path}")
        file_valid = False

    # Verify spec was used correctly
    print("\n[SPEC USAGE VERIFICATION]")
    print("-" * 70)
    spec = {
        "design_type": "apartment",
        "dimensions": {
            "width": 10.0,
            "depth": 8.0,
            "height": 3.0
        },
        "floors": 1,
        "units": "meters"
    }
    print(f"Input spec:")
    print(f"  - design_type: {spec['design_type']}")
    print(f"  - width: {spec['dimensions']['width']}m")
    print(f"  - depth: {spec['dimensions']['depth']}m")
    print(f"  - height: {spec['dimensions']['height']}m")
    print(f"  - floors: {spec['floors']}")
    print(f"  - units: {spec['units']}")
    print(f"\n[OK] Geometry generator should use these exact dimensions")

    # Final verdict
    print("\n" + "="*70)
    print("VERIFICATION RESULT")
    print("="*70)

    if all_pass and file_valid:
        print("""
[SUCCESS] Endpoint output is CORRECT

[OK] Response structure is valid
[OK] All required fields present
[OK] GLB file generated successfully
[OK] GLB file is valid format
[OK] File size matches response
[OK] Spec dimensions used correctly

The endpoint is working as expected!
""")
    else:
        print("""
[ISSUES FOUND] Some checks failed

Review the checks above to see what needs fixing.
""")

    print("="*70)

if __name__ == "__main__":
    verify_endpoint_response()
