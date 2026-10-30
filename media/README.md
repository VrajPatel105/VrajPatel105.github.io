# media/: photos and résumé for the site

Upload files here with **Add file → Upload files**. The home page picks them up on its own; no code changes needed.

> **Privacy first.** Phone photos carry your GPS location in their metadata. Anything uploaded to this public repo stays in its git history, even after the photo is processed or deleted. **Turn location off when you export a photo, before you upload it.**

| What | Where | Name |
|---|---|---|
| Profile photo (About) | `media/` | `my_photo.jpg` (`.jpeg`, `.png`, `.webp` also work) |
| Résumé | `media/` | any `*.pdf`; if there are several, the most recently committed one wins |
| One photo per role (Experience → Photos) | `media/experience/` | the role's slug, see [experience/README.md](experience/README.md) |
| Gallery ("Off the keyboard") | `media/gallery/` | anything, see [gallery/README.md](gallery/README.md) |

After uploading, ask Claude Code to "adjust the pictures". It fixes orientation, strips metadata, resizes, crops the profile to 4:5 and experience photos to 4:3, renames, and copies a new résumé over `/resume.pdf`. The steps are in `CLAUDE.md`.
