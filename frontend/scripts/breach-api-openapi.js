const text = { type: "string" };
const date = { type: "string", format: "date" };
const url = { type: "string", format: "uri" };
const count = { type: "integer", format: "int64", minimum: 0 };
const flag = { type: "boolean" };
const slug = { type: "string", pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$" };
const names = { type: "array", items: text };
const ref = name => ({ $ref: `#/components/schemas/${name}` });
const array = item => ({ type: "array", items: item });
const object = (properties, required = Object.keys(properties)) => ({ type: "object", properties, required });

function buildOpenApi(site, apiVersion) {
  const common = {
    api_version: { type: "integer", const: apiVersion },
    generated: { ...date, description: "UTC date of the MyRecon build that wrote this file." },
    documentation: url,
    licence: text,
  };
  const catalogue = { ...common, attribution: ref("BreachAttribution") };
  const read = (operationId, summary, schema) => ({
    get: {
      operationId,
      summary,
      responses: {
        "200": { description: summary, content: { "application/json": { schema: ref(schema) } } },
      },
    },
  });
  const incident = read("getBreach", "Read a single incident by its catalogue slug", "BreachResponse");
  incident.get.parameters = [{
    name: "slug", in: "path", required: true,
    description: "Use the slug returned by the catalogue.",
    schema: slug, example: "mckesson",
  }];
  incident.get.responses["404"] = {
    description: "No file exists for this slug.",
    content: { "text/html": { schema: text } },
  };

  const breach = {
    slug, name: text, title: text, domain: { type: ["string", "null"] },
    breach_date: date,
    added_date: { type: "string", format: "date-time", description: "When the upstream source added the incident." },
    accounts: { ...count, description: "Upstream count for this incident. Check count_unit when present." },
    severity: { type: "integer", minimum: 0, maximum: 100, description: "MyRecon’s score based on the published data categories." },
    band: text, verified: flag, sensitive: flag, stealer_log: flag, data_classes: names,
    summary: text, logo: { type: ["string", "null"], format: "uri" }, url,
  };
  const breachDetails = {
    count_unit: { type: "string", examples: ["unique_email_addresses"] },
    data_provider: { type: ["string", "null"] },
    scale_line: { type: ["string", "null"] },
    actions: names,
    fields: array(object({ name: text, why: text })),
    story: object({ background: names, how: names, motive: names, outcome: names, editorial: names }),
    check_targets: array(object({ name: text, breach_date: date, match_year: flag }, ["name", "breach_date"])),
  };

  return {
    openapi: "3.1.1",
    info: {
      title: "MyRecon Public Data API",
      version: String(apiVersion),
      description: "Keyless GET access to MyRecon’s selected archive of public breach metadata and original case-file index. The archive carries attribution to Have I Been Pwned. Refer to each feed’s licence for reuse terms.",
    },
    servers: [{ url: `${site}/data/v${apiVersion}` }],
    externalDocs: { description: "Examples and attribution requirements", url: `${site}/developers.html` },
    paths: {
      "/index.json": read("getIndex", "Discover the public feeds and API description", "Discovery"),
      "/breaches.json": read("listBreaches", "Read the MyRecon breach catalogue", "BreachCatalogue"),
      "/breaches/{slug}.json": incident,
      "/latest.json": read("listLatestBreaches", "Read the most recently added catalogue entries", "LatestBreaches"),
      "/case-files.json": read("listCaseFiles", "Read the original case-file index", "CaseFileIndex"),
      "/stats.json": read("getStats", "Read aggregate archive counters", "Stats"),
    },
    components: {
      schemas: {
        BreachAttribution: object({
          required: flag, source: text, source_url: url, distributor: text, distributor_url: url, licence: url, notice: text,
        }),
        CaseFileAttribution: object({ required: flag, author: text, author_url: url, notice: text }),
        Breach: object({ ...breach, ...breachDetails }, Object.keys(breach)),
        CaseFile: object({
          slug, url, headline: text, subject: text, description: text,
          occurred: { ...text, description: "Editorial date label, which can be a range or approximation." },
          disclosed: { ...text, description: "Editorial disclosure date label." },
          people_count: { ...count, description: "Reported number of people, or 0 when the case file has no count." },
          vector: text, exposed: names, published: date, updated: date, reading_minutes: count,
        }),
        BreachResponse: object({ ...catalogue, breach: ref("Breach") }),
        BreachCatalogue: object({
          ...catalogue, count, total_accounts: { ...count, description: "Sum of reported counts across incidents. A person or account can appear more than once." },
          breaches: array(ref("Breach")),
        }),
        LatestBreaches: object({ ...catalogue, count, breaches: array(ref("Breach")) }),
        CaseFileIndex: object({ ...common, attribution: ref("CaseFileAttribution"), count, case_files: array(ref("CaseFile")) }),
        Stats: object({
          ...catalogue, breaches_tracked: count, accounts_affected: count, severe_breaches: count,
          stealer_log_breaches: count, verified_breaches: count, case_files: count, case_file_words: count,
        }),
        Discovery: object({
          ...catalogue, name: text, description: text, openapi: url, embed: url,
          counts: object({ breaches: count, case_files: count }),
          endpoints: object({
            breaches: url, breach_by_slug: { ...text, description: "URL template with a {slug} placeholder." },
            latest: url, case_files: url, stats: url,
          }),
        }),
      },
    },
  };
}

module.exports = { buildOpenApi };
