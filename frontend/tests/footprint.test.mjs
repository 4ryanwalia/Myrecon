import test from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {caseFile, edition, provesAnswer, sourceUrl} from '../assets/footprint/mysteries.mjs';
import {graph, pathBetween, nearby} from '../assets/footprint/evidence.mjs';

test('weekly sources, answers and archive links stay bound to their edition', () => {
  const sunday = edition(new Date('2026-11-22T23:59:59Z'));
  const monday = edition(new Date('2026-11-23T00:00:00Z'));
  assert.notEqual(sunday.index, monday.index);
  assert.equal(edition(new Date('2026-11-23T00:00:00Z'), sunday.week).index, sunday.index);
  assert.equal(edition(new Date('2026-11-23T00:00:00Z'), '2027-02-01').index, monday.index);
  for (let i = 0; i < 8; i++) {
    const c = caseFile(i);
    assert.equal(provesAnswer(c, String(c.maker), sourceUrl(c, c.proofPage)), true);
    assert.equal(provesAnswer(c, String(1 - c.maker), sourceUrl(c, c.proofPage)), false);
    assert.equal(provesAnswer(c, String(c.maker), sourceUrl(c, 'a')), false);
    assert.equal(provesAnswer(c, String(c.maker), sourceUrl(caseFile((i+1)%8), 'credits')), false);
  }
});

test('removing one public field preserves an alternate path; matching handles alone give no edge', () => {
  const urlA = 'https://github.com/sample', urlB = 'https://dev.to/sample', portfolio = 'https://example.org/work';
  const a = {url: urlA, platform: 'GitHub', handle: 'sample', links: [{label: 'website', url: portfolio}]};
  const b = {url: urlB, platform: 'DEV', handle: 'sample', links: [{label: 'GitHub', url: urlA}, {label: 'website', url: portfolio}]};
  const g = graph([a, b]);
  assert.deepEqual(pathBetween(g.edges, urlA, urlB, g.edges[1]), [urlA, portfolio, urlB]);
  assert.equal(pathBetween(g.edges.slice(0, 2), urlA, urlB, g.edges[1]), null);
  assert.deepEqual(graph([{...a, links: []}, {...b, links: []}]).edges, []);
  assert(nearby('orb_it').includes('orbit'));
});

test('all five tools work on a phone viewport and only explicit scrapbook saves persist', async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}, timezoneId: 'Asia/Kolkata'});
    const errors = [], requests = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.route('**/*', async route => {
      const u = new URL(route.request().url());
      if (u.hostname === 'www.myrecon.xyz') {
        const filename = u.pathname === '/footprint' ? 'index.html' : u.pathname.split('/').pop();
        const path = fileURLToPath(new URL('../assets/footprint/' + filename, import.meta.url));
        const mime = filename.endsWith('.mjs') ? 'application/javascript' : filename.endsWith('.css') ? 'text/css' : 'text/html';
        return route.fulfill({path, contentType: mime});
      }
      requests.push(u);
      let status = 200, json;
      if (u.hostname === 'api.github.com' && u.pathname === '/users/orbit') {
        json = {login:'orbit', created_at:'2014-03-02T12:00:00Z', bio:'Tiny games', blog:'https://sample.test'};
      } else if (u.hostname === 'api.github.com' && (u.pathname.endsWith('/repos') || u.pathname.startsWith('/search'))) {
        const rows = [{owner:{login:'orbit'}, html_url:'https://github.com/orbit/maze', name:'Maze', created_at:'2014-01-02T12:00:00Z'}];
        json = u.pathname.endsWith('/repos') ? rows : {items: rows};
      } else if (u.hostname === 'dev.to' && u.searchParams.get('url') === 'orbit') {
        json = {username:'orbit', joined_at:'Mar 2, 2014', summary:'An illustrated journal', github_username:'orbit', website_url:'https://sample.test/'};
      } else if (u.hostname === 'dev.to' && u.pathname === '/api/articles') json = [];
      else if (u.hostname === 'hacker-news.firebaseio.com') { status = 503; json = {}; }
      else { status = 404; json = {}; }
      return route.fulfill({status, json, headers: {'Access-Control-Allow-Origin':'*'}});
    });
    await page.goto('https://www.myrecon.xyz/footprint');
    const button = name => page.getByRole('button', {name, exact:true});
    const results = page.locator('#results');
    await page.getByLabel('Your old handle').fill('orbit');
    await page.getByLabel('Year').fill('2014');
    await button('Find public traces').click();
    await page.getByRole('heading', {name:'Timeline for @orbit'}).waitFor();
    assert.match(await results.innerText(), /2014-03-02 · DEV/);
    assert.match(await results.innerText(), /Hacker News · inconclusive/);
    assert.equal(await results.locator('article').first().getByRole('heading').innerText(), 'Maze');
    await button('Save recognized find').first().click();
    await page.getByRole('link', {name:'Recognition game',exact:true}).click();
    await button('Find my clues').click();
    await button('I recognize it').click();
    await button('Keep in recap').click();
    await button('Unsure / skip').click(); await button('Next clue').click();
    await button('Unsure / skip').click(); await button('View recap').click();
    assert.equal(await results.locator('.record').count(), 1);
    await page.getByRole('link', {name:'Account links',exact:true}).click();
    await button('Find my profiles').click();
    await page.getByRole('checkbox', {name:'GitHub @orbit',exact:true}).check();
    await page.getByRole('checkbox', {name:'DEV @orbit',exact:true}).check();
    await page.getByLabel('Public link to hide').selectOption({index:3});
    assert.match(await results.innerText(), /Still connected via/);
    await page.getByRole('link', {name:'Handle tryout',exact:true}).click();
    await page.getByLabel('First handle').fill('orb_it'); await page.getByLabel('Second handle').fill('orbit');
    await page.getByLabel('Third handle').fill('orbitpress');
    await button('Compare handles').click(); await page.getByRole('heading', {name:'@orbitpress',exact:true}).waitFor();
    assert.match(await results.innerText(), /Potential spelling confusion/);
    assert.match(await results.innerText(), /Inconclusive/);
    assert.match(await results.innerText(), /No public profile returned/);
    const count = requests.length;
    await page.goto('https://www.myrecon.xyz/footprint?week=2026-11-16#mystery');
    // Fix the clock so this test also runs before the first published edition.
    await page.clock.install({time: new Date('2026-11-18T12:00:00Z')}); await page.reload();
    await button('Start mystery').click(); await button('Night Arcade profile').click();
    await button('Use this source').click(); await page.getByLabel('Which profile made it?').selectOption('0');
    await button('Submit answer').click(); await page.getByText(/Look for the page/).waitFor();
    await button('Moon Orchard · studio journal').click();
    await button('Moon Orchard · release credits').click(); await button('Use this source').click();
    await button('Submit answer').click(); await button('Share my time').waitFor();
    assert.equal(requests.length, count);
    await page.getByRole('link', {name:/My scrapbook/}).click();
    assert.equal(await results.locator('article').count(), 1);
    await button('Remove from scrapbook').click(); await page.reload();
    await page.getByText(/Your scrapbook is empty/).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});
