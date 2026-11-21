const fs = require('node:fs');
const path = require('node:path');
const { validCase, comparisonSeries } = require('../assets/js/username-benchmark.js');

// The homepage draws two views of the same case. Keep individual observations
// in the linked evidence file so readers can download them when needed.
function buildUsernameChart(root = path.resolve(__dirname, '..')) {
  const data = JSON.parse(fs.readFileSync(path.join(root, 'data/username-benchmark.json'), 'utf8'));
  if (!validCase(data)) throw new Error('Invalid username benchmark evidence');
  const chart = {
    date: data.tools.myrecon.started_at_utc.slice(0, 10),
    sharedAddressCount: data.shared_address_count,
    full: comparisonSeries(data, 'full'),
    shared: comparisonSeries(data, 'shared'),
  };
  const file = path.join(root, 'index.html');
  const html = fs.readFileSync(file, 'utf8');
  const slot = /(<script type="application\/json" id="usernameCaseChartData">)[\s\S]*?(<\/script>)/;
  if (!slot.test(html)) throw new Error('Homepage username chart data slot is missing');
  const json = JSON.stringify(chart).replace(/</g, '\\u003c');
  const next = html.replace(slot, (_, open, close) => open + json + close);
  if (html !== next) fs.writeFileSync(file, next);
}

if (require.main === module) buildUsernameChart();
module.exports = { buildUsernameChart };
