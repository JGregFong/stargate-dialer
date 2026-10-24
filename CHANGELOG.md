# Changelog

## 2026-10-24

### Changed

- Share configurable RPM across computer/DHD dialing, ring rendering, and abort braking through common motion calculations; add the `--rpm` launch option.
- Shorten acceleration ramps for fast moves so rendering still stops at the selected symbol.

- Split the console into composed keyboard, archive, options, command, and renderer components, with shared UI geometry in its own module.
- Separate simulation policies for address validation, encoding states, DHD queues, activation, and connection lifetime; retain the public Dialer interface.
- Correct extended-address acquisition messages to show the selected symbol count.
- Consolidate the README around current controls, setup, architecture, and verification.

- Set glyph-track cruising speed to 5 RPM (30 degrees per second), with smooth 1.5-second acceleration and braking ramps.
- Calculate symbol travel times from angular distance while preserving alternating rotation, centered symbol stops, and the 2.8-second encoding and lock interval.
- Synchronize glyph animation, tile flashes, and gate audio with the variable dialing cycle lengths, including DHD resume timing.
- Separate connector colors from chevron colors; inactive connectors remain dim while selected chevrons use yellow outlines.
- Add six stripes along each side of the chevron clamps and narrow their inward-facing ends. Name the outer portion the clamp and the inner portion the jewel in the rendering code.
- Use a black console background and brighter yellow details, and label the glyph keyboard's dialing button ACTIVATE.

### Added

- Native Windows x64 and Linux x64 single-file builds after successful CI tests, with packaged preview checks and downloadable zip/tar archives retained for 14 days.

- GitHub Actions workflow for the locked Python 3.14 environment, headless test discovery, and preview rendering on pushes and pull requests.
- Regression checks for non-default RPM in both dialing behaviors and all address lengths, DHD resume, and abort continuity.

- Regression tests for cruising speed, smooth speed ramps, symbol alignment, and encoding timing.
- Eight program screenshots and an overview in `previews/`.
- Chevron reference photograph in `reference/Front_Face_SG1.jpg`.
