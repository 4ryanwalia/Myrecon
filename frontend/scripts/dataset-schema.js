'use strict';
/* Dataset JSON-LD for articles that publish original, downloadable data.
 *
 * Why it exists: an AI answer or a search feature citing a measurement needs
 * to know what was measured, when, how, and where the raw files are. Article
 * markup has nowhere to put any of that, so original research reads to a
 * machine like any other blog post. Original data is the site's main source
 * of information gain over pages that already rank.
 *
 * Front matter in content/blog/<slug>.html opts in with a "dataset" object:
 *   name, description, temporalCoverage, measurementTechnique (strings),
 *   keywords, variableMeasured (string arrays),
 *   distribution: [{ url: "/assets/...", format: "text/csv" }]
 * A license is emitted only when the front matter states one; never assume it.
 */

const SITE = 'https://www.myrecon.xyz';

function datasetSchema(article) {
  const d = article.dataset;
  if (!d) return null;
  for (const field of ['name', 'description', 'temporalCoverage', 'measurementTechnique']) {
    if (typeof d[field] !== 'string' || !d[field].trim()) throw new Error(`${article.slug}: dataset.${field} is required`);
  }
  if (!Array.isArray(d.distribution) || !d.distribution.length) throw new Error(`${article.slug}: dataset.distribution needs at least one file`);
  const value = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    '@id': `${article.url}#dataset`,
    name: d.name,
    description: d.description,
    url: article.url,
    creator: { '@type': 'Organization', '@id': `${SITE}/#organization`, name: 'MyRecon', url: `${SITE}/` },
    datePublished: article.datePublished,
    dateModified: article.dateModified,
    temporalCoverage: d.temporalCoverage,
    isAccessibleForFree: true,
    measurementTechnique: d.measurementTechnique,
  };
  if (d.license) value.license = d.license;
  if (d.keywords?.length) value.keywords = d.keywords;
  if (d.variableMeasured?.length) value.variableMeasured = d.variableMeasured.map(name => ({ '@type': 'PropertyValue', name }));
  value.distribution = d.distribution.map(file => ({
    '@type': 'DataDownload',
    encodingFormat: file.format,
    contentUrl: file.url.startsWith('http') ? file.url : `${SITE}${file.url}`,
  }));
  return value;
}

module.exports = { datasetSchema };
