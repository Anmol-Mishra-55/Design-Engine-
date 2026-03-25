# Export Pipeline

## Objective
Generate and deliver downloadable design artifacts in:

- `GLB`
- `STL`
- `STEP`

## Canonical Source
`GLB` generated from Prompt Runner-produced `spec_json` is the canonical geometry source.

Pipeline:
1. `spec_json` -> geometry generator -> `GLB`
2. `GLB` + spec dimensions -> `STL`
3. `GLB` + spec dimensions -> `STEP`

Implementation location:
- `backend/app/core_bucket_pipeline.py`

## Storage Strategy (Bucket Authority)
Remote-first, local-fallback:

- Remote bucket upload via `app.storage.upload_to_bucket(...)`
- If remote upload fails, local fallback paths are used:
  - `backend/data/geometry_outputs/<spec_id>.glb`
  - `backend/data/export_outputs/<spec_id>.stl`
  - `backend/data/export_outputs/<spec_id>.step`

Static serving:
- `GET /static/geometry/<spec_id>.glb`
- `GET /static/exports/<spec_id>.stl`
- `GET /static/exports/<spec_id>.step`

Configured in:
- `backend/app/main.py`

## API Response Contract
`POST /api/v1/generate` now returns export URLs in:

- `export_urls.glb`
- `export_urls.stl`
- `export_urls.step`

And convenience fields:

- `glb_url`
- `stl_url`
- `step_url`

Schema updated in:
- `backend/app/schemas/generate.py`

## Notes
- `STL` is generated as deterministic ASCII mesh export.
- `STEP` is generated as deterministic STEP payload with canonical geometry envelope metadata.
- Both are traceable to source `GLB` via hash metadata in generated files.

## Technical Details

### GLB Generation

**Primary Method**: `geometry_generator_real.generate_real_glb(spec_json)`
- Uses spec_json dimensions, objects, and materials
- Generates proper glTF 2.0 binary format
- Includes meshes, materials, textures

**Fallback Method**: `_fallback_glb()`
- Minimal valid GLB structure
- Used when primary generation fails
- Structure:
  ```
  glTF header (8 bytes): b"glTF\x02\x00\x00\x00"
  JSON chunk: {"asset":{"version":"2.0"}, ...}
  Padding to 1024 bytes
  ```

### STL Conversion Algorithm

**Input**: GLB bytes + spec_json + spec_id

**Process**:
1. Extract dimensions from spec_json:
   ```python
   width = spec_json["dimensions"]["width"]   # meters
   length = spec_json["dimensions"]["length"] # meters
   height = spec_json["dimensions"]["height"] # meters
   ```

2. Generate 8 box vertices:
   ```python
   vertices = [
       (0, 0, 0),           # Bottom-front-left
       (width, 0, 0),       # Bottom-front-right
       (width, length, 0),  # Bottom-back-right
       (0, length, 0),      # Bottom-back-left
       (0, 0, height),      # Top-front-left
       (width, 0, height),  # Top-front-right
       (width, length, height),  # Top-back-right
       (0, length, height)  # Top-back-left
   ]
   ```

3. Define 12 triangular faces (2 per box side):
   ```python
   faces = [
       # Bottom (z=0)
       (0, 1, 2), (0, 2, 3),
       # Top (z=height)
       (4, 5, 6), (4, 6, 7),
       # Front (y=0)
       (0, 1, 5), (0, 5, 4),
       # Right (x=width)
       (1, 2, 6), (1, 6, 5),
       # Back (y=length)
       (2, 3, 7), (2, 7, 6),
       # Left (x=0)
       (3, 0, 4), (3, 4, 7)
   ]
   ```

4. Calculate normal for each face:
   ```python
   def triangle_normal(a, b, c):
       u = b - a  # Edge vector 1
       v = c - a  # Edge vector 2
       n = cross_product(u, v)  # Normal vector
       return normalize(n)
   ```

5. Generate ASCII STL:
   ```
   solid bhiv_{spec_id}_{glb_hash}
     facet normal nx ny nz
       outer loop
         vertex x1 y1 z1
         vertex x2 y2 z2
         vertex x3 y3 z3
       endloop
     endfacet
     ...
   endsolid bhiv_{spec_id}_{glb_hash}
   ```

**Traceability**:
- Filename includes spec_id
- Solid name includes SHA256 hash of source GLB (first 16 chars)
- Example: `solid bhiv_spec_abc123_a1b2c3d4e5f6g7h8`

### STEP Conversion Algorithm

