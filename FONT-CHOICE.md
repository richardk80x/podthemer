# Enlarge font selection

The original private theme used SF Compact Text Semibold at 13px for main text. The public theme now uses **Inter Tight Semibold (weight 600), 13px**, with 11/10/11px secondary variants. No SF font or SF bitmap patch is distributed.

Compared locally at 13px and the builder’s one-bit threshold: Inter Semibold, Inter Tight Semibold, and Roboto Condensed Semibold, against the earlier SF Compact reference. Inter Tight offered a compact width close to the reference, a similar UI sans-serif feel, and complete Latin letters/digits at the required size. This is a design judgment among the tested candidates, not a claim of an exact match. Font choice is fixed; no font controls were added.

For four representative strings, using firmware-style per-glyph advances, the reference widths were 205/222/231/208 pixels; Inter Tight was 201/213/231/202; Inter was 207/218/238/212; Roboto Condensed was 178/189/195/182. Letterforms and spacing differ from SF Compact. The reference font and its private comparison images stay outside release packages.

Without column sharing, Inter Tight’s 13px glyph atlas would exceed the fixed allocations. Only Enlarge uses lossless sharing of identical contiguous column runs. Each glyph still refers to a contiguous rectangle, has its intended advance/bearing, and round-trips to exactly the same pixels. At 13px the main atlas uses 1236/1248 columns on Gen 1/2 and Gen 3, and 3077/3136 on 4G and both Minis. Unsupported glyphs are preserved from the supplied firmware; no preserved Apple glyphs are bundled. Enlarge fails if a requested size cannot fit.

Inter Tight is supplied unmodified under the SIL OFL 1.1, with the complete upstream notice in assets/fonts/INTER-TIGHT-OFL.txt. Source: [Google Fonts Inter Tight](https://github.com/google/fonts/tree/main/ofl/intertight). The [Inter project](https://rsms.me/inter/) describes the related family’s text-oriented designs. The exact source SHA-256 is recorded in the raster cache and build reports.

Software validation verifies the font cells, allocation bounds and stored pixels. Readability and physical-screen appearance still need testing on each supported iPod.
