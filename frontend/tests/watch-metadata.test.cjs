const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'watch.html'), 'utf8');
const entities = [...html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)]
  .flatMap(([, raw]) => {
    const schema = JSON.parse(raw);
    return schema['@graph'] || [schema];
  });

// Provider evidence read on 2026-10-20 from YouTube's ytInitialPlayerResponse
// for https://www.youtube.com/watch?v=JysZLBTrdc4:
// videoDetails.lengthSeconds = "60"; microformat.playerMicroformatRenderer
// uploadDate/publishDate = "2026-10-13T11:44:41+05:30". The provider thumbnail
// https://i.ytimg.com/vi/JysZLBTrdc4/hqdefault.jpg returned HTTP 200 image/jpeg.
test('watch output publishes the verified video metadata alongside its player', () => {
  const videos = entities.filter(entity => entity['@type'] === 'VideoObject');
  assert.equal(videos.length, 1, 'serialize the VideoObject into the generated page');
  const video = videos[0];
  assert.equal(video.duration, 'PT1M');
  assert.equal(video.uploadDate, '2026-10-13T11:44:41+05:30');
  assert.deepEqual(video.thumbnailUrl, ['https://i.ytimg.com/vi/JysZLBTrdc4/hqdefault.jpg']);
  assert.equal(video.embedUrl, 'https://www.youtube-nocookie.com/embed/JysZLBTrdc4');
  assert.ok(html.includes(`<iframe src="${video.embedUrl}"`));
  assert.equal(Object.hasOwn(video, 'contentUrl'), false, 'a YouTube watch page is not a media-file URL');
  assert.ok(html.includes('rel="canonical" href="https://www.myrecon.xyz/watch.html"'));
  assert.match(html, /Watch the 60-second MyRecon product video/);
});

test('watch FAQ schema matches visible answers and keeps verification limits', () => {
  const faq = entities.find(entity => entity['@type'] === 'FAQPage');
  assert.ok(faq);
  for (const question of faq.mainEntity) {
    assert.ok(html.includes(`<summary>${question.name}</summary>`), question.name);
    assert.ok(html.includes(`<p>${question.acceptedAnswer.text}</p>`), question.name);
  }
  assert.match(html, /A matching handle is a public-profile lead/);
  assert.doesNotMatch(html, /2-minute|PT2M15S|1:15|1:45|email breach exposures with k-anonymity|Eliminating soft-404|returning verified public profile leads/);
});

test('watch page retains the existing live discovery routes', () => {
  for (const route of ['/username-checker.html', '/boost.html', '/browser.html', '/goal.html', '/directory.html']) {
    assert.ok(html.includes(`href="${route}"`), route);
    assert.ok(fs.existsSync(path.join(root, route.slice(1))), route);
  }
});
