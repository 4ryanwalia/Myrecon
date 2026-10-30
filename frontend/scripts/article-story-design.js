/* Shared article presentation. Source descriptions remain the factual record. */
const photo = 'https://images.unsplash.com/photo-1564697259644-03cd5e7363fa?auto=format&fit=crop&w=1200&q=80';
const credit = '<a href="https://unsplash.com/photos/person-using-laptop-mJ6E0ZQDMQ8" target="_blank" rel="noopener">Photo: Logan Jeffrey / Unsplash</a> · Context photograph';
function designArticle(html, route) {
  // Remove the old generated filler, including copies produced by build-blog.
  html = html.replace(/<figure class="(?:editorial-photo|blog-photo)"[\s\S]*?<\/figure>/g, '');
  if (html.includes('class="story-feature"') || html.includes('class="story-photo"')) return html;
  const breach = /class="article breach-article(?: cf-article)?"/.test(html);
  const image = `<figure class="story-photo"><img src="${photo}" alt="A person working at a laptop beside a desktop monitor" width="1200" height="800" decoding="async" ${breach ? 'fetchpriority="high"' : 'loading="lazy"'}><figcaption>${credit}</figcaption></figure>`;
  if (breach) {
    // Logos are often tiny marks on large white canvases; the article title identifies the service.
    html = html.replace(/<img class="bx-logo"[^>]*>/g, '');
    const source = html.match(/<div class="bx-source">\s*<p>([\s\S]*?)<\/p>/)?.[1] || html.match(/<h2 id="story">[\s\S]*?<\/h2>\s*<p>([\s\S]*?)<\/p>/)?.[1] || '';
    const opening = source.replace(/<[^>]*>/g, '').split(/(?<=\.)\s+/)[0];
    const doubleCounter = route === 'breaches/doublecounter.html';
    const emailCollection = route === 'breaches/linkedinscrape.html' || route === 'breaches/thepostmillennial.html';
    const title = doubleCounter ? 'A server safeguard. An exposed analytics tool.' : emailCollection ? 'Behind the collected records' : 'Behind the exposed accounts';
    const intro = doubleCounter ? 'Double Counter helps protect Discord servers. Its breach account points to a vulnerability in Metabase, an analytics tool. The published data connected email addresses with Discord usernames.' : opening;
    const feature = `<section class="story-feature" aria-label="Breach briefing"><div class="story-opening"><span class="story-eyebrow">THE HUMAN IMPACT</span><h2>${title}</h2><p>${intro}</p><a class="story-jump" href="#story">Follow the story <span aria-hidden="true">↓</span></a></div>${image}</section>`;
    html = html.replace(/(<header class="bx-head">[\s\S]*?<\/header>)/, `$1${feature}`);
    html = html.replace(/<ul class="bx-classes">([\s\S]*?)<\/ul>/, (_, items) => `<div class="story-exposure">${items.replace(/<li><b>([\s\S]*?)<\/b><span>([\s\S]*?)<\/span><\/li>/g, '<details><summary>$1<span aria-hidden="true">+</span></summary><p>$2</p></details>')}</div>`);
    html = html.replace(/<ol class="bx-actions">([\s\S]*?)<\/ol>/, (_, items) => `<fieldset class="story-checklist"><legend>Your next steps</legend><p>Tick off the actions you have taken. Progress lasts while this page is open.</p>${items.replace(/<li>([\s\S]*?)<\/li>/g, '<label><input type="checkbox"><span>$1</span></label>')}<output aria-live="polite">0 actions completed</output></fieldset>`);
    if (doubleCounter) {
      html = html.replace(/(<fieldset class="story-checklist">)[\s\S]*?(<\/fieldset>)/, '$1<legend>Your next steps</legend><p>Tick off the actions you have taken. Progress lasts while this page is open.</p><label><input type="checkbox"><span>Read the original disclosure to understand which records were affected.</span></label><label><input type="checkbox"><span>Review unexpected Discord messages and emails. Open the service directly instead of following a login link.</span></label><label><input type="checkbox"><span>Review your public profile for personal details you no longer want to share.</span></label><output aria-live="polite">0 actions completed</output>$2');
      html = html.replace('The address becomes a confirmed, active target, expect more phishing, better aimed.', 'An exposed address can be used for targeted phishing. A familiar service name does not make a message trustworthy.').replace('Where the account was used, which narrows a person down further than most people expect.', 'The account describes countries and postcodes for a small subset of paying subscribers. It does not establish precise or live locations.').replace('Turns an anonymous address into an identified person, which is what makes targeted phishing possible.', 'Names appeared in a small subset of subscriber records and may make a fraudulent message more convincing.').replace('A handle links this account to every other place the same handle is used.', 'Discord usernames can provide leads to other public profiles. A matching handle alone does not prove shared ownership.');
      html = html.replace('<h2 id="story">The story behind the breach</h2>', '<h2 id="story">How a Discord handle became an email trail</h2><p class="story-context">The important connection is between an account and its contact details. A message using your Discord handle may feel familiar; that familiarity is not proof that the sender is legitimate.</p>');
      html = html.replace('<h2 id="how">How did it happen?</h2>', '<h2 id="how">01 / The reported entry point</h2>').replace('<h2 id="motive">What was the motive?</h2>', '<h2 id="motive">02 / What the record does not tell us</h2>').replace('<h2 id="outcome">What was the outcome?</h2>', '<h2 id="outcome">03 / What left the service</h2>');
    }
  } else {
    // A supporting photo should never interrupt a title and its metadata.
    if (html.includes('<nav class="blog-toc"')) html = html.replace('<nav class="blog-toc"', `${image}<nav class="blog-toc"`);
    else html = html.replace(/(<article\b[\s\S]*?)(<h2\b)/, `$1${image}$2`);
  }
  if (!html.includes('/assets/css/article-story.css')) html = html.replace('</head>', '<link rel="stylesheet" href="/assets/css/article-story.css">\n</head>');
  if (breach && !html.includes('/assets/js/article-story.js')) html = html.replace('</body>', '<script src="/assets/js/article-story.js" defer></script>\n</body>');
  return html;
}
module.exports = { designArticle };
