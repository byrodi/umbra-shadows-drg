# Umbra Shadows: mod.io page text

Name: Umbra Shadows
Summary (mod.io limit 250 characters):
Every flare casts round, soft shadows in its class colour; headlamps cast shadows too. Far shadows fade out smoothly, so a cave full of flares stays playable. Client-side: other players do not need it.

Tags: Visual. The approval category (Verified / Approved / Sandbox) is decided by the DRG mod reviewers, not
by the author; Umbra is client-side only and changes no gameplay.

## Description

**Umbra Shadows** gives the caves real shadows.

- **Every flare lights all round.** Rocks, stalactites and bugs throw shadows in every direction, like from
  a real flame, instead of the game's three narrow beams.
- **Class colours.** Hand flare light takes the colour of the dwarf who threw it: Driller yellow, Engineer red,
  Gunner green, Scout blue. Coloured flares are as bright as white ones. The flare gun keeps its own light.
- **Headlamp shadows.** Your headlamp and your team mates' headlamps cast shadows.
- **The flare gun** gets the same light; a flare stuck in a wall lights the cave, not just the wall.
- **Cave walls cast shadows** again (Mod Hub hides terrain shadows by default).

### Built to keep your frame rate

Shadows cost GPU time, so Umbra limits them where you cannot see them:

- Far flare shadows **fade out smoothly** with distance and are not drawn at all (the engine's own shadow
  fade; no popping, no flares switching on and off).
- Flare shadow maps are half size; the game's own three shadow beams per flare are turned off.
- Shadows in volumetric fog are off unless you turn them on.
- No per-frame scripts.

If you need more FPS, lower **Shadow distance** on the Umbra Shadows page in Mod Hub.

### Settings (Mod Hub, optional)

Enabled, own / team headlamp shadows, soft penumbra, cave walls cast shadows, light shafts in fog,
shadow distance, flare and flare gun shadow range, class colour, flare brightness, flare shadow strength,
penumbra size, shadow resolution. Everything applies at once in a mission. Without Mod Hub the defaults are used.

### Compatibility

- Client-side and visual only: other players do not need it.
- Made to run next to Advanced Darkness, Pretty Flashlights, Better Post Processing and Mod Hub.
- **Do not use together with "Shadows!"**: both change flare lights; Shadows! replaces the flares, so
  Umbra cannot work on them.

### Known limits

- Your own dwarf does not cast a shadow from your own headlamp (it would block the lamp).
- Point light shadows have no contact-hardening penumbra in this engine; flare shadow edges are soft
  from the smaller shadow map.
