# EMSN2 Vocalization Integration

This folder contains EMSN-specific vocalization integration scripts.

## Files

- `vocalization_enricher.py` - Enriches BirdNET detections with vocalization type (EMSN-specific, uses PostgreSQL)
- `vocalization_classifier.py` - CNN inference classifier (copy from emsn-vocalization repo)

## Community Repository

For training, Colab notebooks, and the full vocalization classifier system, see:
**https://github.com/RonnyCHL/emsn-vocalization**

The classifier code here is a local copy for the enricher service.
For updates, sync from the community repository.
