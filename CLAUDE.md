# CLAUDE.md: vrajpatel105.github.io

Vraj Patel's portfolio. Plain HTML on GitHub Pages, deployed from `main`. No build step, no frameworks, no GitHub Actions.

## Ground rules

- **Keep the design.** `index.html` (the "BATCHER" design) is one self-contained file: inline CSS and JS, Google Fonts only. Add things only from its existing tokens and components; don't restyle it.
- **Never invent or change numbers or facts.** Use only what is already on the site, in the blog posts, or in Vraj's project READMEs. If the résumé and the site disagree, ask Vraj before changing either.
- **Do not touch `transformer-trace/`.** Check with `git diff --stat main -- transformer-trace/` (must be empty).
- **Light theme only:** no neon or glow, no blue/violet/cyan gradients, no black backgrounds. Text ≥ 12px, tap targets ≥ 44px, no horizontal scroll from 360px up, respect `prefers-reduced-motion`.
- **Plain HTML on Pages.** `.nojekyll` is present. Don't create a folder named `resume/` (it is in `.gitignore`, so git drops it).
- **Posts** (`paged-inference/`, `gpu-inference/`) share `assets/post.css` (tokens copied from `index.html`) and `assets/post.js` (reading progress + bar charts). Chart colours: `#b85f3e` = Vraj's implementation, `#3d6ea8` = baseline, grey `#9a978f` = unquantized reference. Every chart keeps its data table as the accessible twin. Keep post URLs and titles; the résumé and LinkedIn link to them.

## How the site finds files (no code edits needed)

The home page builds one file list for `media/`, `notes/` and `resume.pdf`:

1. On `*.github.io`: one call to `https://api.github.com/repos/VrajPatel105/vrajpatel105.github.io/git/trees/main?recursive=1`, cached in sessionStorage for 10 minutes (unauthenticated limit: 60/hour per visitor).
2. Fallback, and the source of file dates: `content.json` at the root, written by `scripts/build_content_index.py`. **Regenerate and commit it whenever `media/` or `notes/` change.**
3. Any failure falls back quietly to placeholders.

The `PROFILE_PHOTO`, `RESUME_URL` and `GALLERY` constants at the top of the page script are overrides. Left empty, they mean "use the folder".

### Folders, names and slugs

```
media/
  README.md                 naming rules + GPS privacy note
  my_photo.jpg              profile photo, About section, 4:5 frame (.jpg/.jpeg/.png/.webp)
  <anything>.pdf            résumé; if several, the newest by last commit date wins
  experience/<slug>.jpg     one photo per role, Experience → Photos tab, 4:3
  gallery/*.jpg             any number, any shape, "Off the keyboard" section
notes/
  ml/*.pdf                  Notes → Machine learning column
  dl/*.pdf                  Notes → Deep learning column
```

| Slug | Role |
|---|---|
| `gdms-capstone` | Senior Capstone, General Dynamics Mission Systems |
| `fleet-robotics` | ML Engineer Intern, Fleet Robotics |
| `bluetech-externship-2026` | Blue Tech externship, 2026 |
| `smast-research` | Research Software Engineering Intern, SMAST |
| `smast-data-science` | Data Science Intern, SMAST |
| `bluetech-externship-2025` | Blue Tech externship, 2025 (1st place) |

Gallery captions come from file names: `01-friday-tennis.jpg` → "Friday tennis". Camera names (`IMG_2034`, `PXL_…`) get no caption. Leading numbers set the order.

Résumé buttons (nav, hero, contact) link the newest PDF in `media/`, then `/resume.pdf`, then the GitHub profile. The static `href` is `https://vrajpatel105.github.io/resume.pdf`.

## Notes need no code

Drop PDFs into `notes/ml/` or `notes/dl/`. Title = file name without `.pdf` and without a leading order number (`01 Recurrent Neural Networks.pdf` → "Recurrent Neural Networks"); rows sort by file name, numbers compared numerically. A filter box appears past 10 notes. Then regenerate `content.json`.

## "Adjust the pictures"

When Vraj says this after uploading, do the following. The script is `scripts/process_photos.py` (needs `pip install Pillow pillow-heif`; pillow-heif is for iPhone HEIC).

1. **Survey:** `git pull`, then list everything new under `media/` (`git log --stat -5 -- media/`, `ls -R media`).
2. **Move misplaced files** into the right folder (`git mv`): the profile photo to `media/my_photo.<ext>`, role photos to `media/experience/`, everything else to `media/gallery/`. **Rename experience photos to their slug** (table above). If it's unclear which role a photo belongs to, ask.
3. **Look at each photo** (open it with the Read tool) to decide the crop: the profile at 4:5, experience photos at 4:3, framed on the subject (face/people, not the centre by default). Note the subject's centre as fractions of width/height.
4. **Process:**
   ```bash
   python3 scripts/process_photos.py --dry-run
   python3 scripts/process_photos.py --crop media/my_photo.jpg=0.5,0.35 --crop media/experience/fleet-robotics.jpg=0.45,0.5
   ```
   This fixes orientation, **strips all metadata including GPS**, converts to JPG, and resizes the long edge to at most **2000px (gallery), 1600px (experience), 1400px (profile)**. Gallery photos keep their shape. Look at the output again to confirm each crop.
5. **New résumé:** if a new PDF arrived in `media/`, rename it to `media/Vraj_Patel_Resume.pdf` (`git mv`, replacing the old one) and copy it over `/resume.pdf` so old links serve the latest version. Clear company-specific PDF metadata (e.g. a Title naming a company) with pypdf if present.
6. **Regenerate the index:** `python3 scripts/build_content_index.py`.
7. **Verify:** `python3 -m http.server` and check in a headless browser (Playwright is preinstalled) at 360, 768 and 1280px: the profile photo, the Photos tab and the lightbox from both the gallery and the Photos tab, gallery captions, no console errors, no horizontal overflow.
8. **Ship:** commit, push, open a PR and merge it into `main`. After Pages deploys (~1 minute), check https://vrajpatel105.github.io/.

Remind Vraj: phone photos carry GPS, and the originals stay in git history even after processing. Turn location off before exporting.

## Verify before merging any change

- Serve locally (`python3 -m http.server`) and check 360, 375, 768, 1024, 1280 and 1440px: no horizontal overflow, no console errors, no text under 12px, tap targets ≥ 44px, the sticky nav never covers section headings, "you are here" reads "08 / Notes" at the bottom.
- Links: notes PDFs, résumé, posts ↔ home page, images in posts.
- `git diff --stat main -- transformer-trace/` is empty.

## If the Pages deploy fails

GitHub Pages deploys `main` with its built-in "pages build and deployment" run. If the **build** job passes but **deploy** fails with "Deployment failed, try again later", the problem is on GitHub's side, not in the files. Re-run the failed jobs from the Actions tab. If the re-run sits in "queued" for a long time, merge the next change to `main` instead: every push starts a fresh deploy.
