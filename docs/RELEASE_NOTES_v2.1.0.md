## EMSN 2.0 Vocalization Classifier v2.1.0

Eerste publieke release van de vocalization classifier voor Nederlandse vogelsoorten.

### Wat is dit?
Een geautomatiseerde pipeline die CNN-modellen traint om vogelgeluiden te classificeren naar type: **song** (zang), **call** (roep), of **alarm** (alarmroep).

### Highlights
- 232 Nederlandse vogelsoorten ondersteund
- PyTorch CNN geoptimaliseerd voor CPU (geen GPU nodig)
- Kwartaal versioning systeem (2025Q1, 2025Q2, etc.)
- Xeno-canto integratie voor trainingsdata
- Grafana dashboard voor monitoring
- PostgreSQL database voor status tracking

### Bug Fixes in v2.1
- numpy float64 → Python float voor PostgreSQL compatibiliteit
- DataLoader workers stabiliteit fix voor NAS
- Volume mount voor live code updates

### Licenties
- **Code:** Apache 2.0
- **Modellen:** CC BY-NC 4.0

### Citeren
```bibtex
@software{emsn2_vocalization,
  author = {Hullegie, Ronny},
  title = {EMSN 2.0 Vocalization Classifier},
  year = {2025},
  url = {https://github.com/RonnyCHL/emsn2}
}
```

---
Full changelog: https://github.com/RonnyCHL/emsn2/blob/main/docs/vocalization/README.md#changelog
