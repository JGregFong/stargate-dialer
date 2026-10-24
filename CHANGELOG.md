# Changelog

## 2026-10-24

### Changed

- Set glyph-track cruising speed to 5 RPM (30 degrees per second), with smooth 1.5-second acceleration and braking ramps.
- Calculate symbol travel times from angular distance while preserving alternating rotation, centered symbol stops, and the 2.8-second encoding and lock interval.
- Synchronize glyph animation, tile flashes, and gate audio with the variable dialing cycle lengths, including DHD resume timing.
- Separate connector colors from chevron colors; inactive connectors remain dim while selected chevrons use yellow outlines.
- Add six stripes along each side of the chevron clamps and narrow their inward-facing ends. Name the outer portion the clamp and the inner portion the jewel in the rendering code.
- Use a black console background and brighter yellow details, and label the glyph keyboard's dialing button ACTIVATE.

### Added

- Regression tests for cruising speed, smooth speed ramps, symbol alignment, and encoding timing.
- Eight program screenshots and an overview in `previews/`.
- Chevron reference photograph in `reference/Front_Face_SG1.jpg`.
