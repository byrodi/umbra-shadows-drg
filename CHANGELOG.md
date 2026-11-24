# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-24

### Added

- Detailed settings are back. Open "Detailed settings" under Shadow quality to set each one by hand.
  Quality: headlamp shadows, soft edges, cave wall shadows, shadows in fog, shadow distance, how many hand flares
  and flare gun flares cast shadows and how far. Look: class colour, flare brightness, shadow strength and
  penumbra size.
- Shadow quality has a fifth choice, Custom. Changing a quality setting switches to Custom, and your values
  stay after a restart. Picking Low, Medium, High or Ultra again sets all quality settings to that level.
  The look settings stay as you set them.

### Changed

- The settings page now uses the game's fonts, colours, check boxes and sliders. Class colour moved into the
  detailed settings.
- Engineer flares give a softer red light (30% less red), so the scene no longer looks washed in red.

### Fixed

- No more small stutter once a second in long missions. Burnt-out flares stay on the ground until the mission ends,
  and the mod checked every one of them, and compared each flare with each other one, every second. With 200 flares
  that took 15 to 20 ms. Now the mod looks only at burning flares, and picks the nearest ones in one pass.
- Burnt-out flares near you no longer take a shadow away from a burning flare further off.
- Shadows of a flying or rolling flare no longer swing around: the shadow light stays at the flare's centre
  while it moves.
- The light of a flare gun flare no longer changes brightness when the flare goes out. It stays steady and then
  fades out over 3 seconds.

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

[unreleased]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/byrodi/umbra-shadows-drg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/byrodi/umbra-shadows-drg/releases/tag/v0.1.0