**Input**: GLB bytes + spec_json + spec_id

**Process**:
1. Extract dimensions (same as STL)

2. Generate ISO-10303-21 header:
   ```
   ISO-10303-21;
   HEADER;
   FILE_DESCRIPTION(('BHIV canonical STEP export'),'2;1');
   FILE_NAME('{spec_id}.step','{timestamp}',('BHIV'),('DesignEngine'),'CoreBucketPipeline','','');
   FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
   ENDSEC;
   ```

3. Add metadata in DATA section:
   ```
   DATA;
   #1=DESCRIPTIVE_REPRESENTATION_ITEM('SOURCE_GLB_SHA256','{hash}');
   #2=DESCRIPTIVE_REPRESENTATION_ITEM('DIMENSIONS_M','{w}x{l}x{h}');
   ```

4. Generate CARTESIAN_POINT entries:
   ```
   #10=CARTESIAN_POINT('V0',(0.000000,0.000000,0.000000));
   #11=CARTESIAN_POINT('V1',(width,0.000000,0.000000));
   ...
   #17=CARTESIAN_POINT('V7',(0.000000,length,height));
   ```

5. Close DATA section:
   ```
   ENDSEC;
   END-ISO-10303-21;
   ```

**Traceability**:
- FILE_NAME includes spec_id and timestamp
- SOURCE_GLB_SHA256 links to source GLB
- DIMENSIONS_M records exact dimensions used

## File Format Specifications

### GLB (GL Transmission Format Binary)
- **Standard**: glTF 2.0
- **MIME Type**: model/gltf-binary
- **Extension**: .glb
- **Structure**:
  - Header (12 bytes): magic, version, length
  - JSON chunk: Scene graph, materials, animations
  - Binary chunk: Geometry data, textures
- **Validation**: Must start with "glTF" magic bytes (0x46546C67)

### STL (STereoLithography)
- **Format**: ASCII (not binary)
- **MIME Type**: model/stl
- **Extension**: .stl
- **Structure**:
  ```
  solid <name>
    facet normal <nx> <ny> <nz>
      outer loop
        vertex <x> <y> <z>
        vertex <x> <y> <z>
        vertex <x> <y> <z>
      endloop
    endfacet
    ...
  endsolid <name>
  ```
- **Units**: Meters (as per spec_json dimensions)
- **Validation**: Must start with "solid" and end with "endsolid"

### STEP (Standard for the Exchange of Product model data)
- **Standard**: ISO 10303-21 (STEP-File)
- **MIME Type**: application/step
- **Extension**: .step or .stp
- **Schema**: AUTOMOTIVE_DESIGN (AP214)
- **Structure**:
  - ISO-10303-21 header
  - HEADER section: File metadata
  - DATA section: Entity instances
  - END-ISO-10303-21 footer
- **Validation**: Must start with "ISO-10303-21;" and end with "END-ISO-10303-21;"

## Troubleshooting Export Failures

### GLB Generation Fails
**Symptom**: Fallback GLB used (minimal geometry)

**Causes**:
1. Invalid spec_json structure
2. Missing required fields (dimensions, objects)
3. geometry_generator_real import error

**Debug**:
```python
from app.geometry_generator_real import generate_real_glb
try:
    glb = generate_real_glb(spec_json)
except Exception as e:
    print(f"Error: {e}")
```

**Fix**:
- Validate spec_json has dimensions dict
- Check objects array is present
- Verify geometry_generator_real.py exists

### STL File Invalid
**Symptom**: STL file doesn't open in CAD software

**Causes**:
1. Dimensions are zero or negative
2. Normal vectors are invalid
3. File truncated during write

**Validation**:
```bash
# Check file starts correctly
head -1 file.stl  # Should be "solid bhiv_..."

# Check file ends correctly
tail -1 file.stl  # Should be "endsolid bhiv_..."

# Count facets (should be 12 for box)
grep -c "facet normal" file.stl
```

**Fix**:
- Ensure dimensions > 0 in spec_json
- Check disk space for complete write
- Verify file permissions

### STEP File Invalid
**Symptom**: STEP file rejected by CAD software

**Causes**:
1. Invalid ISO-10303-21 syntax
2. Missing required sections
3. Incorrect entity references

**Validation**:
```bash
# Check header
head -5 file.step
# Should show:
# ISO-10303-21;
# HEADER;
# FILE_DESCRIPTION(...

# Check footer
tail -1 file.step
# Should be: END-ISO-10303-21;

# Validate entity IDs
grep "^#[0-9]" file.step
# Should show sequential IDs: #1, #2, #10, #11, ...
```

