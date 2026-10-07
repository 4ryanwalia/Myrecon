/* Rebuild original article explainers. Requires sharp and ffmpeg locally.
 * Published MP4, posters and WebVTT files are checked in; production does not
 * generate videos or require these authoring dependencies.
 */
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const media = JSON.parse(fs.readFileSync(path.join(root, 'content/blog-media.json'), 'utf8'));
const output = path.join(root, 'assets/media/blog');
const scratch = path.resolve(root, '../output/blog-media-authoring');
const escape = text => String(text).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'})[char]);

function lines(text, maxChars) {
  const result = [];
  let line = '';
  for (const word of text.split(/\s+/)) {
    if (line && `${line} ${word}`.length > maxChars) { result.push(line); line = word; }
    else line = line ? `${line} ${word}` : word;
  }
  if (line) result.push(line);
  return result;
}

function frame(record, index) {
  const [heading, text] = record.steps[index];
  const titleLines = lines(record.title, 47);
  const bodyLines = lines(text, 56);
  const title = titleLines.map((line, i) => `<text x="72" y="${155 + i * 46}" font-size="38" font-weight="700">${escape(line)}</text>`).join('');
  const paragraph = bodyLines.map((line, i) => `<text x="74" y="${385 + i * 44}" font-size="32" fill="#d3d9d6">${escape(line)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
    <rect width="1280" height="720" fill="#152621"/><circle cx="1160" cy="85" r="220" fill="#203b31"/><circle cx="1200" cy="740" r="220" fill="#1c332b"/>
    <g font-family="Arial, sans-serif" fill="#f7f7f4"><text x="72" y="65" font-size="20" letter-spacing="3">MYRECON / PUBLIC-SOURCE RESEARCH</text>
    ${title}<text x="72" y="285" font-size="22" fill="#aec8b8">STEP ${index + 1} OF 4</text><text x="72" y="332" font-size="35" font-weight="700">${escape(heading)}</text>
    ${paragraph}<text x="74" y="662" font-size="19" fill="#bdc9c2">Illustrative workflow · Read the article for sources and limits</text>
    ${record.steps.map((_, i) => `<rect x="${72 + i * 290}" y="590" width="${i === index ? 272 : 265}" height="7" rx="3.5" fill="${i <= index ? '#9cc2a6' : '#3a5147'}"/>`).join('')}
    </g></svg>`;
}

function timestamp(seconds) { return `00:${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}.000`; }

async function main() {
  fs.mkdirSync(output, {recursive:true});
  fs.mkdirSync(scratch, {recursive:true});
  for (const [slug, record] of Object.entries(media)) {
    const work = path.join(scratch, slug);
    fs.mkdirSync(work, {recursive:true});
    for (let i = 0; i < record.steps.length; i++) {
      const png = await sharp(Buffer.from(frame(record, i))).png().toBuffer();
      fs.writeFileSync(path.join(work, `${i}.png`), png);
      if (i === 0) await sharp(png).jpeg({quality:85}).toFile(path.join(output, `${slug}-poster.jpg`));
    }
    const files = Array.from({length:4}, (_, i) => path.join(work, `${i}.png`));
    const args = ['-hide_banner', '-loglevel', 'error', '-y'];
    for (const file of files) args.push('-loop', '1', '-framerate', '12', '-t', '8', '-i', file);
    const filters = files.map((_, i) => `[${i}:v]format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st=7.75:d=0.25[v${i}]`).join(';') + ';[v0][v1][v2][v3]concat=n=4:v=1:a=0[v]';
    args.push('-filter_complex', filters, '-map', '[v]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p', '-r', '12', '-movflags', '+faststart', '-an', path.join(output, `${slug}.mp4`));
    execFileSync('ffmpeg', args, {stdio:['ignore','pipe','pipe']});
    const captions = 'WEBVTT\n\n' + record.steps.map(([heading, text], i) => `${i + 1}\n${timestamp(i * 8)} --> ${timestamp((i + 1) * 8)}\n${heading}\n${text}\n`).join('\n');
    fs.writeFileSync(path.join(output, `${slug}.vtt`), captions);
    console.log(`[media] ${slug}: 32s MP4, poster and captions`);
  }
}
main().catch(error => {console.error(error.message); process.exitCode=1;});
