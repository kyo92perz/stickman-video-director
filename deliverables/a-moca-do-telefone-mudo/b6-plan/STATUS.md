# A Moça do Telefone Mudo — B6 status

Decisions recorded from the user:
- Language: pt-BR narration. Caption profile is the existing locked `eiffel-v44-portrait-archivo-black-v1` (Archivo Black). All pt-BR glyphs (áéíóúâêôãõàç and capitals) are present in fonts/ArchivoBlack.ttf (checked with fontTools). The language is a user-directed deviation from the English-only portrait profile, recorded here per the caption policy. The engine is unchanged.
- Production: full (painted characters per view + painted worlds). Image generation approved.

Done:
- Narration master: ../audio-master/master-narration.wav (79.72 s), timing in ../audio-master/timing.json
- Story beats: story.json; portrait shot plan (9 shots): portrait-plan.json; captions.json with ESTIMATED timings (proportional to characters, must be realigned to the recording before approval)
- Style test: art/narrator-front.png (front view, cream canvas, not alpha-cut). Stick limbs and ink direction look right; not yet validated against the V44 standard.

Not done (blockers for render):
- Per-view painted packages (front, three_quarter, side) for narrator, Dona Eunice and the lady in white: body/head sprites with alpha, arm/leg sockets, cuffs, neck attachment, calibrated poses.
- Painted worlds: 1987 house, hallway, bedroom, city map.
- scene.py (puppet runtime), real word-level caption alignment, mix, preview/motion review.
- Renders take ~20 min each on this 2-CPU sandbox.
