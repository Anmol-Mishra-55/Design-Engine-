# Execution Authority

## Allowed Path
Client → Core → Bucket → Prompt Runner → Engine → Bucket → Core

## Forbidden:
- Direct LLM calls
- Geometry fallback generation
- Multiple execution paths
- Skipping Core or Bucket

## Enforcement:
- All requests must originate from Core
- All outputs must be stored in Bucket
- Prompt Runner is the only execution trigger
