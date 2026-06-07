# Tests

## Implemented

- **`test_constraints.py`**: Unit tests for the constraint checker:
  - Feasible schedule (all constraints satisfied).
  - One violation each: availability (power outside window), per_charger (exceeds max or negative), site_cap (total > P_max), energy (under-delivery / unmet).

## Planned

- Data loader (format conversion, API response handling).
- Metrics (cost, peak, unmet from known schedule).
- Integration: baseline and agent pipelines on small fixtures.
