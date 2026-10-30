# vrajpatel105.github.io

Personal site and writing by **Vraj Patel**, live at https://vrajpatel105.github.io/.

All content (the projects, the measurements, the Transformer implementation, the shape trace, the diagrams, and the writing) was researched, built, and authored by me. Site structure, HTML/CSS, and deployment were done with the help of [Claude](https://claude.ai) (Anthropic), which also appears as a contributor in the commit history for that reason.

## Structure

```
index.html                 home page (one self-contained file)
resume.pdf                 latest résumé (kept in sync with media/)
content.json               file index snapshot, written by scripts/build_content_index.py
media/                     photos and résumé, uploaded through GitHub (see media/README.md)
  my_photo.jpg             profile photo
  *.pdf                    résumé
  experience/<slug>.jpg    one photo per role
  gallery/*.jpg            "Off the keyboard" photos
notes/ml/, notes/dl/       study notes as PDFs, listed automatically
paged-inference/           post: Building a paged inference engine from scratch
gpu-inference/             post: Building a GPU inference stack from scratch
transformer-trace/         post: I Built a Transformer From Scratch (shape trace)
assets/post.css, post.js   shared styles and charts for the posts
scripts/                   build_content_index.py, process_photos.py
CLAUDE.md                  conventions for Claude Code sessions
```

## Adding things

Upload with **Add file → Upload files** on GitHub. Nothing needs a code change.

- **Photos:** profile photo as `media/my_photo.jpg`; one photo per role in `media/experience/` named by slug (listed in `media/experience/README.md`); anything else in `media/gallery/`. **Turn location off when exporting.** Photos keep their GPS data otherwise, and the repo history is public. Then ask Claude Code to "adjust the pictures" (resize, crop, strip metadata; see `CLAUDE.md`).
- **Notes:** drop PDFs into `notes/ml/` or `notes/dl/`. `03 Attention.pdf` is listed as "Attention", in file-name order.
- **Résumé:** upload a PDF to `media/`. The Résumé buttons link the newest one. Copy it over `/resume.pdf` too so old links stay current.

After adding files locally, run `python3 scripts/build_content_index.py` and commit `content.json`. The live site reads the GitHub API directly and uses that file as a fallback and for dates.

## Posts

- [Building a paged inference engine from scratch, and measuring it honestly](paged-inference/)
- [Building a GPU inference stack from scratch, and measuring it honestly](gpu-inference/)
- [I Built a Transformer From Scratch. Here's the Shape Trace Nobody Shows You.](transformer-trace/index.html)

## Stack

Plain HTML, CSS and a little JavaScript. No build step. Hosted on GitHub Pages.
