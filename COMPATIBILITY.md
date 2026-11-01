# Monochrome scope and compatibility — 0.4.0 release candidate

The following exact owner-supplied firmware images have implemented resource profiles and pass software preservation/export checks with all four themes. None of the new cross-family outputs has been tested on actual iPod hardware.

| Hardware family shown in preview | Original IPSW | Internal payload | Display | Status |
| --- | --- | --- | --- | --- |
| iPod 1st / 2nd generation | iPod_1.1.5.ipsw | Firmware-1.1.5 | 160 × 128 | Software-validated; no device test |
| iPod 3rd generation | iPod_2.2.3.ipsw | Firmware-2.2.3 | 160 × 128 | Software-validated; no device test |
| iPod 4th generation, monochrome | iPod_4.3.1.1.ipsw | Firmware-4.3.1.1 | 160 × 128 | Software-validated; earlier private v1 user-reported working |
| iPod mini 1st generation | iPod_3.1.4.1.ipsw | Firmware-3.2.6.1 | 138 × 110 | Software-validated; no device test |
| iPod mini 2nd generation | iPod_7.1.4.1.ipsw | Firmware-7.2.6.1 | 138 × 110 | Software-validated; no device test |

Identification uses the exact firmware payload SHA-256, the internal payload name, and manifest FamilyID/UpdaterFamilyID. Renaming the IPSW does not change identification. The Mini's outer and inner version-like filenames differ; the app validates the actual internal name. Gen 1 and Gen 2 share this firmware family, so the app shows that shared family instead of claiming it can distinguish a connected device. The app does not inspect connected hardware.

Each profile has its own font allocation data, menu row/inset offsets, picture locations, protected resources, and checksum range. Gen 1/2 and Gen 3 checksums begin at their partition offset; the later supplied images begin 512 bytes later. Those formats are not patched with the 4G resource map. Mini previews use a smaller screen and compact case; the Gen 3 preview shows its separate button row. Device views are original vector illustrations with model-specific proportions and controls; they are not product photographs or OS emulation. Gen 1/2 share their front control arrangement. Mini uses a representative silver finish because firmware cannot identify case color.

The same theme names and font-size settings apply across these profiles. All original firmware pictures, including icons and animations, remain unchanged. No firmware instruction patches are introduced. Playback, storage, commands, and native input handling remain the original firmware's responsibility; preserving their bytes is not proof of unchanged runtime behavior after UI changes.

These exact hashes are recorded in `device-profiles.json`; generated payload baselines are in `profile-baselines.json`. Other firmware versions, family variants such as an unprovided Mini family-6 image, color/photo iPods, nano, video/classic, shuffle, and iPod touch are not supported. Different images remain rejected until their own profiles are implemented and tested. No Apple IPSWs are included or downloaded by the app.

Hardware facts: [Apple mini specifications](https://support.apple.com/en-tm/112317), Rockbox's configuration headers for [1G/2G](https://github.com/Rockbox/rockbox/blob/master/firmware/export/config/ipod1g2g.h), [3G](https://github.com/Rockbox/rockbox/blob/master/firmware/export/config/ipod3g.h), [4G](https://github.com/Rockbox/rockbox/blob/master/firmware/export/config/ipod4g.h), [mini 1G](https://github.com/Rockbox/rockbox/blob/master/firmware/export/config/ipodmini1g.h), and [mini 2G](https://github.com/Rockbox/rockbox/blob/master/firmware/export/config/ipodmini2g.h). Firmware profile implementation and validation are local results, not conclusions drawn from Rockbox support.

Release 0.4.0 final QA uses all five restored owner-supplied original IPSW archives, with original ZIP integrity, exact payload SHA-256 and manifest identities verified. No firmware fixtures are shipped. See migration-verification.json and packaged-app-checks.json.
