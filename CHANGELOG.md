# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-23

### Changed

- The settings page now has one Shadow quality choice (Low, Medium, High, Ultra) instead of a long list.
  Medium is the default. Your old hand-set values are replaced by the chosen level.
- Only the flares nearest to you cast shadows: 2 to 6 hand flares and up to 4 flare gun flares,
  depending on the level (Ultra: every hand flare). The others still light the cave. This keeps big fights smooth.

### Fixed

- Flare gun flares now really cast shadows; before, their light had none.
- Shadows of a flare no longer jump for up to a second after the flare stops rolling.
- The flare gun's light no longer switches back to the game's brightness for a moment.
- No more striped, jagged shadows on the Space Rig: soft shadows are now used only in missions.

## [0.2.0] - 2026-11-22

### Fixed

- A burnt-out flare no longer goes dark all at once: its light fades away over a few seconds.

## [0.1.0] - 2026-11-20

### Added

- Every flare lights all round and casts shadows of rocks, walls and bugs.
- Hand flares glow in the thrower's class colour; the flare gun keeps its own light.
- Your headlamp and your team mates' headlamps cast shadows.
- Far flare shadows fade out smoothly with the engine's own shadow fade.
- Settings page in Mod Hub.

[unreleased]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/byrodi/umbra-shadows-drg/releases/tag/v0.1.0
