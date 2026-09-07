# Editorial takes

Drop an HTML fragment in here named after the breach's HIBP `Name` — not its
title — and the generator places it near the top of that article under a
"MyRecon's take" byline, above the generated analysis.

```
frontend/content/breaches/UnderArmour.html
```

The `Name` is the value in the `name` field of
`frontend/assets/data/breaches.json`, and it is also the filename the article
is built from (`underarmour.html` ← `UnderArmour`).

## What goes in the file

A fragment, not a page. No `<html>`, no `<head>`, no wrapper `<div>` — just the
content, and it inherits the site's styles:

```html
<p>The interesting part of this one is not the size. It is that the data sat
unnoticed on a forum for two months before anyone connected it to the
company.</p>

<p>That gap is the norm rather than the exception, which is why "no evidence of
misuse" in a disclosure statement means so much less than it sounds like.</p>
```

Whatever you write appears **as well as** the generated sections, never instead
of them. The severity score, the field-by-field explanation and the advice all
still render underneath, so a half-written take never leaves a broken page.

## Why it is separated

Everything else on these pages is derived from the breach record — a number, a
date, a flag. That is what lets the method note at the bottom of every article
promise the analysis cannot drift from the evidence. Hand-written opinion is a
different kind of claim, so it gets a different visual treatment and its own
byline, and the reader is never left guessing which is which.

## Removing one

Delete the file. The next build drops the section and the article goes back to
being fully generated.
