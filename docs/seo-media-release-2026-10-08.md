# Article media release

The twelve articles published on 8 October 2026 each receive a relevant editorial photo and a distinct four-step, 32-second silent explainer. Native video controls, English WebVTT captions and an expandable text transcript support playback and accessible reading. Videos load on demand. Matching Article/VideoObject metadata and twelve image/video sitemap entries describe the visible media.

The homepage is restored byte for byte from commit `92ff85bb`. The site build preserves the checked-in homepage, and footer enhancement skips it. Tool JavaScript, tool styles, backend code and lookup behavior are unchanged by this follow-up.

## Assets and authoring

Three photos were generated with the built-in image-generation tool, compressed to 1600 x 900 WebP and reused by relevant topic. Visible captions identify them as AI-created editorial illustrations. Original PNG outputs are preserved in `C:\Users\91966\.codex\generated_images\01a117d9-19c8-7a71-92af-c464f20df905`.

- `frontend/assets/img/blog/research-workspace.webp`: a photorealistic public-source research desk with laptop, smartphone, camera and notebook, natural side light, restrained green and warm neutral colors, a realistic editorial composition with space around the devices; no readable personal data, brand logos or people.
- `frontend/assets/img/blog/social-profile-research.webp`: a photorealistic smartphone displaying an abstract social-profile layout beside a laptop on a clean research desk, subtle green and neutral palette, natural light and realistic device detail; no readable names, usernames, personal information, brand logos or people.
- `frontend/assets/img/blog/privacy-workspace.webp`: a photorealistic privacy-review desk with a closed laptop, face-down smartphone and notebook, calm natural light, restrained green and neutral colors and a realistic editorial composition; no readable personal information, brand logos or people.

These are the editorial prompt briefs for the three images. They depict illustrative workspaces rather than product screenshots or real investigations.

`frontend/content/blog-media.json` contains the exact titles, descriptions, four-step scripts, photo choices and creation timestamps. `frontend/scripts/create-blog-media.js` authors original video frames with Sharp and encodes MP4s with FFmpeg. The checked-in MP4, JPEG posters and VTT files are in `frontend/assets/media/blog`. Production builds consume those files without requiring authoring dependencies. All twelve videos are 1280 x 720 H.264 with a duration of 32 seconds.

## Verification

- Production static build: 194 canonical sitemap URLs, including twelve image and twelve video records.
- Focused publication and discovery suite: 22 passing tests.
- Browser verification: fifteen routes at 375px and 1280px, including loaded photos, actual playback of all twelve videos, captions, transcripts and layout checks.
- Homepage byte equality and unchanged tool/backend paths are asserted by the publication tests.

The repository's separate backend CI failures were already present in the preceding release and are documented in `seo-release-2026-10-08.md`. These article changes do not fix them. Search ranking, indexing and AI citation placement are provider decisions.