**Fix**:
- Ensure all sections present (HEADER, DATA, ENDSEC)
- Verify entity IDs are unique and sequential
- Check no special characters in strings

### Storage Failure (Both Remote and Local)
**Symptom**: HTTP 500 error, no files created

**Causes**:
1. Disk full
2. Permission denied
3. Directory doesn't exist

**Debug**:
```bash
# Check disk space
df -h backend/data/

# Check permissions
ls -ld backend/data/geometry_outputs/
ls -ld backend/data/export_outputs/

# Check directories exist
test -d backend/data/geometry_outputs && echo "OK" || echo "MISSING"
test -d backend/data/export_outputs && echo "OK" || echo "MISSING"
```

**Fix**:
```bash
# Create directories
mkdir -p backend/data/geometry_outputs
mkdir -p backend/data/export_outputs

# Fix permissions
chmod 755 backend/data/geometry_outputs
chmod 755 backend/data/export_outputs
```

## Verifying Export Quality

### Visual Inspection
1. **GLB**: Open in Blender, Three.js viewer, or Windows 3D Viewer
2. **STL**: Open in MeshLab, FreeCAD, or online STL viewer
3. **STEP**: Open in FreeCAD, SolidWorks, or AutoCAD

### Automated Validation

**GLB Validation**:
```python
import struct

def validate_glb(filepath):
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'glTF':
            return False, "Invalid magic bytes"
        version = struct.unpack('<I', f.read(4))[0]
        if version != 2:
            return False, f"Unsupported version: {version}"
        return True, "Valid GLB"
```

**STL Validation**:
```python
def validate_stl(filepath):
    with open(filepath, 'r') as f:
        first_line = f.readline().strip()
        if not first_line.startswith('solid'):
            return False, "Missing 'solid' header"

        facet_count = 0
        for line in f:
            if 'facet normal' in line:
                facet_count += 1

        if facet_count == 0:
            return False, "No facets found"

        return True, f"Valid STL with {facet_count} facets"
```

**STEP Validation**:
```python
def validate_step(filepath):
    with open(filepath, 'r') as f:
        first_line = f.readline().strip()
        if first_line != 'ISO-10303-21;':
            return False, "Invalid STEP header"

        content = f.read()
        if 'HEADER;' not in content:
            return False, "Missing HEADER section"
        if 'DATA;' not in content:
            return False, "Missing DATA section"
        if not content.strip().endswith('END-ISO-10303-21;'):
            return False, "Invalid STEP footer"

        return True, "Valid STEP file"
```

### Dimension Verification

```python
def verify_dimensions(spec_json, stl_path):
    expected_width = spec_json['dimensions']['width']
    expected_length = spec_json['dimensions']['length']
    expected_height = spec_json['dimensions']['height']

    # Parse STL and find max coordinates
    max_x = max_y = max_z = 0
    with open(stl_path, 'r') as f:
        for line in f:
            if 'vertex' in line:
                parts = line.strip().split()
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                max_z = max(max_z, z)

    tolerance = 0.001  # 1mm tolerance
    assert abs(max_x - expected_width) < tolerance
    assert abs(max_y - expected_length) < tolerance
    assert abs(max_z - expected_height) < tolerance

    return True, "Dimensions match"
```

## Performance Considerations

### Generation Time
- GLB: 50-500ms (depends on complexity)
- STL: 10-50ms (simple box geometry)
- STEP: 5-20ms (text generation)
- Total: ~100-600ms per request

### File Sizes
- GLB: 1KB-10MB (depends on geometry complexity)
- STL (ASCII): 2-5KB for simple box, scales with face count
- STEP: 1-3KB for simple geometry

### Optimization Tips
1. **Caching**: Cache generated exports for identical spec_json
2. **Async**: Generate exports in background for large models
3. **Compression**: Gzip STL/STEP files (50-70% size reduction)
4. **Binary STL**: Use binary STL for large models (5x smaller)

## Integration with CAD Software

### Blender
```python
import bpy
bpy.ops.import_scene.gltf(filepath="spec_abc123.glb")
```

### FreeCAD
```python
import FreeCAD
import Import
Import.insert("spec_abc123.step", "Document")
```

### MeshLab
```bash
meshlabserver -i spec_abc123.stl -o output.obj
```

### Online Viewers
- GLB: https://gltf-viewer.donmccurdy.com/
- STL: https://www.viewstl.com/
- STEP: https://www.freecadweb.org/ (desktop only)
